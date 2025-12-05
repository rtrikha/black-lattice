"""
Flight Tracker module for LED matrix display.
Fetches flight data from OpenSky Network API and displays flights near user's location.
"""

import json
import math
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import requests
from PIL import Image
from rgbmatrix import RGBMatrix, graphics

from utils import (
    load_config,
    create_matrix,
    create_graphics_color,
    load_font,
    get_project_root,
)


class FlightTracker:
    """Fetches and displays flight data on the LED matrix."""
    
    # RapidAPI endpoints
    API_URL_RAPIDAPI = "https://aircraftscatter.p.rapidapi.com/lat/{lat}/lon/{lon}/"
    # Aerodatabox API for flight route lookup by flight number
    # RapidAPI version might use different format than direct API
    # Try multiple endpoint formats
    API_URL_AERODATABOX1 = "https://aerodatabox.p.rapidapi.com/flights/number/{flight_number}/{date}"
    API_URL_AERODATABOX2 = "https://aerodatabox.p.rapidapi.com/flights/search/number/{flight_number}"
    API_URL_AERODATABOX3 = "https://aerodatabox.p.rapidapi.com/flights/{flight_number}/{date}"
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the FlightTracker display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        flight_config = self.config.get("flight_tracker", {})
        self.latitude = flight_config.get("latitude", 0.0)
        self.longitude = flight_config.get("longitude", 0.0)
        self.radius_km = flight_config.get("radius_km", 25)
        self.update_interval = flight_config.get("update_interval_seconds", 30)
        self.animation_speed = flight_config.get("animation_speed", 0.5)
        
        # Load styles.json for styling
        self.styles = self._load_styles()
        route_style = self.styles.get("classes", {}).get(".flight-route", {})
        route_city_style = self.styles.get("classes", {}).get(".flight-route-city", {})
        number_style = self.styles.get("classes", {}).get(".flight-number", {})
        icon_style = self.styles.get("classes", {}).get(".flight-icon", {})
        
        # Get colors from styles (fallback to config if not in styles)
        route_color_hex = route_style.get("color", "#00FFFF")
        route_city_color_hex = route_city_style.get("color", "#00FFFF")
        number_color_hex = number_style.get("color", "#00FFFF")
        icon_color_hex = icon_style.get("color", "#0099FF")  # Default blue
        self.route_color = self._hex_to_color(route_color_hex)
        self.route_city_color = self._hex_to_color(route_city_color_hex)
        self.number_color = self._hex_to_color(number_color_hex)
        
        # Extract RGB values for SetPixel calls
        self.route_color_rgb = self._color_to_rgb(route_color_hex)
        self.route_city_color_rgb = self._color_to_rgb(route_city_color_hex)
        self.number_color_rgb = self._color_to_rgb(number_color_hex)
        self.icon_color_rgb = self._color_to_rgb(icon_color_hex)
        
        # Get font sizes from styles
        route_font_size = route_style.get("font_size", "medium")
        route_city_font_size = route_city_style.get("font_size", "xs")
        number_font_size = number_style.get("font_size", "small")
        self.route_font = self._get_font(route_font_size)
        self.route_city_font = self._get_font(route_city_font_size)
        self.number_font = self._get_font(number_font_size)
        # Store font sizes for height calculations
        self.route_font_size = route_font_size
        self.route_city_font_size = route_city_font_size
        self.number_font_size = number_font_size
        
        # Get brightness from styles (0-100, default 100)
        self.number_brightness = number_style.get("brightness", 100) / 100.0  # Convert to 0.0-1.0
        self.route_brightness = route_style.get("brightness", 100) / 100.0  # Convert to 0.0-1.0
        self.route_city_brightness = route_city_style.get("brightness", 100) / 100.0  # Convert to 0.0-1.0
        
        # Legacy color support (from config)
        self.color = create_graphics_color(flight_config.get("color", {"r": 0, "g": 255, "b": 255}))
        
        # API provider
        self.api_provider = flight_config.get("api_provider", "rapidapi").lower()
        self.rapidapi_key = flight_config.get("rapidapi_key", "")
        
        # Aviation Edge API (for route lookups)
        self.aviation_edge_key = flight_config.get("aviation_edge_key", "")
        self.route_api_provider = flight_config.get("route_api_provider", "aviation_edge").lower()
        
        # Airport cache for Aviation Edge (to avoid repeated lookups)
        self._airport_cache = {}
        
        # User-Agent for API requests
        self.user_agent = flight_config.get(
            "user_agent",
            "FlightTracker/1.0 (LED Matrix Display)"
        )
        self.demo_mode = flight_config.get("demo_mode", False)
        
        # Load aircraft icon
        self.aircraft_icon = self._load_aircraft_icon()
        
        # Keep legacy fonts for error/loading messages (backward compatibility)
        self.main_font = self.route_font  # Use route font as main
        self.small_font = self.number_font  # Use number font as small
        
        # Cached flight data
        self.flights: List[Dict] = []
        self.current_flight_index = 0
        self.last_update = 0
        self.animation_state = True  # For blinking animation
        self.last_animation_toggle = time.time()
        
        # Last seen flight (for display when no current flights)
        self.last_seen_flight: Optional[Dict] = None
        self.last_seen_time = 0
        
        # Track if we've made at least one API call
        self.has_attempted_fetch = False
        self.first_fetch_start_time = 0
        
        # Cache for flight route lookups (to avoid too many API calls)
        self.route_cache: Dict[str, Dict[str, str]] = {}
        self.route_cache_time: Dict[str, float] = {}
        self.route_cache_ttl = 3600  # Cache routes for 1 hour
        
        # Local route database (scraped from FlightAware)
        self.route_database: Dict[str, Dict[str, str]] = {}
        self._load_route_database()
        
        # Quota handling - stop API calls if quota exceeded
        self.quota_exceeded = False
        self.quota_exceeded_until = 0  # Timestamp when we can try again (24 hours)
        self.quota_error_logged = False  # Only log quota error once
        
        # Error handling
        self.consecutive_failures = 0
        self.last_error_time = 0
        self.error_cooldown = 60  # Don't print errors more than once per minute
        
        # Rate limiting - minimum time between API requests (OpenSky recommends being respectful)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
        # Scrolling marquee for city/country line
        self.city_country_scroll_position = 0
        self.city_country_scroll_speed = 20  # pixels per second
        self.last_scroll_time = time.time()
        self.city_country_text_cache = ""  # Track when text changes to reset scroll
        self.city_country_gap_size = 0  # Gap in pixels between loops
    
    def _load_route_database(self):
        """Load local route database from data/flight_routes.json."""
        project_root = get_project_root()
        self.database_path = project_root / "data" / "flight_routes.json"
        
        if self.database_path.exists():
            try:
                with open(self.database_path, 'r', encoding='utf-8') as f:
                    self.route_database = json.load(f)
                print(f"Loaded {len(self.route_database)} routes from local database")
            except Exception as e:
                print(f"Warning: Could not load route database: {e}")
                self.route_database = {}
        else:
            self.route_database = {}
            print("No local route database found (data/flight_routes.json). It will be created automatically as routes are found.")
    
    def _save_route_database(self):
        """Save route database to JSON file. Called automatically after successful API lookups."""
        try:
            # Create parent directory if it doesn't exist
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.database_path, 'w', encoding='utf-8') as f:
                json.dump(self.route_database, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save route database: {e}")
    
    def _load_styles(self) -> dict:
        """Load styles.json file."""
        project_root = get_project_root()
        styles_path = project_root / "config" / "styles.json"
        try:
            with open(styles_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load styles.json: {e}")
            return {}
    
    def _hex_to_color(self, hex_color: str) -> graphics.Color:
        """Convert hex color string to graphics.Color."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return graphics.Color(r, g, b)
        return graphics.Color(0, 255, 255)  # Default cyan
    
    def _color_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color string to (r, g, b) tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        return (0, 255, 255)  # Default cyan
    
    def _get_font(self, font_size: str) -> graphics.Font:
        """Get font based on size name from styles."""
        font_map = {
            "xs": "4x6.bdf",
            "small": "5x7.bdf",
            "medium": "7x13.bdf",
            "large": "7x13.bdf"
        }
        font_file = self.styles.get("font_sizes", {}).get(font_size, font_map.get(font_size, "7x13.bdf"))
        return load_font(font_file)
    
    def _get_font_height(self, font_size: str) -> int:
        """Get font height in pixels based on font size name."""
        # Map font sizes to their heights (from BDF file names)
        height_map = {
            "xs": 6,      # 4x6.bdf
            "small": 7,   # 5x7.bdf
            "medium": 13, # 7x13.bdf
            "large": 13   # 7x13.bdf
        }
        return height_map.get(font_size, 13)  # Default to 13 if unknown
    
    def _get_font_char_width(self, font_size: str) -> int:
        """Get font character width in pixels based on font size name."""
        # Map font sizes to their character widths (from BDF file names)
        width_map = {
            "xs": 4,      # 4x6.bdf
            "small": 5,   # 5x7.bdf
            "medium": 7, # 7x13.bdf
            "large": 7    # 7x13.bdf
        }
        return width_map.get(font_size, 7)  # Default to 7 if unknown
    
    def _load_aircraft_icon(self) -> Optional[Image.Image]:
        """Load the aircraft icon from assets folder."""
        project_root = get_project_root()
        icon_path = project_root / "assets" / "images" / "icons" / "aircraft.png"
        
        if not icon_path.exists():
            # Try without icons subdirectory
            icon_path = project_root / "assets" / "images" / "aircraft.png"
        
        if not icon_path.exists():
            print(f"Warning: Aircraft icon not found at {icon_path}")
            return None
        
        try:
            img = Image.open(icon_path)
            # Convert to RGBA if not already (handles transparency)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize to a reasonable size (12x12 pixels to fit between airport codes)
            icon_size = 12
            img = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
            print(f"DEBUG: Loaded aircraft icon from {icon_path}, size: {img.size}, mode: {img.mode}")
            return img
        except Exception as e:
            print(f"Error loading aircraft icon: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _draw_aircraft_icon(self, x: int, y: int, color_rgb: tuple, brightness: float = 1.0, visible: bool = True):
        """Draw the aircraft icon at the given position with optional brightness/pulse effect.
        
        Args:
            x: X position
            y: Y position
            color_rgb: Base color as (r, g, b) tuple
            brightness: Brightness multiplier (0.0 to 1.0) for pulse effect
            visible: Whether to draw the icon (for blink effect)
        """
        if not visible:
            return
            
        if not self.aircraft_icon:
            return
        
        icon_size = self.aircraft_icon.size[0]
        r, g, b = color_rgb
        
        # Apply brightness for pulse effect
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)
        
        for py in range(icon_size):
            for px in range(icon_size):
                pixel_x = x + px
                pixel_y = y + py
                if 0 <= pixel_x < self.canvas.width and 0 <= pixel_y < self.canvas.height:
                    try:
                        pixel = self.aircraft_icon.getpixel((px, py))
                        if len(pixel) == 4:  # RGBA
                            _, _, _, a = pixel
                            if a < 128:  # Skip mostly transparent pixels
                                continue
                        # Use the provided color with brightness applied
                        self.canvas.SetPixel(pixel_x, pixel_y, r, g, b)
                    except Exception:
                        pass
    
    def calculate_bounding_box(self) -> tuple:
        """
        Calculate bounding box (min_lat, max_lat, min_lon, max_lon) from center point and radius.
        
        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        # Earth's radius in kilometers
        R = 6371.0
        
        # Convert radius to degrees (approximate)
        # Latitude: 1 degree ≈ 111 km
        # Longitude: 1 degree ≈ 111 km * cos(latitude)
        lat_deg = self.radius_km / 111.0
        lon_deg = self.radius_km / (111.0 * math.cos(math.radians(self.latitude)))
        
        min_lat = self.latitude - lat_deg
        max_lat = self.latitude + lat_deg
        min_lon = self.longitude - lon_deg
        max_lon = self.longitude + lon_deg
        
        return (min_lat, max_lat, min_lon, max_lon)
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Returns:
            Distance in kilometers.
        """
        # Earth's radius in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    # ICAO to IATA airline code mapping for common airlines
    # Aerodatabox uses IATA codes, but ADS-B transmits ICAO codes
    ICAO_TO_IATA = {
        # UAE/Middle East
        "FDB": "FZ",   # FlyDubai
        "UAE": "EK",   # Emirates
        "ETD": "EY",   # Etihad Airways
        "QTR": "QR",   # Qatar Airways
        "GFA": "GF",   # Gulf Air
        "SVA": "SV",   # Saudia
        "KAC": "KU",   # Kuwait Airways
        "OMA": "WY",   # Oman Air
        "RJA": "RJ",   # Royal Jordanian
        "MEA": "ME",   # Middle East Airlines
        "IAW": "IA",   # Iraqi Airways
        # Asia
        "AIC": "AI",   # Air India
        "IGO": "6E",   # IndiGo
        "SEJ": "SG",   # SpiceJet
        "CPA": "CX",   # Cathay Pacific
        "SIA": "SQ",   # Singapore Airlines
        "THA": "TG",   # Thai Airways
        "MAS": "MH",   # Malaysia Airlines
        "GIA": "GA",   # Garuda Indonesia
        "PAL": "PR",   # Philippine Airlines
        "CES": "MU",   # China Eastern
        "CSN": "CZ",   # China Southern
        "CCA": "CA",   # Air China
        "ANA": "NH",   # All Nippon Airways
        "JAL": "JL",   # Japan Airlines
        "KAL": "KE",   # Korean Air
        "AAR": "OZ",   # Asiana Airlines
        # Europe
        "BAW": "BA",   # British Airways
        "DLH": "LH",   # Lufthansa
        "AFR": "AF",   # Air France
        "KLM": "KL",   # KLM
        "SWR": "LX",   # Swiss
        "AUA": "OS",   # Austrian
        "BEL": "SN",   # Brussels Airlines
        "TAP": "TP",   # TAP Portugal
        "IBE": "IB",   # Iberia
        "AZA": "AZ",   # ITA Airways (formerly Alitalia)
        "SAS": "SK",   # Scandinavian Airlines
        "FIN": "AY",   # Finnair
        "EIN": "EI",   # Aer Lingus
        "VIR": "VS",   # Virgin Atlantic
        "EZY": "U2",   # easyJet
        "RYR": "FR",   # Ryanair
        "WZZ": "W6",   # Wizz Air
        "VLG": "VY",   # Vueling
        # Americas
        "AAL": "AA",   # American Airlines
        "DAL": "DL",   # Delta Air Lines
        "UAL": "UA",   # United Airlines
        "SWA": "WN",   # Southwest Airlines
        "JBU": "B6",   # JetBlue
        "NKS": "NK",   # Spirit Airlines
        "FFT": "F9",   # Frontier Airlines
        "ACA": "AC",   # Air Canada
        "AMX": "AM",   # Aeromexico
        "AVA": "AV",   # Avianca
        "LAN": "LA",   # LATAM
        "GLO": "G3",   # Gol
        "AZU": "AD",   # Azul
        "CMP": "CM",   # Copa Airlines
        # Africa
        "ETH": "ET",   # Ethiopian Airlines
        "SAA": "SA",   # South African Airways
        "MSR": "MS",   # EgyptAir
        "RAM": "AT",   # Royal Air Maroc
        "KQA": "KQ",   # Kenya Airways
        # Australia/Oceania
        "QFA": "QF",   # Qantas
        "VOZ": "VA",   # Virgin Australia
        "ANZ": "NZ",   # Air New Zealand
        # Cargo
        "FDX": "FX",   # FedEx
        "UPS": "5X",   # UPS Airlines
        "GTI": "GT",   # Atlas Air
    }
    
    # Country code to country name mapping (ISO 3166-1 alpha-2)
    COUNTRY_CODE_TO_NAME = {
        "AE": "UAE", "IN": "India", "US": "USA", "GB": "UK", "FR": "France",
        "DE": "Germany", "IT": "Italy", "ES": "Spain", "NL": "Netherlands",
        "BE": "Belgium", "CH": "Switzerland", "AT": "Austria", "SE": "Sweden",
        "NO": "Norway", "DK": "Denmark", "FI": "Finland", "PL": "Poland",
        "CZ": "Czechia", "GR": "Greece", "PT": "Portugal", "IE": "Ireland",
        "TR": "Turkey", "EG": "Egypt", "SA": "Saudi", "KW": "Kuwait",
        "QA": "Qatar", "BH": "Bahrain", "OM": "Oman", "JO": "Jordan",
        "LB": "Lebanon", "IQ": "Iraq", "IR": "Iran", "PK": "Pakistan",
        "BD": "Bangladesh", "LK": "Sri Lanka", "MM": "Myanmar", "TH": "Thailand",
        "VN": "Vietnam", "PH": "Philippines", "ID": "Indonesia", "MY": "Malaysia",
        "SG": "Singapore", "CN": "China", "JP": "Japan", "KR": "South Korea",
        "TW": "Taiwan", "HK": "Hong Kong", "AU": "Australia", "NZ": "New Zealand",
        "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina",
        "CL": "Chile", "CO": "Colombia", "PE": "Peru", "ZA": "South Africa",
        "KE": "Kenya", "NG": "Nigeria", "GH": "Ghana", "MA": "Morocco",
        "RU": "Russia", "UA": "Ukraine", "KZ": "Kazakhstan", "UZ": "Uzbekistan",
    }

    def lookup_flight_route(self, flight_number: str) -> tuple:
        """
        Look up flight route (origin/destination).
        Checks local database first, then cache, then API as last resort.
        
        Args:
            flight_number: Flight number (e.g., "EK215", "SVA725")
        
        Returns:
            Tuple of (origin, destination, origin_city, destination_city, origin_country, destination_country),
            or ("", "", "", "", "", "") if not found.
        """
        # Clean flight number (remove spaces, convert to uppercase)
        # Handle both string and other types
        if isinstance(flight_number, str):
            flight_number = flight_number.strip().upper()
        else:
            flight_number = str(flight_number).strip().upper()
        
        # Try to convert ICAO to IATA code for better compatibility
        # Extract airline code (letters at the start) and flight number (digits + optional letter at end)
        match = re.match(r'^([A-Z]{2,3})(\d+[A-Z]?)$', flight_number)
        flight_numbers_to_try = [flight_number]  # Original first
        
        if match:
            airline_code = match.group(1)
            flight_num = match.group(2)
            
            # If it's a 3-letter ICAO code, try IATA conversion
            if len(airline_code) == 3 and airline_code in self.ICAO_TO_IATA:
                iata_code = self.ICAO_TO_IATA[airline_code]
                iata_flight = f"{iata_code}{flight_num}"
                flight_numbers_to_try.append(iata_flight)
        
        # STEP 1: Check local database first (O(1) lookup, zero API calls)
        for fn in flight_numbers_to_try:
            if fn in self.route_database:
                route_data = self.route_database[fn]
                # Update cache with database result
                self.route_cache[fn] = route_data
                self.route_cache_time[fn] = time.time()
                return (route_data.get("origin", ""), 
                       route_data.get("destination", ""),
                       route_data.get("origin_city", ""),
                       route_data.get("destination_city", ""),
                       route_data.get("origin_country", ""),
                       route_data.get("destination_country", ""))
        
        # STEP 2: Check cache (for any variant)
        for fn in flight_numbers_to_try:
            if fn in self.route_cache:
                cache_time = self.route_cache_time.get(fn, 0)
                if time.time() - cache_time < self.route_cache_ttl:
                    cached = self.route_cache[fn]
                    return (cached.get("origin", ""), 
                           cached.get("destination", ""),
                           cached.get("origin_city", ""),
                           cached.get("destination_city", ""),
                           cached.get("origin_country", ""),
                           cached.get("destination_country", ""))
        
        # STEP 3: Only call API as last resort (if API key available and quota not exceeded)
        # Try Aviation Edge API first if configured
        if self.route_api_provider == "aviation_edge" and self.aviation_edge_key:
            route_data = self._lookup_route_aviation_edge(flight_numbers_to_try)
            if route_data:
                origin, destination, origin_city, destination_city, origin_country, destination_country = route_data
                # Save to database automatically
                route_dict = {
                    "origin": origin,
                    "destination": destination,
                    "origin_city": origin_city,
                    "destination_city": destination_city,
                    "origin_country": origin_country,
                    "destination_country": destination_country
                }
                if flight_number not in self.route_database:
                    self.route_database[flight_number] = route_dict
                    self._save_route_database()
                    print(f"DEBUG: Saved route for {flight_number} to database: {origin} -> {destination}")
                return route_data
            # Aviation Edge failed - don't fall back to Aerodatabox if Aviation Edge is primary
            return ("", "", "", "", "", "")
        
        # Fall back to Aerodatabox API (existing) only if Aviation Edge not configured
        if not self.rapidapi_key:
            return ("", "", "", "", "", "")
        
        # Check if quota is exceeded - don't make API calls
        if self.quota_exceeded:
            current_time = time.time()
            if current_time < self.quota_exceeded_until:
                # Still in cooldown period, return empty
                return ("", "", "", "", "", "")
            else:
                # Cooldown expired, reset flag and try again
                self.quota_exceeded = False
                self.quota_error_logged = False
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        headers = {
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": "aerodatabox.p.rapidapi.com",
            "User-Agent": self.user_agent
        }
        
        # Optimize: Only try the most reliable endpoint first
        # Only try additional endpoints if the first one fails
        # This reduces API calls from ~10 per flight to ~1-2 per flight
        endpoints_to_try = [
            (self.API_URL_AERODATABOX1, today),  # Most reliable endpoint with today's date
        ]
        
        # Only try more endpoints if first attempt fails AND quota not exceeded
        if not self.quota_exceeded:
            # Add fallback endpoints (only if needed)
            endpoints_to_try.extend([
                (self.API_URL_AERODATABOX1, yesterday),  # Try yesterday if today fails
                (self.API_URL_AERODATABOX2, None),  # Alternative endpoint format
            ])
        
        first_attempt = True
        # Try original flight number first, only try IATA conversion if original fails
        # This reduces calls from 2 variants × 5 endpoints = 10 calls to ~1-3 calls
        for fn_to_try in flight_numbers_to_try:
            for endpoint_template, date_str in endpoints_to_try:
                if date_str:
                    url = endpoint_template.format(flight_number=fn_to_try, date=date_str)
                else:
                    url = endpoint_template.format(flight_number=fn_to_try)
                try:
                    # Add a small delay to avoid rate limits
                    time.sleep(0.3)
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    # Debug: Print response status
                    if response.status_code == 204:
                        # No content - flight not found, try next variant/endpoint
                        if first_attempt:
                            print(f"DEBUG: No data for {fn_to_try} (204 No Content)")
                            first_attempt = False
                        continue
                    
                    # Handle quota exceeded (429)
                    if response.status_code == 429:
                        self.quota_exceeded = True
                        # Don't try again for 24 hours
                        self.quota_exceeded_until = time.time() + (24 * 3600)
                        if not self.quota_error_logged:
                            print(f"WARNING: API quota exceeded. Route lookups disabled for 24 hours.")
                            print(f"  Response: {response.text[:200]}")
                            self.quota_error_logged = True
                        # Stop trying all endpoints immediately
                        return ("", "", "", "", "", "")
                    
                    if response.status_code != 200:
                        if first_attempt:
                            print(f"DEBUG: Aerodatabox API returned status {response.status_code} for flight {fn_to_try}")
                            print(f"  URL: {url}")
                            print(f"  Response: {response.text[:300]}")
                            first_attempt = False
                        continue  # Try next endpoint
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Parse the response - format may vary
                        origin = ""
                        destination = ""
                        origin_city = ""
                        destination_city = ""
                        origin_country = ""
                        destination_country = ""
                    
                        # Try different response structures
                        if isinstance(data, list) and len(data) > 0:
                            flight_data = data[0]
                        elif isinstance(data, dict):
                            flight_data = data
                        else:
                            continue  # Try next endpoint
                        
                        # Try to extract origin and destination
                        # Check for departure/arrival airports
                        departure = (flight_data.get("departure") or 
                                    flight_data.get("dep") or 
                                    flight_data.get("origin") or {})
                        arrival = (flight_data.get("arrival") or 
                                  flight_data.get("arr") or 
                                  flight_data.get("destination") or {})
                        
                        # Get airport codes and location info - handle nested structure
                        # API returns: departure.airport.iata or just departure.iata
                        if isinstance(departure, dict):
                            airport = departure.get("airport")
                            if isinstance(airport, dict):
                                # Nested: departure.airport.iata
                                origin = airport.get("iata") or airport.get("icao") or ""
                                # Extract city and country
                                origin_city = airport.get("municipalityName") or airport.get("name") or ""
                                origin_country = airport.get("countryCode") or ""
                            else:
                                # Flat: departure.iata
                                origin = (departure.get("iata") or 
                                         departure.get("icao") or 
                                         departure.get("iataCode") or 
                                         airport or "")
                        elif isinstance(departure, str):
                            origin = departure
                        
                        if isinstance(arrival, dict):
                            airport = arrival.get("airport")
                            if isinstance(airport, dict):
                                # Nested: arrival.airport.iata
                                destination = airport.get("iata") or airport.get("icao") or ""
                                # Extract city and country
                                destination_city = airport.get("municipalityName") or airport.get("name") or ""
                                destination_country = airport.get("countryCode") or ""
                            else:
                                # Flat: arrival.iata
                                destination = (arrival.get("iata") or 
                                              arrival.get("icao") or 
                                              arrival.get("iataCode") or 
                                              airport or "")
                        elif isinstance(arrival, str):
                            destination = arrival
                        
                        # Also try direct fields
                        if not origin:
                            origin = (flight_data.get("from") or 
                                     flight_data.get("From") or 
                                     flight_data.get("originIata") or 
                                     flight_data.get("departureIata") or "")
                        
                        if not destination:
                            destination = (flight_data.get("to") or 
                                         flight_data.get("To") or 
                                         flight_data.get("destinationIata") or 
                                         flight_data.get("arrivalIata") or "")
                        
                        # Ensure origin and destination are strings before stripping
                        if isinstance(origin, str):
                            origin = origin.strip()
                        elif origin:
                            origin = str(origin).strip()
                        else:
                            origin = ""
                        
                        if isinstance(destination, str):
                            destination = destination.strip()
                        elif destination:
                            destination = str(destination).strip()
                        else:
                            destination = ""
                        
                        # Clean city and country strings
                        if isinstance(origin_city, str):
                            origin_city = origin_city.strip()
                        else:
                            origin_city = str(origin_city).strip() if origin_city else ""
                        
                        if isinstance(destination_city, str):
                            destination_city = destination_city.strip()
                        else:
                            destination_city = str(destination_city).strip() if destination_city else ""
                        
                        origin_country = origin_country.strip() if isinstance(origin_country, str) else str(origin_country).strip() if origin_country else ""
                        destination_country = destination_country.strip() if isinstance(destination_country, str) else str(destination_country).strip() if destination_country else ""
                        
                        # Cache the result (using original flight number as key)
                        if origin or destination:
                            route_data = {
                                "origin": origin,
                                "destination": destination,
                                "origin_city": origin_city,
                                "destination_city": destination_city,
                                "origin_country": origin_country,
                                "destination_country": destination_country
                            }
                            
                            # Save to cache
                            self.route_cache[flight_number] = route_data
                            self.route_cache_time[flight_number] = time.time()
                            
                            # Save to database for future lookups (auto-populate over time)
                            if flight_number not in self.route_database:
                                self.route_database[flight_number] = route_data
                                self._save_route_database()
                                print(f"DEBUG: Saved route for {flight_number} to database: {origin} -> {destination}")
                            
                            # Also save variant if different (e.g., IATA vs ICAO)
                            if fn_to_try != flight_number and fn_to_try not in self.route_database:
                                self.route_database[fn_to_try] = route_data
                                self._save_route_database()
                            
                            if fn_to_try != flight_number:
                                print(f"DEBUG: Found route for {flight_number} (via {fn_to_try}): {origin} -> {destination}")
                            else:
                                print(f"DEBUG: Found route for {flight_number}: {origin} -> {destination}")
                            
                            return (origin, destination, origin_city, destination_city, origin_country, destination_country)
                        
                except Exception as e:
                    if first_attempt:
                        print(f"DEBUG: Error trying endpoint for {fn_to_try}: {e}")
                        first_attempt = False
                    continue  # Try next endpoint
        
        # All endpoints failed (only print once)
        if flight_number not in self.route_cache:  # Don't spam if we've seen this flight before
            print(f"DEBUG: All Aerodatabox endpoints failed for flight {flight_number}")
        return ("", "", "", "", "", "")
    
    def _lookup_route_aviation_edge(self, flight_numbers_to_try: List[str]) -> Optional[tuple]:
        """
        Look up flight route using Aviation Edge API.
        Uses /flights endpoint with flightIcao parameter (capital I).
        
        Args:
            flight_numbers_to_try: List of flight number variants to try
        
        Returns:
            Tuple of (origin, destination, origin_city, destination_city, origin_country, destination_country),
            or None if not found.
        """
        # Use /flights endpoint with flightIcao parameter (capital I)
        # This accepts full flight number format like UAE215, QTR828, UAE8LT
        for flight_number in flight_numbers_to_try:
            try:
                url = f"https://aviation-edge.com/v2/public/flights?key={self.aviation_edge_key}&flightIcao={flight_number}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        # Take the first flight result
                        flight = data[0]
                        
                        departure = flight.get("departure", {})
                        arrival = flight.get("arrival", {})
                        
                        origin = departure.get("iataCode", "").strip()
                        destination = arrival.get("iataCode", "").strip()
                        
                        if origin and destination:
                            # Look up airport details for city/country
                            origin_city, origin_country = self._get_airport_details(origin)
                            dest_city, dest_country = self._get_airport_details(destination)
                            
                            return (origin, destination, origin_city, dest_city, origin_country, dest_country)
                
            except Exception as e:
                # Continue to next variant
                continue
        
        return None
    
    def _get_airport_details(self, airport_code: str) -> tuple:
        """
        Get airport city and country from Aviation Edge airport database.
        Uses cache to avoid repeated API calls.
        
        Args:
            airport_code: IATA airport code (e.g., "DXB")
        
        Returns:
            Tuple of (city, country_code)
        """
        if not airport_code or not self.aviation_edge_key:
            return ("", "")
        
        # Check cache first
        if airport_code in self._airport_cache:
            return self._airport_cache[airport_code]
        
        try:
            url = f"https://aviation-edge.com/v2/public/airportDatabase?key={self.aviation_edge_key}&codeIataAirport={airport_code}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    airport = data[0]
                    # nameAirport can be either city name or airport name
                    # Try to extract city name by removing common airport suffixes
                    airport_name = airport.get("nameAirport", "").strip()
                    city = airport_name
                    
                    # If it contains airport-related terms, try to extract just the city
                    # Remove common patterns: " Airport", " International", " International Airport"
                    city = re.sub(r'\s+(International\s+)?Airport$', '', city, flags=re.IGNORECASE)
                    city = re.sub(r'\s+International$', '', city, flags=re.IGNORECASE)
                    # Remove other common airport name patterns
                    city = re.sub(r'\s*\([^)]+\)$', '', city)  # Remove parentheses like "(Fiumicino)"
                    
                    # If after cleaning it's empty or too short, use the original
                    if not city or len(city) < 2:
                        city = airport_name
                    
                    country = airport.get("codeIso2Country", "").strip()
                    
                    # Cache the result
                    self._airport_cache[airport_code] = (city, country)
                    return (city, country)
        except Exception:
            pass
        
        # Return empty if not found
        self._airport_cache[airport_code] = ("", "")
        return ("", "")
    
    def fetch_flights_adsbexchange(self) -> Optional[List[Dict]]:
        """Fetch flights from ADSB Exchange public API."""
        # Try different endpoint formats
        endpoints_to_try = [
            {
                "url": "https://public-api.adsbexchange.com/VirtualRadar/AircraftList.json",
                "params": {
                    "lat": self.latitude,
                    "lon": self.longitude,
                    "fDstL": 0,
                    "fDstU": self.radius_km * 1.60934  # Convert km to miles
                }
            },
            {
                "url": "https://public-api.adsbexchange.com/VirtualRadar/AircraftList.json",
                "params": {
                    "lat": self.latitude,
                    "lng": self.longitude,  # Try 'lng' instead of 'lon'
                    "fDstL": 0,
                    "fDstU": self.radius_km * 1.60934
                }
            },
        ]
        
        headers = {"User-Agent": self.user_agent}
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(
                    endpoint["url"],
                    params=endpoint["params"],
                    headers=headers,
                    timeout=10
                )
                
                # Check if we got a valid response
                if response.status_code != 200:
                    continue
                
                # Check if response has content
                if not response.text or len(response.text.strip()) == 0:
                    continue
                
                try:
                    data = response.json()
                except ValueError:
                    # Not valid JSON, try next endpoint
                    continue
                
                # Try different response formats
                aircraft_list = None
                if "acList" in data:
                    aircraft_list = data.get("acList", [])
                elif "ac" in data:
                    aircraft_list = data.get("ac", [])
                elif isinstance(data, list):
                    aircraft_list = data
                
                if not aircraft_list:
                    continue
                
                flights = []
                for aircraft in aircraft_list:
                    if not isinstance(aircraft, dict):
                        continue
                    
                    # Try different field names for callsign
                    callsign = (aircraft.get("Call") or 
                               aircraft.get("callsign") or 
                               aircraft.get("flight") or 
                               aircraft.get("Flight")).strip() if aircraft.get("Call") or aircraft.get("callsign") or aircraft.get("flight") or aircraft.get("Flight") else ""
                    
                    if not callsign:
                        continue
                    
                    # Get altitude
                    alt = (aircraft.get("Alt") or 
                          aircraft.get("altitude") or 
                          aircraft.get("alt_baro") or 0)
                    
                    # Check if on ground
                    on_ground = (aircraft.get("Gnd", False) or 
                                aircraft.get("on_ground", False) or 
                                alt < 100)
                    
                    if not on_ground:
                        aircraft_lat = aircraft.get("Lat") or aircraft.get("lat")
                        aircraft_lon = aircraft.get("Long") or aircraft.get("lon")
                        
                        if aircraft_lat and aircraft_lon:
                            # Calculate distance from user's location
                            distance = self._calculate_distance(
                                self.latitude, self.longitude,
                                aircraft_lat, aircraft_lon
                            )
                            
                        # Try to get origin and destination - check many possible field names
                        origin = (aircraft.get("From") or 
                                 aircraft.get("from") or 
                                 aircraft.get("Orig") or 
                                 aircraft.get("origin") or 
                                 aircraft.get("dep") or
                                 aircraft.get("Dep") or
                                 aircraft.get("Departure") or
                                 aircraft.get("departure") or
                                 aircraft.get("Src") or
                                 aircraft.get("src") or
                                 aircraft.get("Route") or
                                 aircraft.get("route") or "")
                        destination = (aircraft.get("To") or 
                                      aircraft.get("to") or 
                                      aircraft.get("Dest") or 
                                      aircraft.get("destination") or 
                                      aircraft.get("arr") or
                                      aircraft.get("Arr") or
                                      aircraft.get("Arrival") or
                                      aircraft.get("arrival") or
                                      aircraft.get("Dst") or
                                      aircraft.get("dst") or "")
                        
                        flights.append({
                            "callsign": callsign,
                            "latitude": aircraft_lat,
                            "longitude": aircraft_lon,
                            "altitude": alt,
                            "distance": distance,
                            "origin": origin.strip() if isinstance(origin, str) and origin else str(origin).strip() if origin else "",
                            "destination": destination.strip() if isinstance(destination, str) and destination else str(destination).strip() if destination else "",
                        })
                
                # Return only the closest flight
                if flights:
                    flights.sort(key=lambda x: x.get("distance", float('inf')))
                    closest_flight = flights[0]
                    
                    # Preserve any origin/destination from the initial API response
                    existing_origin = closest_flight.get("origin", "")
                    existing_destination = closest_flight.get("destination", "")
                    
                    # If API already provided origin/destination codes, just get city/country for them
                    # This avoids making an unnecessary route lookup API call
                    if existing_origin and existing_destination:
                        # API already has the codes - just get city/country details
                        if not closest_flight.get("origin_city") or not closest_flight.get("destination_city"):
                            origin_city, origin_country = self._get_airport_details(existing_origin)
                            dest_city, dest_country = self._get_airport_details(existing_destination)
                            if origin_city:
                                closest_flight["origin_city"] = origin_city
                            if origin_country:
                                closest_flight["origin_country"] = origin_country
                            if dest_city:
                                closest_flight["destination_city"] = dest_city
                            if dest_country:
                                closest_flight["destination_country"] = dest_country
                    else:
                        # API doesn't have route info - look it up using Aviation Edge
                        callsign = closest_flight.get("callsign", "")
                        if callsign:
                            origin, destination, origin_city, dest_city, origin_country, dest_country = self.lookup_flight_route(callsign)
                            if origin:
                                closest_flight["origin"] = origin
                            if destination:
                                closest_flight["destination"] = destination
                            if origin_city:
                                closest_flight["origin_city"] = origin_city
                            if dest_city:
                                closest_flight["destination_city"] = dest_city
                            if origin_country:
                                closest_flight["origin_country"] = origin_country
                            if dest_country:
                                closest_flight["destination_country"] = dest_country
                    
                    return [closest_flight]  # Only return the closest flight
                
                return []
                    
            except Exception as e:
                # Try next endpoint
                continue
        
        # All endpoints failed
        self._log_error_once("ADSB Exchange API: All endpoints failed or returned no flights")
        return None
    
    def fetch_flights_demo(self) -> List[Dict]:
        """Return demo flight data for testing."""
        import random
        demo_flights = [
            {
                "callsign": "EK215",
                "latitude": self.latitude + 0.1,
                "longitude": self.longitude + 0.1,
                "altitude": 35000,
                "distance": 8.5,
                "origin": "DXB",
                "destination": "LAX"
            },
            {
                "callsign": "QR817",
                "latitude": self.latitude - 0.1,
                "longitude": self.longitude - 0.1,
                "altitude": 38000,
                "distance": 12.3,
                "origin": "DOH",
                "destination": "DXB"
            },
            {
                "callsign": "FZ304",
                "latitude": self.latitude + 0.05,
                "longitude": self.longitude,
                "altitude": 32000,
                "distance": 5.2,
                "origin": "DXB",
                "destination": "BOM"
            },
            {
                "callsign": "BAH123",
                "latitude": self.latitude + 0.08,
                "longitude": self.longitude + 0.05,
                "altitude": 36000,
                "distance": 9.1,
                "origin": "BAH",
                "destination": "DXB"
            },
        ]
        # Return random flight for demo
        return [random.choice(demo_flights)]
    
    def fetch_flights_rapidapi(self) -> Optional[List[Dict]]:
        """Fetch flights from RapidAPI Aircraft Scatter."""
        if not self.rapidapi_key:
            self._log_error_once("RapidAPI key not configured in settings.json")
            return None
        
        try:
            url = self.API_URL_RAPIDAPI.format(lat=self.latitude, lon=self.longitude)
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": "aircraftscatter.p.rapidapi.com",
                "User-Agent": self.user_agent
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse the response - format may vary, let's handle common structures
            flights = []
            
            # Try different response formats
            aircraft_list = None
            if isinstance(data, list):
                aircraft_list = data
            elif isinstance(data, dict):
                # Try common keys
                aircraft_list = (data.get("ac") or 
                               data.get("aircraft") or 
                               data.get("acList") or 
                               data.get("data") or [])
            
            if not aircraft_list:
                return []
            
            for aircraft in aircraft_list:
                if not isinstance(aircraft, dict):
                    continue
                
                # Try different field names for callsign
                # Note: "flight" field in RapidAPI has trailing spaces, so strip it
                callsign = (aircraft.get("Call") or 
                           aircraft.get("callsign") or 
                           aircraft.get("flight") or 
                           aircraft.get("Flight") or
                           aircraft.get("reg") or "").strip()
                
                if not callsign:
                    continue
                
                # Get altitude - RapidAPI uses "alt_baro"
                alt = (aircraft.get("alt_baro") or
                      aircraft.get("Alt") or 
                      aircraft.get("altitude") or 
                      aircraft.get("baro_altitude") or 0)
                
                # Check if on ground - try multiple field names
                on_ground = (aircraft.get("Gnd", False) or 
                            aircraft.get("on_ground", False) or 
                            aircraft.get("ground", False) or
                            alt < 100)
                
                if not on_ground:
                    # Calculate distance from user's location
                    # RapidAPI uses lowercase "lat" and "lon"
                    aircraft_lat = aircraft.get("lat") or aircraft.get("Lat")
                    aircraft_lon = aircraft.get("lon") or aircraft.get("Long")
                    
                    if aircraft_lat and aircraft_lon:
                        # Calculate distance in km using Haversine formula
                        distance = self._calculate_distance(
                            self.latitude, self.longitude,
                            aircraft_lat, aircraft_lon
                        )
                        
                        # Try to get origin and destination - check many possible field names
                        origin = (aircraft.get("From") or 
                                 aircraft.get("from") or 
                                 aircraft.get("Orig") or 
                                 aircraft.get("origin") or 
                                 aircraft.get("dep") or
                                 aircraft.get("Dep") or
                                 aircraft.get("Departure") or
                                 aircraft.get("departure") or
                                 aircraft.get("Src") or
                                 aircraft.get("src") or
                                 aircraft.get("Route") or
                                 aircraft.get("route") or "")
                        destination = (aircraft.get("To") or 
                                      aircraft.get("to") or 
                                      aircraft.get("Dest") or 
                                      aircraft.get("destination") or 
                                      aircraft.get("arr") or
                                      aircraft.get("Arr") or
                                      aircraft.get("Arrival") or
                                      aircraft.get("arrival") or
                                      aircraft.get("Dst") or
                                      aircraft.get("dst") or "")
                        
                        # Store raw aircraft data for debugging
                        self._last_aircraft_data = aircraft
                        
                        flights.append({
                            "callsign": callsign,
                            "latitude": aircraft_lat,
                            "longitude": aircraft_lon,
                            "altitude": alt,
                            "distance": distance,
                            "origin": origin.strip() if isinstance(origin, str) and origin else str(origin).strip() if origin else "",
                            "destination": destination.strip() if isinstance(destination, str) and destination else str(destination).strip() if destination else "",
                            "last_contact": aircraft.get("PosTime") or aircraft.get("last_contact") or time.time()
                        })
            
            # Sort by distance (closest first) and return only the closest flight
            if flights:
                flights.sort(key=lambda x: x.get("distance", float('inf')))
                closest_flight = flights[0]
                
                # Preserve any origin/destination from the initial API response
                existing_origin = closest_flight.get("origin", "")
                existing_destination = closest_flight.get("destination", "")
                
                # If RapidAPI already provided origin/destination codes, just get city/country for them
                # This avoids making an unnecessary route lookup API call
                if existing_origin and existing_destination:
                    # RapidAPI already has the codes - just get city/country details
                    if not closest_flight.get("origin_city") or not closest_flight.get("destination_city"):
                        origin_city, origin_country = self._get_airport_details(existing_origin)
                        dest_city, dest_country = self._get_airport_details(existing_destination)
                        if origin_city:
                            closest_flight["origin_city"] = origin_city
                        if origin_country:
                            closest_flight["origin_country"] = origin_country
                        if dest_city:
                            closest_flight["destination_city"] = dest_city
                        if dest_country:
                            closest_flight["destination_country"] = dest_country
                else:
                    # RapidAPI doesn't have route info - look it up using Aviation Edge
                    callsign = closest_flight.get("callsign", "")
                    if callsign:
                        origin, destination, origin_city, dest_city, origin_country, dest_country = self.lookup_flight_route(callsign)
                        if origin:
                            closest_flight["origin"] = origin
                        if destination:
                            closest_flight["destination"] = destination
                        if origin_city:
                            closest_flight["origin_city"] = origin_city
                        if dest_city:
                            closest_flight["destination_city"] = dest_city
                        if origin_country:
                            closest_flight["origin_country"] = origin_country
                        if dest_country:
                            closest_flight["destination_country"] = dest_country
                
                return [closest_flight]  # Return only the closest flight
            
            return []
            
        except Exception as e:
            self._log_error_once(f"RapidAPI error: {e}")
            return None
    
    def fetch_flights(self, max_retries: int = 1) -> Optional[List[Dict]]:
        """
        Fetch flight data from ADSB Exchange API.
        
        Args:
            max_retries: Maximum number of retry attempts (not used, kept for compatibility).
        
        Returns:
            List of flight dictionaries or None if failed.
        """
        # Demo mode - return sample data
        if self.demo_mode:
            return self.fetch_flights_demo()
        
        # Respect rate limits
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        
        self.last_request_time = time.time()
        
        # Use the configured API provider
        if self.api_provider == "rapidapi":
            flights = self.fetch_flights_rapidapi()
        else:
            # Fallback to ADSB Exchange
            # Use the configured API provider
            if self.api_provider == "rapidapi":
                flights = self.fetch_flights_rapidapi()
            else:
                # Fallback to ADSB Exchange
                flights = self.fetch_flights_adsbexchange()
        
        if flights is not None:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
        
        return flights
    
    def _log_error_once(self, message: str):
        """
        Log an error message, but only once per error_cooldown period.
        
        Args:
            message: Error message to log.
        """
        current_time = time.time()
        if (current_time - self.last_error_time) >= self.error_cooldown:
            print(message)
            self.last_error_time = current_time
            self.consecutive_failures += 1
    
    def update_flights(self, force: bool = False):
        """
        Update flight data if needed.
        
        Args:
            force: Force update even if cache is fresh.
        """
        current_time = time.time()
        
        # If we have consecutive failures, increase the update interval to avoid hammering the API
        effective_interval = self.update_interval
        if self.consecutive_failures > 3:
            effective_interval = self.update_interval * 2  # Double the interval after 3 failures
        
        if force or (current_time - self.last_update) >= effective_interval:
            # Mark that we're attempting a fetch (set this early so display updates)
            if not self.has_attempted_fetch:
                self.has_attempted_fetch = True
                self.first_fetch_start_time = current_time
            
            flights = self.fetch_flights()
            if flights is not None:
                # Update flights list
                self.flights = flights
                self.last_update = current_time
                
                # Reset flight index when new data arrives
                if flights:
                    # We have current flights - update last seen
                    self.current_flight_index = 0
                    # Store the first flight as last seen
                    self.last_seen_flight = flights[0].copy()
                    self.last_seen_flight["seen_at"] = current_time
                    self.last_seen_time = current_time
                # If flights is empty list, keep the existing last_seen_flight
                # This way we always have something to display
    
    def draw_plane_icon(self, x: int, y: int, visible: bool = True):
        """
        Draw a simple plane icon at the given position.
        
        Args:
            x: X coordinate (left position)
            y: Y coordinate (top position)
            visible: Whether the icon should be visible (for blinking)
        """
        if not visible:
            return
        
        # Simple plane icon (8x8 pixels)
        # Using SetPixel to draw the plane shape
        plane_pixels = [
            # Top wing
            (x + 2, y),
            (x + 3, y),
            # Body
            (x + 1, y + 1),
            (x + 2, y + 1),
            (x + 3, y + 1),
            (x + 4, y + 1),
            (x + 5, y + 1),
            # Middle
            (x, y + 2),
            (x + 1, y + 2),
            (x + 2, y + 2),
            (x + 3, y + 2),
            (x + 4, y + 2),
            (x + 5, y + 2),
            (x + 6, y + 2),
            # Bottom wing
            (x + 2, y + 3),
            (x + 3, y + 3),
            # Tail
            (x + 1, y + 4),
            (x + 2, y + 4),
        ]
        
        for px, py in plane_pixels:
            if 0 <= px < self.canvas.width and 0 <= py < self.canvas.height:
                self.canvas.SetPixel(px, py, self.color.red, self.color.green, self.color.blue)
    
    def display(self):
        """Display flight information with animated plane icon."""
        self.canvas.Clear()
        
        # Update animation state
        current_time = time.time()
        animation_speed = self.animation_speed
        
        if not self.flights:
            # Use slower animation for last seen flights
            animation_speed = self.animation_speed * 2
        
        if (current_time - self.last_animation_toggle) >= animation_speed:
            self.animation_state = not self.animation_state
            self.last_animation_toggle = current_time
        
        # Always ensure something is displayed
        if not self.flights:
            # Priority 1: Show last seen flight if available (always show this if we have it)
            if self.last_seen_flight and self.last_seen_flight.get("callsign"):
                # Display last seen flight
                callsign = self.last_seen_flight.get("callsign", "UNKNOWN")
                
                # Draw plane icon (blinking)
                self.draw_plane_icon(2, 2, self.animation_state)
                
                # Truncate if too long for display
                if len(callsign) > 8:
                    callsign = callsign[:8]
                
                # Position text to the right of the icon
                graphics.DrawText(self.canvas, self.main_font, 12, 12, self.color, callsign)
                
                # Show "Last:" indicator
                graphics.DrawText(self.canvas, self.small_font, 12, 22, self.color, "Last:")
            # Priority 2: If we've attempted fetch, show status (error or no flights)
            elif self.has_attempted_fetch:
                if self.consecutive_failures > 0:
                    # Show API error message (we've tried and failed)
                    msg = "API error"
                    graphics.DrawText(self.canvas, self.small_font, 2, 16, self.color, msg)
                else:
                    # We've attempted fetch and got empty result (no flights in area)
                    msg = "No flights"
                    # Center the message
                    x_pos = max(2, (self.canvas.width - len(msg) * 5) // 2)
                    graphics.DrawText(self.canvas, self.small_font, x_pos, 16, self.color, msg)
            else:
                # Show pulsing aircraft icon instead of "Loading..." text
                if self.aircraft_icon:
                    # Center the icon horizontally and vertically
                    icon_size = self.aircraft_icon.size[0]
                    icon_x = (self.canvas.width - icon_size) // 2
                    icon_y = (self.canvas.height - icon_size) // 2
                    
                    # Pulse animation (similar to route icon pulse)
                    fade_down_time = 0.5    # Time to fade from max to min
                    gap_time = 1.0          # Pause at minimum brightness
                    fade_up_time = 0.5      # Time to fade from min to max
                    total_cycle = fade_down_time + gap_time + fade_up_time
                    
                    # Brightness range
                    min_brightness = 0.3    # 30%
                    max_brightness = 1.0    # 100%
                    
                    # Calculate position in animation cycle
                    cycle_position = current_time % total_cycle
                    
                    if cycle_position < fade_down_time:
                        # Fading down (100% -> 30%)
                        progress = cycle_position / fade_down_time
                        pulse_brightness = max_brightness - (max_brightness - min_brightness) * progress
                    elif cycle_position < fade_down_time + gap_time:
                        # Gap at minimum brightness
                        pulse_brightness = min_brightness
                    else:
                        # Fading up (30% -> 100%)
                        progress = (cycle_position - fade_down_time - gap_time) / fade_up_time
                        pulse_brightness = min_brightness + (max_brightness - min_brightness) * progress
                    
                    # Draw pulsing aircraft icon
                    self._draw_aircraft_icon(icon_x, icon_y, self.icon_color_rgb, 
                                            brightness=pulse_brightness, 
                                            visible=True)
                else:
                    # Fallback to text if icon not available
                    msg = "Loading..."
                    x_pos = max(2, (self.canvas.width - len(msg) * 5) // 2)
                    graphics.DrawText(self.canvas, self.small_font, x_pos, 16, self.color, msg)
        else:
            # Get the closest flight (only one flight now)
            flight = self.flights[0]
            callsign = flight.get("callsign", "UNKNOWN")
            origin = flight.get("origin", "")
            destination = flight.get("destination", "")
            
            
            # Calculate vertical positions for centered layout
            # Layout: Flight number (top), Route (middle), City to Country (bottom)
            # Canvas height is 32 pixels
            # Get actual font heights from the fonts being used
            icon_size = 12
            number_font_height = self._get_font_height(self.number_font_size)  # Dynamic based on style
            route_font_height = self._get_font_height(self.route_font_size)  # Dynamic based on style
            city_font_height = self._get_font_height(self.route_city_font_size)  # Dynamic based on style
            gap1 = 0  # Gap between flight number and route
            gap2 = 1  # Gap between route and city/country line
            
            # Total content height: number + gap1 + route + gap2 + city
            total_content_height = number_font_height + gap1 + route_font_height + gap2 + city_font_height
            
            # Calculate the visual center of the canvas
            canvas_center_y = self.canvas.height / 2.0  # 16.0 for 32px canvas
            
            # Calculate the visual center of our content block
            # Move up by 2 pixels to balance spacing (4 grids top, 2 grids bottom -> 3 grids each)
            top_margin = canvas_center_y - (total_content_height / 2.0) - 1
            
            # Flight number baseline (TOP LINE)
            number_y = int(top_margin + number_font_height)
            
            # Route text baseline (MIDDLE LINE)
            route_y = int(top_margin + number_font_height + gap1 + route_font_height)
            
            # City/Country text baseline (BOTTOM LINE)
            city_y = int(top_margin + number_font_height + gap1 + route_font_height + gap2 + city_font_height)
            
            # Icon should be vertically centered with the route text
            # For 7x13 font, the visual center is about 6-7 pixels above baseline
            # Position icon so its center aligns with text visual center
            text_visual_center = route_y - 6  # Approximate visual center of text
            icon_y = text_visual_center - icon_size // 2 + 1  # Center icon, then move 1 pixel down
            
            # Display flight number on TOP LINE - HORIZONTALLY CENTERED
            # Truncate if too long for display
            if len(callsign) > 10:
                callsign = callsign[:10]
            
            # Flight number character width (dynamic based on font size)
            number_char_width = self._get_font_char_width(self.number_font_size)
            number_width = len(callsign) * number_char_width
            number_x = max(0, (self.canvas.width - number_width) // 2)
            
            # Apply brightness from styles.json to flight number color
            r, g, b = self.number_color_rgb
            dimmed_r = int(r * self.number_brightness)
            dimmed_g = int(g * self.number_brightness)
            dimmed_b = int(b * self.number_brightness)
            dimmed_number_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
            
            graphics.DrawText(self.canvas, self.number_font, number_x, number_y, dimmed_number_color, callsign)
            
            # Display route on BOTTOM LINE with aircraft icon - CENTERED
            if origin or destination:
                # Get airport codes (first 3 characters)
                orig_code = origin[:3] if origin and len(origin) >= 3 else origin
                dest_code = destination[:3] if destination and len(destination) >= 3 else destination
                
                # Route uses MEDIUM font (7x13) = 7 pixels wide per character
                route_char_width = 7
                spacing = 2  # Space on each side of icon
                
                # Calculate widths
                orig_width = len(orig_code) * route_char_width if orig_code else 0
                dest_width = len(dest_code) * route_char_width if dest_code else 0
                icon_width = icon_size if self.aircraft_icon else 10  # "->" fallback
                
                # Total width: origin + space + icon + space + destination
                total_width = orig_width + spacing + icon_width + spacing + dest_width
                
                # Center the route horizontally
                start_x = max(0, (self.canvas.width - total_width) // 2)
                
                # Calculate exact positions with proper spacing
                orig_x = start_x
                icon_x = orig_x + orig_width + spacing
                dest_x = icon_x + icon_width + spacing
                
                # Draw origin code with brightness from styles.json
                if orig_code:
                    r, g, b = self.route_color_rgb
                    dimmed_r = int(r * self.route_brightness)
                    dimmed_g = int(g * self.route_brightness)
                    dimmed_b = int(b * self.route_brightness)
                    dimmed_route_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
                    graphics.DrawText(self.canvas, self.route_font, orig_x, route_y, dimmed_route_color, orig_code)
                
                # Draw aircraft icon between origin and destination (with pulse + gap)
                if self.aircraft_icon and orig_code and dest_code:
                    # Animation timing (in seconds)
                    fade_down_time = 0.5    # Time to fade from max to min
                    gap_time = 1.0          # Pause at minimum brightness
                    fade_up_time = 0.5      # Time to fade from min to max
                    total_cycle = fade_down_time + gap_time + fade_up_time
                    
                    # Brightness range
                    min_brightness = 0   # 30%
                    max_brightness = 1.0    # 100%
                    
                    # Calculate position in animation cycle
                    cycle_position = current_time % total_cycle
                    
                    if cycle_position < fade_down_time:
                        # Fading down (100% -> 30%)
                        progress = cycle_position / fade_down_time
                        pulse_brightness = max_brightness - (max_brightness - min_brightness) * progress
                    elif cycle_position < fade_down_time + gap_time:
                        # Gap at minimum brightness
                        pulse_brightness = min_brightness
                    else:
                        # Fading up (30% -> 100%)
                        progress = (cycle_position - fade_down_time - gap_time) / fade_up_time
                        pulse_brightness = min_brightness + (max_brightness - min_brightness) * progress
                    
                    # icon_y is pre-calculated to be vertically centered with text
                    self._draw_aircraft_icon(icon_x, icon_y, self.icon_color_rgb, 
                                            brightness=pulse_brightness, 
                                            visible=True)
                elif orig_code and dest_code:
                    # Fallback: draw simple arrow if icon not available (with brightness)
                    r, g, b = self.route_color_rgb
                    dimmed_r = int(r * self.route_brightness)
                    dimmed_g = int(g * self.route_brightness)
                    dimmed_b = int(b * self.route_brightness)
                    dimmed_route_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
                    graphics.DrawText(self.canvas, self.route_font, icon_x, route_y, dimmed_route_color, "->")
                
                # Draw destination code with brightness from styles.json
                if dest_code:
                    r, g, b = self.route_color_rgb
                    dimmed_r = int(r * self.route_brightness)
                    dimmed_g = int(g * self.route_brightness)
                    dimmed_b = int(b * self.route_brightness)
                    dimmed_route_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
                    graphics.DrawText(self.canvas, self.route_font, dest_x, route_y, dimmed_route_color, dest_code)
            else:
                # No route data available - show just "UFO" text (no icon)
                ufo_text = "UFO"
                route_char_width = 7  # Medium font width
                ufo_width = len(ufo_text) * route_char_width
                
                # Center horizontally
                ufo_x = max(0, (self.canvas.width - ufo_width) // 2)
                
                # Draw "UFO" text with brightness from styles.json
                r, g, b = self.route_color_rgb
                dimmed_r = int(r * self.route_brightness)
                dimmed_g = int(g * self.route_brightness)
                dimmed_b = int(b * self.route_brightness)
                dimmed_route_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
                graphics.DrawText(self.canvas, self.route_font, ufo_x, route_y, dimmed_route_color, ufo_text)
            
            # Display city to city on THIRD LINE (if available) - SCROLLING MARQUEE
            origin_city = flight.get("origin_city", "")
            destination_city = flight.get("destination_city", "")
            
            if origin_city and destination_city:
                # Format: "Dubai to Dubai" or "Dubai to London"
                city_country_text = f"{origin_city} to {destination_city}"
                
                # Reset scroll position if text changed
                if city_country_text != self.city_country_text_cache:
                    self.city_country_scroll_position = 0
                    self.city_country_text_cache = city_country_text
                    self.last_scroll_time = time.time()
                
                # Use route city font and style from styles.json
                city_font = self.route_city_font
                city_char_width = self._get_font_char_width(self.route_city_font_size)
                city_width = len(city_country_text) * city_char_width
                canvas_width = self.canvas.width
                
                # Only scroll if text is wider than the canvas
                if city_width > canvas_width:
                    # Update scroll position based on time
                    current_time = time.time()
                    scroll_delta = current_time - self.last_scroll_time
                    self.last_scroll_time = current_time
                    
                    # Move scroll position (pixels per second)
                    self.city_country_scroll_position += self.city_country_scroll_speed * scroll_delta
                    
                    # Calculate when text is completely off-screen to the left
                    # Text starts at canvas_width (right edge) when position = 0
                    # Text is fully off left when position = canvas_width + city_width
                    text_off_screen_position = canvas_width + city_width
                    
                    # Total cycle: text scrolling + gap
                    total_cycle = text_off_screen_position + self.city_country_gap_size
                    
                    # Reset scroll position when it completes a full cycle
                    if self.city_country_scroll_position >= total_cycle:
                        self.city_country_scroll_position = 0
                    
                    # Calculate x position
                    # Position 0: text starts at right edge (x = canvas_width)
                    # Position text_off_screen_position: text fully off left (x = -city_width)
                    # Position total_cycle: gap complete, ready to restart
                    if self.city_country_scroll_position <= text_off_screen_position:
                        # Text is visible or scrolling
                        city_x = int(canvas_width - self.city_country_scroll_position)
                    else:
                        # In gap period - don't draw text (it's off-screen)
                        city_x = -1000  # Way off screen
                else:
                    # Text fits, center it
                    city_x = max(0, (canvas_width - city_width) // 2)
                    # Reset scroll position when text fits
                    self.city_country_scroll_position = 0
                
                # Use route city color and brightness from styles.json (separate from route codes)
                r, g, b = self.route_city_color_rgb
                dimmed_r = int(r * self.route_city_brightness)
                dimmed_g = int(g * self.route_city_brightness)
                dimmed_b = int(b * self.route_city_brightness)
                dimmed_route_city_color = graphics.Color(dimmed_r, dimmed_g, dimmed_b)
                graphics.DrawText(self.canvas, city_font, city_x, city_y, dimmed_route_city_color, city_country_text)
            
            # Debug: Print what fields are available (only once per unique flight)
            if (not origin and not destination) and callsign not in getattr(self, '_debugged_flights', set()):
                if not hasattr(self, '_debugged_flights'):
                    self._debugged_flights = set()
                self._debugged_flights.add(callsign)
                print(f"DEBUG: Flight {callsign} - Route lookup failed")
                print(f"  Origin: '{origin}', Destination: '{destination}'")
                api_name = "Aviation Edge" if self.route_api_provider == "aviation_edge" else "Aerodatabox"
                print(f"  Note: {api_name} API may not support this flight number format (may be private/charter/ferry flight)")
        
        # Always swap the canvas to ensure display updates
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def run(self, display_interval: float = 0.1):
        """
        Run the flight tracker display continuously.
        
        Args:
            display_interval: How often to refresh the display in seconds.
        """
        try:
            # Show initial display immediately (will show last seen flight if available)
            self.display()
            
            # Initial fetch - do it synchronously but update display after
            self.update_flights(force=True)
            self.display()  # Update display after initial fetch
            
            while True:
                self.update_flights()
                self.display()
                time.sleep(display_interval)
        except KeyboardInterrupt:
            self.clear()
    
    def clear(self):
        """Clear the display."""
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


def run():
    """Run the flight tracker display as a standalone module."""
    config = load_config()
    tracker = FlightTracker(config=config)
    tracker.run()


if __name__ == "__main__":
    run()

