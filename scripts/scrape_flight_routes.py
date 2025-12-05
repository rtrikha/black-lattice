#!/usr/bin/env python3
"""
Flight Route Database Builder using Aerodatabox API
Builds a local route database by querying the Aerodatabox API for flight routes.
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta

import requests


class FlightRouteBuilder:
    """Builds flight route database using Aerodatabox API."""
    
    API_URL = "https://aerodatabox.p.rapidapi.com/flights/number/{flight_number}/{date}"
    DELAY_BETWEEN_REQUESTS = 0.5  # Seconds to wait between requests (be respectful of API limits)
    
    # ICAO to IATA airline code conversion (for better API compatibility)
    ICAO_TO_IATA = {
        "UAE": "EK", "QTR": "QR", "FDB": "FZ", "GFA": "GF", "ETD": "EY",
        "SVA": "SV", "AIC": "AI", "IGO": "6E", "KAC": "KU", "OMA": "WY",
    }
    
    def __init__(self, database_path: Path, rapidapi_key: str):
        """
        Initialize the route builder.
        
        Args:
            database_path: Path to the JSON file where routes will be stored.
            rapidapi_key: RapidAPI key for Aerodatabox API.
        """
        self.database_path = database_path
        self.rapidapi_key = rapidapi_key
        self.database: Dict[str, Dict] = {}
        self.load_database()
        
        self.headers = {
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": "aerodatabox.p.rapidapi.com",
            "User-Agent": "FlightRouteBuilder/1.0"
        }
        
    def load_database(self):
        """Load existing route database from JSON file."""
        if self.database_path.exists():
            try:
                with open(self.database_path, 'r', encoding='utf-8') as f:
                    self.database = json.load(f)
                print(f"Loaded {len(self.database)} existing routes from database")
            except Exception as e:
                print(f"Warning: Could not load database: {e}")
                self.database = {}
        else:
            self.database = {}
            print("Starting with empty database")
    
    def save_database(self):
        """Save route database to JSON file."""
        try:
            # Create parent directory if it doesn't exist
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.database_path, 'w', encoding='utf-8') as f:
                json.dump(self.database, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.database)} routes to {self.database_path}")
        except Exception as e:
            print(f"Error saving database: {e}")
    
    def lookup_flight_route(self, flight_number: str, date: str = None) -> Optional[Dict]:
        """
        Look up route data for a single flight number using Aerodatabox API.
        
        Args:
            flight_number: Flight number (e.g., "EK215", "QR817")
            date: Date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            Dict with route data, or None if not found/error.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Clean flight number
        flight_number = flight_number.strip().upper()
        
        # Try original flight number first
        route_data = self._try_api_lookup(flight_number, date)
        if route_data:
            return route_data
        
        # Try IATA conversion if it's a 3-letter ICAO code
        match = re.match(r'^([A-Z]{3})(\d+[A-Z]?)$', flight_number)
        if match:
            airline_code = match.group(1)
            flight_num = match.group(2)
            
            if airline_code in self.ICAO_TO_IATA:
                iata_code = self.ICAO_TO_IATA[airline_code]
                iata_flight = f"{iata_code}{flight_num}"
                route_data = self._try_api_lookup(iata_flight, date)
                if route_data:
                    return route_data
        
        # Try yesterday's date if today didn't work
        if date == datetime.now().strftime("%Y-%m-%d"):
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            route_data = self._try_api_lookup(flight_number, yesterday)
            if route_data:
                return route_data
        
        return None
    
    def _try_api_lookup(self, flight_number: str, date: str) -> Optional[Dict]:
        """Try to lookup a flight route via API."""
        url = self.API_URL.format(flight_number=flight_number, date=date)
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 204:
                # No content - flight not found
                return None
            
            if response.status_code == 429:
                print(f"  ⚠ API quota exceeded. Please wait before continuing.")
                return None
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Parse the response
            route_data = {
                "origin": "",
                "destination": "",
                "origin_city": "",
                "destination_city": "",
                "origin_country": "",
                "destination_country": "",
            }
            
            # Handle different response structures
            if isinstance(data, list) and len(data) > 0:
                flight_data = data[0]
            elif isinstance(data, dict):
                flight_data = data
            else:
                return None
            
            # Extract departure/arrival airports
            departure = (flight_data.get("departure") or 
                        flight_data.get("dep") or 
                        flight_data.get("origin") or {})
            arrival = (flight_data.get("arrival") or 
                      flight_data.get("arr") or 
                      flight_data.get("destination") or {})
            
            # Get airport codes and location info
            if isinstance(departure, dict):
                airport = departure.get("airport")
                if isinstance(airport, dict):
                    route_data["origin"] = airport.get("iata") or airport.get("icao") or ""
                    route_data["origin_city"] = airport.get("municipalityName") or airport.get("name") or ""
                    route_data["origin_country"] = airport.get("countryCode") or ""
                else:
                    route_data["origin"] = (departure.get("iata") or 
                                           departure.get("icao") or "")
            elif isinstance(departure, str):
                route_data["origin"] = departure
            
            if isinstance(arrival, dict):
                airport = arrival.get("airport")
                if isinstance(airport, dict):
                    route_data["destination"] = airport.get("iata") or airport.get("icao") or ""
                    route_data["destination_city"] = airport.get("municipalityName") or airport.get("name") or ""
                    route_data["destination_country"] = airport.get("countryCode") or ""
                else:
                    route_data["destination"] = (arrival.get("iata") or 
                                                arrival.get("icao") or "")
            elif isinstance(arrival, str):
                route_data["destination"] = arrival
            
            # Only return if we found at least origin and destination
            if route_data["origin"] and route_data["destination"]:
                # Clean up strings
                for key in route_data:
                    if isinstance(route_data[key], str):
                        route_data[key] = route_data[key].strip()
                return route_data
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            return None
        except Exception as e:
            return None
    
    def generate_flight_list(self) -> List[str]:
        """
        Generate a list of common flight numbers to query.
        Focuses on UAE/Gulf region airlines.
        """
        flights = []
        
        # Emirates (EK) - common routes (focus on likely active flights)
        # EK flights are typically 3-digit, but some are 4-digit
        for num in range(1, 1000):
            flights.append(f"EK{num:03d}")
        for num in range(2000, 3000):  # Some 4-digit EK flights
            flights.append(f"EK{num}")
        
        # FlyDubai (FZ)
        for num in range(100, 1000):
            flights.append(f"FZ{num}")
        
        # Qatar Airways (QR)
        for num in range(800, 1000):
            flights.append(f"QR{num}")
        
        # Gulf Air (GF)
        for num in range(100, 1000):
            flights.append(f"GF{num}")
        
        # Etihad (EY)
        for num in range(100, 1000):
            flights.append(f"EY{num}")
        
        # Saudia (SV)
        for num in range(100, 1000):
            flights.append(f"SV{num}")
        
        # Air India (AI)
        for num in range(100, 999):
            flights.append(f"AI{num}")
        
        # IndiGo (6E)
        for num in range(100, 999):
            flights.append(f"6E{num}")
        
        # Kuwait Airways (KU)
        for num in range(100, 999):
            flights.append(f"KU{num}")
        
        # Oman Air (WY)
        for num in range(100, 999):
            flights.append(f"WY{num}")
        
        return flights
    
    def build_database(self, flight_numbers: List[str], save_interval: int = 50):
        """
        Build route database for a list of flight numbers.
        
        Args:
            flight_numbers: List of flight numbers to query
            save_interval: Save database every N flights (to avoid data loss)
        """
        total = len(flight_numbers)
        found = 0
        skipped = 0
        errors = 0
        quota_hit = False
        
        print(f"Starting to query {total} flights...")
        print(f"Saving database every {save_interval} flights")
        print("-" * 60)
        
        for i, flight_number in enumerate(flight_numbers, 1):
            # Skip if already in database
            if flight_number.upper() in self.database:
                skipped += 1
                if i % 100 == 0:
                    print(f"Progress: {i}/{total} (found: {found}, skipped: {skipped}, errors: {errors})")
                continue
            
            print(f"[{i}/{total}] Querying {flight_number}...", end=" ")
            
            route_data = self.lookup_flight_route(flight_number)
            
            if route_data:
                self.database[flight_number.upper()] = route_data
                found += 1
                print(f"✓ Found: {route_data['origin']} → {route_data['destination']}")
            else:
                errors += 1
                print("✗ Not found")
            
            # Check for quota exceeded
            if route_data is None and "quota" in str(route_data).lower():
                quota_hit = True
                print("\n⚠ API quota exceeded. Stopping to avoid further issues.")
                print("  You can resume later - already scraped routes are saved.")
                break
            
            # Save periodically
            if i % save_interval == 0:
                self.save_database()
                print(f"  (Saved database: {len(self.database)} routes)")
            
            # Rate limiting
            if i < total and not quota_hit:
                time.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        # Final save
        self.save_database()
        
        print("-" * 60)
        print(f"Database building complete!")
        print(f"  Total flights: {total}")
        print(f"  Found routes: {found}")
        print(f"  Already in DB: {skipped}")
        print(f"  Not found/errors: {errors}")
        print(f"  Total in database: {len(self.database)}")
        
        if quota_hit:
            print("\n⚠ API quota was exceeded. Resume later to continue.")


