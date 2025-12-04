#!/bin/bash
# Test script for flight tracking APIs
# Coordinates: Dubai (25.2048, 55.2708), Radius: 25km

echo "=== Testing OpenSky Network API ==="
echo ""

# First, let's see the raw response
echo "Raw API Response:"
curl -s -w "\nHTTP Status: %{http_code}\n" -H "User-Agent: FlightTracker/1.0 (https://github.com/openskynetwork/opensky-api)" \
  "https://opensky-network.org/api/states/all?lamin=24.9796&lamax=25.4300&lomin=55.0219&lomax=55.5197" \
  | head -20

echo ""
echo "=== Parsed JSON (if valid) ==="
echo ""

# Try to parse JSON
RESPONSE=$(curl -s -H "User-Agent: FlightTracker/1.0 (https://github.com/openskynetwork/opensky-api)" \
  "https://opensky-network.org/api/states/all?lamin=24.9796&lamax=25.4300&lomin=55.0219&lomax=55.5197")

if [ -z "$RESPONSE" ]; then
    echo "ERROR: Empty response from API"
elif echo "$RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "$RESPONSE" | python3 -m json.tool | head -50
else
    echo "ERROR: Invalid JSON response"
    echo "Response content:"
    echo "$RESPONSE" | head -10
fi

echo ""
echo "=== Extracting flight callsigns ==="
echo ""

# Extract just the callsigns (flight numbers) from the response
RESPONSE=$(curl -s -H "User-Agent: FlightTracker/1.0 (https://github.com/openskynetwork/opensky-api)" \
  "https://opensky-network.org/api/states/all?lamin=24.9796&lamax=25.4300&lomin=55.0219&lomax=55.5197")

echo "$RESPONSE" | python3 -c "
import json
import sys
try:
    response_text = sys.stdin.read()
    if not response_text or response_text.strip() == '':
        print('ERROR: Empty response from API')
        sys.exit(1)
    
    data = json.loads(response_text)
    if 'states' in data and data['states']:
        print('Flights found:')
        count = 0
        for state in data['states']:
            if state and len(state) > 1:
                callsign = state[1]
                on_ground = state[8] if len(state) > 8 else True
                if callsign and callsign.strip() and not on_ground:
                    lat = state[6] if len(state) > 6 else 'N/A'
                    lon = state[5] if len(state) > 5 else 'N/A'
                    alt = state[7] if len(state) > 7 else 'N/A'
                    print(f'  {callsign.strip():<10} | Lat: {lat:>8} | Lon: {lon:>8} | Alt: {alt:>6}m')
                    count += 1
        if count == 0:
            print('No flights in air found (all aircraft are on ground)')
    elif 'states' in data:
        print('No flights found in area')
    else:
        print('Unexpected response format:')
        print(json.dumps(data, indent=2)[:500])
except json.JSONDecodeError as e:
    print(f'ERROR: Invalid JSON - {e}')
    print('Response was:')
    print(response_text[:200])
except Exception as e:
    print(f'ERROR: {e}')
"

echo ""
echo "=== Last flight that crossed (most recent) ==="
echo ""

# Get the most recent flight
RESPONSE=$(curl -s -H "User-Agent: FlightTracker/1.0 (https://github.com/openskynetwork/opensky-api)" \
  "https://opensky-network.org/api/states/all?lamin=24.9796&lamax=25.4300&lomin=55.0219&lomax=55.5197")

echo "$RESPONSE" | python3 -c "
import json
import sys
try:
    response_text = sys.stdin.read()
    if not response_text or response_text.strip() == '':
        print('ERROR: Empty response from API')
        sys.exit(1)
    
    data = json.loads(response_text)
    if 'states' in data and data['states']:
        flights = []
        for state in data['states']:
            if state and len(state) > 1:
                callsign = state[1]
                on_ground = state[8] if len(state) > 8 else True
                if callsign and callsign.strip() and not on_ground:
                    last_contact = state[4] if len(state) > 4 else 0
                    flights.append({
                        'callsign': callsign.strip(),
                        'last_contact': last_contact,
                        'lat': state[6] if len(state) > 6 else None,
                        'lon': state[5] if len(state) > 5 else None,
                        'alt': state[7] if len(state) > 7 else None
                    })
        if flights:
            # Sort by last_contact (most recent first)
            flights.sort(key=lambda x: x['last_contact'], reverse=True)
            latest = flights[0]
            print(f\"Flight: {latest['callsign']}\")
            print(f\"Last seen: {latest['last_contact']} seconds ago\")
            print(f\"Position: Lat {latest['lat']}, Lon {latest['lon']}\")
            print(f\"Altitude: {latest['alt']}m\")
        else:
            print('No flights in air found')
    else:
        print('No data returned from API')
except json.JSONDecodeError as e:
    print(f'ERROR: Invalid JSON - {e}')
except Exception as e:
    print(f'ERROR: {e}')
"

