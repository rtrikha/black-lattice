#!/usr/bin/env python3
"""Test color parsing for #B54300"""

hex_color = "#B54300"
hex_color = hex_color.lstrip("#")
r = int(hex_color[0:2], 16)
g = int(hex_color[2:4], 16)
b = int(hex_color[4:6], 16)

print(f"Hex: #B54300")
print(f"RGB: ({r}, {g}, {b})")
print(f"Expected: Orange/Brown color")
print(f"RGB(181, 67, 0) should be orange-brown, not crimson")

# Test with the actual parsing function
import sys
sys.path.insert(0, 'src')
from utils import hex_to_rgb, parse_color

parsed = hex_to_rgb("#B54300")
print(f"\nParsed RGB: {parsed}")

parsed2 = parse_color("#B54300")
print(f"Parse color result: {parsed2}")

