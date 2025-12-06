"""
Weather module for LED matrix display.
Fetches weather data from OpenWeatherMap API and displays it.
"""

import time
from datetime import datetime

import requests
from rgbmatrix import RGBMatrix, graphics

from utils import (
    load_config,
    create_matrix,
    create_graphics_color,
    load_font,
)
from style_parser import create_style_manager


class Weather:
    """Fetches and displays weather data on the LED matrix."""
    
    API_URL = "https://api.openweathermap.org/data/2.5/weather"
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None, style_manager=None):
        """
        Initialize the Weather display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
            style_manager: Optional StyleManager instance (should be created BEFORE matrix).
        """
        self.config = config or load_config()
        self.style_manager = style_manager or create_style_manager()
        self.matrix = matrix or create_matrix(self.config)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        weather_config = self.config.get("weather", {})
        self.api_key = weather_config.get("api_key", "")
        self.city = weather_config.get("city", "New York")
        self.units = weather_config.get("units", "metric")
        self.update_interval = weather_config.get("update_interval_seconds", 600)
        
        # Use stylesheet classes for styling (from styles.json)
        self.temp_style = self.style_manager.resolve_style(classes=["weather-temp"])
        self.condition_style = self.style_manager.resolve_style(classes=["weather-condition"])
        
        # Fonts and colors from resolved styles
        self.main_font = self.temp_style.font
        self.small_font = self.condition_style.font
        self.temp_color = self.temp_style.color
        self.condition_color = self.condition_style.color
        
        # Cached weather data
        self.weather_data = None
        self.last_update = 0
    
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
            response.raise_for_status()
            return response.json()
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
    
    def get_temperature(self) -> str:
        """Get formatted temperature string."""
        if not self.weather_data:
            return "--"
        
        temp = self.weather_data.get("main", {}).get("temp", 0)
        unit = "C" if self.units == "metric" else "F"
        return f"{temp:.0f}{unit}"
    
    def get_condition(self) -> str:
        """Get weather condition description."""
        if not self.weather_data:
            return "No data"
        
        weather_list = self.weather_data.get("weather", [])
        if weather_list:
            return weather_list[0].get("main", "Unknown")
        return "Unknown"
    
    def get_humidity(self) -> str:
        """Get humidity percentage."""
        if not self.weather_data:
            return "--%"
        
        humidity = self.weather_data.get("main", {}).get("humidity", 0)
        return f"{humidity}%"
    
    def display(self):
        """Display weather information."""
        self.canvas.Clear()
        
        if not self.weather_data:
            # Show placeholder or error message
            if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
                msg = "Set API key"
            else:
                msg = "Loading..."
            graphics.DrawText(self.canvas, self.small_font, 2, 16, self.condition_color, msg)
        else:
            # Display temperature prominently (uses .weather-temp style)
            temp_str = self.get_temperature()
            graphics.DrawText(self.canvas, self.main_font, 2, 12, self.temp_color, temp_str)
            
            # Display condition (uses .weather-condition style)
            condition = self.get_condition()
            graphics.DrawText(self.canvas, self.small_font, 2, 22, self.condition_color, condition)
            
            # Display city name (truncated if needed)
            city_display = self.city[:10] if len(self.city) > 10 else self.city
            graphics.DrawText(self.canvas, self.small_font, 2, 30, self.condition_color, city_display)
        
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def run(self, display_interval: float = 1.0):
        """
        Run the weather display continuously.
        
        Args:
            display_interval: How often to refresh the display in seconds.
        """
        try:
            # Initial fetch
            self.update_weather(force=True)
            
            while True:
                self.update_weather()
                self.display()
                time.sleep(display_interval)
        except KeyboardInterrupt:
            self.clear()
    
    def clear(self):
        """Clear the display."""
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


def run():
    """Run the weather display as a standalone module."""
    config = load_config()
    weather = Weather(config=config)
    weather.run()


if __name__ == "__main__":
    run()

