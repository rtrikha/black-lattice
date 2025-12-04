#!/usr/bin/env python3
"""
LED Matrix Display - Main Entry Point

Usage:
    sudo python3 main.py --mode text --message "Hello World"
    sudo python3 main.py --mode clock
    sudo python3 main.py --mode weather
    sudo python3 main.py --mode time_weather_calendar
    sudo python3 main.py --mode flight_tracker
"""

import argparse
import sys

from utils import load_config, create_matrix
from text_scroller import TextScroller
from clock import Clock
from weather import Weather
from time_weather_calendar import TimeWeatherCalendar
from flight_tracker import FlightTracker


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LED Matrix Display Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 main.py --mode text --message "Hello World"
  sudo python3 main.py --mode text --message "Scrolling!" --scroll
  sudo python3 main.py --mode clock
  sudo python3 main.py --mode weather
  sudo python3 main.py --mode time_weather_calendar
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["text", "clock", "weather", "time_weather_calendar", "flight_tracker"],
        default="text",
        help="Display mode (default: text)"
    )
    
    parser.add_argument(
        "--message", "-t",
        type=str,
        default=None,
        help="Text message to display (for text mode)"
    )
    
    parser.add_argument(
        "--scroll", "-s",
        action="store_true",
        default=True,
        help="Enable scrolling for text mode (default: enabled)"
    )
    
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        help="Disable scrolling for text mode (static display)"
    )
    
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        help="Scroll speed in seconds per pixel (lower = faster)"
    )
    
    parser.add_argument(
        "--brightness", "-b",
        type=int,
        default=None,
        help="Override display brightness (0-100)"
    )
    
    return parser.parse_args()


def run_text_mode(args, config, matrix):
    """Run text display mode."""
    scroller = TextScroller(matrix=matrix, config=config)
    
    # Get message from args or config
    message = args.message
    if message is None:
        message = config.get("text_scroller", {}).get("default_text", "Hello World!")
    
    # Determine scroll vs static
    scroll = args.scroll and not args.no_scroll
    
    print(f"Displaying text: {message}")
    print(f"Mode: {'scrolling' if scroll else 'static'}")
    print("Press Ctrl+C to exit")
    
    try:
        if scroll:
            scroller.scroll(message, speed=args.speed)
        else:
            scroller.display_static(message)
            # Keep display on until interrupted
            import time
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        scroller.clear()


def run_clock_mode(args, config, matrix):
    """Run clock display mode."""
    clock = Clock(matrix=matrix, config=config)
    
    print("Displaying clock")
    print("Press Ctrl+C to exit")
    
    try:
        clock.run()
    except KeyboardInterrupt:
        pass
    finally:
        clock.clear()


def run_weather_mode(args, config, matrix):
    """Run weather display mode."""
    weather_config = config.get("weather", {})
    api_key = weather_config.get("api_key", "")
    
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("Warning: No API key configured!")
        print("Edit config/settings.json and add your OpenWeatherMap API key")
        print("Get a free key at: https://openweathermap.org/api")
    
    weather = Weather(matrix=matrix, config=config)
    
    city = weather_config.get("city", "Unknown")
    print(f"Displaying weather for: {city}")
    print("Press Ctrl+C to exit")
    
    try:
        weather.run()
    except KeyboardInterrupt:
        pass
    finally:
        weather.clear()


def run_time_weather_calendar_mode(args, config, matrix):
    """Run time_weather_calendar composite display mode."""
    # Check for API key in time_weather_calendar config or fallback to weather config
    twc_config = config.get("time_weather_calendar", {})
    weather_config = twc_config.get("weather", {}) if twc_config else {}
    if not weather_config:
        weather_config = config.get("weather", {})
    
    api_key = weather_config.get("api_key", "")
    
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("Warning: No API key configured!")
        print("Edit config/settings.json and add your OpenWeatherMap API key")
        print("Get a free key at: https://openweathermap.org/api")
    
    display = TimeWeatherCalendar(matrix=matrix, config=config)
    
    city = weather_config.get("city", "Unknown")
    print(f"Displaying time, weather, and calendar for: {city}")
    print("Press Ctrl+C to exit")
    
    try:
        display.run()
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_flight_tracker_mode(args, config, matrix):
    """Run flight tracker display mode."""
    flight_config = config.get("flight_tracker", {})
    latitude = flight_config.get("latitude", 0.0)
    longitude = flight_config.get("longitude", 0.0)
    radius_km = flight_config.get("radius_km", 25)
    
    if latitude == 0.0 and longitude == 0.0:
        print("Warning: No coordinates configured!")
        print("Edit config/settings.json and add your latitude and longitude")
        print("Example: \"latitude\": 25.2048, \"longitude\": 55.2708")
    
    tracker = FlightTracker(matrix=matrix, config=config)
    
    print(f"Tracking flights within {radius_km}km of ({latitude}, {longitude})")
    print("Press Ctrl+C to exit")
    
    try:
        tracker.run()
    except KeyboardInterrupt:
        pass
    finally:
        tracker.clear()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError:
        print("Error: config/settings.json not found!")
        print("Make sure you're running from the project root directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Override brightness if specified
    if args.brightness is not None:
        config.setdefault("matrix", {})["brightness"] = max(0, min(100, args.brightness))
    
    # Create matrix
    try:
        matrix = create_matrix(config)
    except Exception as e:
        print(f"Error initializing matrix: {e}")
        print("Make sure you're running with sudo and the hardware is connected.")
        sys.exit(1)
    
    # Run the appropriate mode
    try:
        if args.mode == "text":
            run_text_mode(args, config, matrix)
        elif args.mode == "clock":
            run_clock_mode(args, config, matrix)
        elif args.mode == "weather":
            run_weather_mode(args, config, matrix)
        elif args.mode == "time_weather_calendar":
            run_time_weather_calendar_mode(args, config, matrix)
        elif args.mode == "flight_tracker":
            run_flight_tracker_mode(args, config, matrix)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("\nDisplay stopped.")


if __name__ == "__main__":
    main()