def main():
    """Main entry point."""
    import sys
    
    # Get project root
    project_root = Path(__file__).parent.parent
    database_path = project_root / "data" / "flight_routes.json"
    
    # Load config to get API key
    config_path = project_root / "config" / "settings.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        rapidapi_key = config.get("flight_tracker", {}).get("rapidapi_key", "")
    except Exception as e:
        print(f"Error loading config: {e}")
        rapidapi_key = input("Enter your RapidAPI key: ").strip()
    
    if not rapidapi_key:
        print("Error: RapidAPI key is required")
        sys.exit(1)
    
    builder = FlightRouteBuilder(database_path, rapidapi_key)
    
    # Generate flight list
    print("Generating flight list...")
    flight_numbers = builder.generate_flight_list()
    print(f"Generated {len(flight_numbers)} flight numbers to query")
    
    # Ask user if they want to proceed
    print(f"\nThis will query {len(flight_numbers)} flights using Aerodatabox API.")
    print(f"Estimated time: ~{len(flight_numbers) * builder.DELAY_BETWEEN_REQUESTS / 60:.1f} minutes")
    print(f"Note: This uses your API quota. Only flights with active routes will be found.")
    response = input("Continue? (y/n): ")
    
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Start building database
    builder.build_database(flight_numbers, save_interval=50)


if __name__ == "__main__":
    main()
