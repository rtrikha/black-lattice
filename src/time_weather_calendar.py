"""
Time Weather Calendar composite UI module for LED matrix display.
Combines time, date, calendar info, weather icon, and temperature in a 2-column grid layout.
"""

import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image
from rgbmatrix import RGBMatrix

from utils import (
    load_config,
    create_matrix,
    get_text_width,
    create_graphics_color,
    get_project_root,
)
from layout import LayoutEngine, Element
from style_parser import create_style_manager


class TimeWeatherCalendar:
    """Composite UI displaying time, date, calendar, weather icon, and temperature."""
    
    API_URL = "https://api.openweathermap.org/data/2.5/weather"
    
    # Weather condition to icon file mapping (supports both .svg and .png)
    WEATHER_ICONS = {
        "Clear": "sun",
        "Clouds": "cloud",
        "Rain": "rain",
        "Drizzle": "rain",
        "Thunderstorm": "thunderstorm",
        "Snow": "snow",
        "Mist": "cloud",
        "Fog": "cloud",
        "Haze": "cloud",
        "Dust": "cloud",
        "Sand": "cloud",
        "Ash": "cloud",
        "Squall": "rain",
        "Tornado": "thunderstorm",
    }
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the TimeWeatherCalendar display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        
        # Initialize layout engine with CSS-like styling
        self.layout = LayoutEngine(self.matrix)
        
        # Clock configuration
        clock_config = self.config.get("time_weather_calendar", {}).get("clock", {})
        if not clock_config:
            # Fallback to main clock config
            clock_config = self.config.get("clock", {})
        self.format_24h = clock_config.get("format_24h", False)
        self.show_seconds = clock_config.get("show_seconds", False)
        
        # Weather configuration
        weather_config = self.config.get("time_weather_calendar", {}).get("weather", {})
        if not weather_config:
            # Fallback to main weather config
            weather_config = self.config.get("weather", {})
        self.api_key = weather_config.get("api_key", "")
        self.city = weather_config.get("city", "New York")
        self.units = weather_config.get("units", "metric")
        self.update_interval = weather_config.get("update_interval_seconds", 600)
        
        # Cached weather data
        self.weather_data = None
        self.last_update = 0
    
    def get_time_string(self) -> str:
        """Get formatted time string based on config."""
        now = datetime.now()
        
        if self.format_24h:
            # 24-hour format
            return now.strftime("%H:%M")
        else:
            # 12-hour format
            return now.strftime("%I:%M")
    
    def get_date_with_calendar(self) -> str:
        """Get date string with day of week."""
        now = datetime.now()
        # Format: "Thu 4 Dec"
        return now.strftime("%a %-d %b")
    
    def fetch_weather(self) -> dict:
        """
        Fetch weather data from OpenWeatherMap API.
        
        Returns:
            Weather data dictionary or None if failed.
        """
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            return None
        
        try:
            params = {
                "q": self.city,
                "appid": self.api_key,
                "units": self.units,
            }
            response = requests.get(self.API_URL, params=params, timeout=10)
            
            # Check for 401 specifically before raising
            if response.status_code == 401:
                print(f"Error: Invalid or unactivated API key.")
                print(f"Please verify:")
                print(f"  1. The API key is correct: {self.api_key[:8]}...")
                print(f"  2. You've verified your email on OpenWeatherMap")
                print(f"  3. The API key is activated (may take a few hours after signup)")
                print(f"Get a free API key at: https://openweathermap.org/api")
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            print(f"Error fetching weather: {e}")
            return None
        except requests.RequestException as e:
            print(f"Error fetching weather: {e}")
            return None
    
    def update_weather(self, force: bool = False):
        """
        Update weather data if needed.
        
        Args:
            force: Force update even if cache is fresh.
        """
        current_time = time.time()
        if force or (current_time - self.last_update) >= self.update_interval:
            data = self.fetch_weather()
            if data:
                self.weather_data = data
                self.last_update = current_time
    
    def get_weather_condition(self) -> str:
        """Get weather condition name."""
        if not self.weather_data:
            return None
        
        weather_list = self.weather_data.get("weather", [])
        if not weather_list:
            return None
        
        return weather_list[0].get("main", "Unknown")
    
    def draw_weather_icon(self, canvas, x, y, condition):
        """Draw weather icon image based on condition."""
        icon_filename = self.WEATHER_ICONS.get(condition)
        if not icon_filename:
            return  # No icon for this condition
        
        # Look for icon in assets/images/icons/ directory
        # Try both .svg and .png extensions
        project_root = get_project_root()
        icon_base = project_root / "assets" / "images" / "icons" / icon_filename
        
        # Try SVG first, then PNG
        icon_path = None
        for ext in ['.svg', '.png']:
            test_path = icon_base.with_suffix(ext)
            if test_path.exists():
                icon_path = test_path
                break
        
        # Fallback to assets/images/ if icons subdirectory doesn't exist
        if not icon_path:
            icon_base = project_root / "assets" / "images" / icon_filename
            for ext in ['.svg', '.png']:
                test_path = icon_base.with_suffix(ext)
                if test_path.exists():
                    icon_path = test_path
                    break
        
        if not icon_path or not icon_path.exists():
            print(f"Warning: Weather icon not found: {icon_filename}.svg or {icon_filename}.png")
            print(f"  Searched in: {project_root / 'assets' / 'images' / 'icons'}")
            print(f"  Condition: {condition}")
            return
        
        try:
            # Load and resize icon (target size: 10x10 pixels)
            icon_size = 10
            img = None
            
            # Handle SVG files
            if icon_path.suffix.lower() == '.svg':
                try:
                    # Try using cairosvg if available
                    import cairosvg
                    # Convert SVG to PNG in memory
                    png_data = cairosvg.svg2png(url=str(icon_path), output_width=icon_size, output_height=icon_size)
                    from io import BytesIO
                    img = Image.open(BytesIO(png_data))
                    img = img.convert("RGB")
                except ImportError:
                    # Fallback: try svglib
                    try:
                        from svglib.svglib import svg2rlg
                        from reportlab.graphics import renderPM
                        drawing = svg2rlg(str(icon_path))
                        if drawing:
                            # Render to PNG in memory
                            from io import BytesIO
                            png_data = renderPM.drawToString(drawing, fmt='PNG', dpi=72)
                            img = Image.open(BytesIO(png_data))
                            img = img.convert("RGB")
                            img = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                        else:
                            print(f"Warning: Could not parse SVG: {icon_path}")
                            return
                    except ImportError:
                        print(f"Warning: SVG support requires 'cairosvg' or 'svglib'. Install with: pip install cairosvg")
                        print(f"  Or convert {icon_path} to PNG format")
                        return
            else:
                # Handle regular image formats (PNG, JPG, etc.)
                img = Image.open(icon_path)
                img = img.convert("RGB")
            
            # Resize to target size
            img = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
            
            # Draw icon on canvas at specified position
            # Handle images with transparency/alpha channel
            pixels_drawn = 0
            for py in range(icon_size):
                for px in range(icon_size):
                    pixel_x = x + px
                    pixel_y = y + py
                    # Only draw if within canvas bounds
                    if 0 <= pixel_x < self.layout.width and 0 <= pixel_y < self.layout.height:
                        try:
                            # Handle RGBA images (with alpha channel)
                            pixel = img.getpixel((px, py))
                            if len(pixel) == 4:  # RGBA
                                r, g, b, a = pixel
                                # Skip fully transparent pixels
                                if a < 50:  # Lower threshold to allow more pixels
                                    continue
                            else:  # RGB
                                r, g, b = pixel
                            
                            # Draw the pixel - don't skip based on color
                            # The threshold was too aggressive
                            canvas.SetPixel(pixel_x, pixel_y, r, g, b)
                            pixels_drawn += 1
                        except Exception as e:
                            # Skip this pixel if there's an error
                            pass
            
            # Debug: print if no pixels were drawn
            if pixels_drawn == 0:
                print(f"Warning: No pixels drawn for icon at ({x}, {y}). Image might be all transparent/black.")
                # Try drawing a test pixel to verify position
                if 0 <= x < self.layout.width and 0 <= y < self.layout.height:
                    canvas.SetPixel(x, y, 255, 255, 0)  # Yellow test pixel
                    print(f"Drew test pixel at ({x}, {y})")
        except Exception as e:
            print(f"Error loading weather icon {icon_filename}: {e}")
    
    def get_temperature(self) -> str:
        """Get formatted temperature string."""
        if not self.weather_data:
            return "--"
        
        temp = self.weather_data.get("main", {}).get("temp", 0)
        unit = "c" if self.units == "metric" else "f"
        return f"{int(temp)}{unit}"
    
    def display(self):
        """Display the composite UI vertically stacked and center-aligned."""
        # Update weather if needed
        self.update_weather()
        
        # Get all display strings
        time_str = self.get_time_string()
        date_str = self.get_date_with_calendar()
        temp_str = self.get_temperature()
        weather_condition = self.get_weather_condition()
        
        # Create separate elements for each line, all center-aligned
        # We'll position them manually to stack vertically
        elements = [
            Element(
                text=time_str,
                classes=["time-weather-time"],
                style_overrides={"gravity": "center"}
            ),
            Element(
                text=date_str,
                classes=["time-weather-date"],
                style_overrides={"gravity": "center"}
            ),
            Element(
                text=temp_str,
                classes=["time-weather-temp"],
                style_overrides={"gravity": "center"}
            ),
        ]
        
        # Calculate vertical positions to stack them with consistent spacing
        # Get font heights for each element
        font_heights = []
        for element in elements:
            style = self.layout.style_manager.resolve_style(classes=element.classes, overrides=element.style_overrides)
            if style.font_size == "xs":
                font_heights.append(6)
            elif style.font_size == "small":
                font_heights.append(7)
            elif style.font_size == "large":
                font_heights.append(13)
            else:  # medium or default
                font_heights.append(13)
        
        # Calculate consistent gap between lines (space between bottom of one line and top of next)
        gap_between_lines = 2  # Consistent gap in pixels (reduce this to make lines closer)
        
        # Calculate total height needed
        total_height = sum(font_heights) + (gap_between_lines * (len(elements) - 1))
        
        # Calculate starting Y position (center the block vertically)
        start_y = (self.layout.height - total_height) // 2
        
        # Ensure minimum top margin (at least 2 pixels from top)
        min_top_margin = 2
        if start_y < min_top_margin:
            start_y = min_top_margin
        
        # Position each element manually with consistent spacing
        current_y = start_y
        for i, element in enumerate(elements):
            style = self.layout.style_manager.resolve_style(classes=element.classes, overrides=element.style_overrides)
            text_width = get_text_width(style.font, element.text)
            
            # Special handling for temperature (3rd element, index 2) - need to account for icon
            if i == 2 and weather_condition:  # Temperature element
                icon_size = 10
                gap = 2
                # Calculate total width of icon + gap + text
                total_width = icon_size + gap + text_width
                start_x = (self.layout.width - total_width) // 2
                # Temperature text goes after the icon
                x = start_x + icon_size + gap
            else:
                # Center other elements normally
                x = (self.layout.width - text_width) // 2
            
            # Y position is at the baseline (bottom of text)
            y = current_y + font_heights[i]
            element.x = x
            element.y = y
            
            # Move to next line: current position + font height + gap
            current_y = y + gap_between_lines
        
        # Render text elements first (but don't swap yet - we need to add the icon)
        # We'll manually render to canvas so we can add the icon before swapping
        self.layout.canvas.Clear()
        
        # Render each text element
        for element in elements:
            self.layout.render_element(element)
        
        # Draw weather icon next to temperature (on the same line - 3rd element)
        if weather_condition:
            # Get the temperature element position (last element, index 2)
            temp_element = elements[2]  # Temperature is the 3rd element (index 2)
            temp_style = self.layout.style_manager.resolve_style(
                classes=temp_element.classes,
                overrides=temp_element.style_overrides
            )
            temp_width = get_text_width(temp_style.font, temp_element.text)
            
            # Calculate icon position: to the left of temperature, on the same line
            icon_size = 10  # Icon size
            gap = 2  # Gap between icon and temperature text
            
            # Center the icon+text combination horizontally (same calculation as above)
            total_width = icon_size + gap + temp_width
            start_x = (self.layout.width - total_width) // 2
            icon_x = start_x
            
            # Align icon vertically with temperature text
            # temp_element.y is the baseline of the text (bottom of text)
            # For small font (7px height), text center is around baseline - 3 or 4
            # Icon center should align with text center
            # Icon is 10px tall, so center is at icon_y + 5
            # Text center is at temp_element.y - 3.5 (half of 7px font)
            # So: icon_y + 5 = temp_element.y - 3.5
            # Therefore: icon_y = temp_element.y - 8.5 ≈ temp_element.y - 8
            icon_y = temp_element.y - 8  # Align icon center with text center
            
            # Draw the icon on the canvas (icon images have their own colors)
            self.draw_weather_icon(
                self.layout.canvas,
                icon_x,
                icon_y,
                weather_condition
            )
        
        # Swap canvas to display
        self.layout.canvas = self.matrix.SwapOnVSync(self.layout.canvas)
    
    def run(self, update_interval: float = 0.5):
        """
        Run the display continuously.
        
        Args:
            update_interval: How often to refresh the display in seconds.
        """
        # Initial weather fetch
        self.update_weather(force=True)
        
        try:
            while True:
                self.display()
                time.sleep(update_interval)
        except KeyboardInterrupt:
            self.clear()
    
    def clear(self):
        """Clear the display."""
        self.layout.clear()


def run():
    """Run the time_weather_calendar as a standalone module."""
    config = load_config()
    display = TimeWeatherCalendar(config=config)
    display.run()


if __name__ == "__main__":
    run()

