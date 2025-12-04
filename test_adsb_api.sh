#!/bin/bash
echo "Testing ADSB Exchange API..."
echo ""

# Test the API and show full response
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "https://public-api.adsbexchange.com/VirtualRadar/AircraftList.json?lat=25.2048&lon=55.2708&fDstL=0&fDstU=40")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

echo "HTTP Status: $HTTP_CODE"
echo ""
echo "Response body (first 500 chars):"
echo "$BODY" | head -c 500
echo ""
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    echo "Trying to parse JSON..."
    echo "$BODY" | python3 -m json.tool 2>&1 | head -20
else
    echo "API returned error status: $HTTP_CODE"
fi

