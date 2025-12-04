#!/usr/bin/env python3
"""
LED Matrix Display - Main Entry Point

Usage:
    sudo python3 main.py --mode text --message "Hello World"
    sudo python3 main.py --mode clock
    sudo python3 main.py --mode weather
"""

import argparse
import sys

from utils import load_config, create_matrix
from text_scroller import TextScroller
from clock import Clock
from weather import Weather


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
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["text", "clock", "weather"],
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
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("\nDisplay stopped.")


if __name__ == "__main__":
    main()

