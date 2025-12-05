#!/bin/bash
# Test script for Aviation Edge API
# Usage: ./test_aviation_edge.sh YOUR_API_KEY

API_KEY="${1:-YOUR_API_KEY_HERE}"

if [ "$API_KEY" == "YOUR_API_KEY_HERE" ]; then
    echo "Usage: $0 YOUR_API_KEY"
    echo ""
    echo "Get your API key from: https://aviation-edge.com/premium-api/"
    exit 1
fi

echo "Testing Aviation Edge API..."
echo "================================"
echo ""

# Test 1: Routes endpoint for a specific flight
echo "1. Testing Routes endpoint for EK215:"
echo "-----------------------------------"
curl -s "https://aviation-edge.com/v2/public/routes?key=${API_KEY}&flight_iata=EK215" | python3 -m json.tool | head -80
echo ""
echo ""

# Test 2: Schedules endpoint for a specific flight
echo "2. Testing Schedules endpoint for EK215:"
echo "-----------------------------------"
curl -s "https://aviation-edge.com/v2/public/schedules?key=${API_KEY}&flight_iata=EK215" | python3 -m json.tool | head -80
echo ""
echo ""

# Test 3: Routes by airline (Emirates)
echo "3. Testing Routes by airline (EK):"
echo "-----------------------------------"
curl -s "https://aviation-edge.com/v2/public/routes?key=${API_KEY}&airline_iata=EK" | python3 -m json.tool | head -100
echo ""
echo ""

# Test 4: Airport database for DXB
echo "4. Testing Airport database for DXB:"
echo "-----------------------------------"
curl -s "https://aviation-edge.com/v2/public/airportDatabase?key=${API_KEY}&codeIataAirport=DXB" | python3 -m json.tool | head -50
echo ""
echo ""

echo "================================"
echo "Test complete!"
echo ""
echo "Review the responses above to see if the data format and content meet your needs."





