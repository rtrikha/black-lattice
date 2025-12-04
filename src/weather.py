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


class Weather:
    """Fetches and displays weather data on the LED matrix."""
    
    API_URL = "https://api.openweathermap.org/data/2.5/weather"
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the Weather display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        weather_config = self.config.get("weather", {})
        self.api_key = weather_config.get("api_key", "")
        self.city = weather_config.get("city", "New York")
        self.units = weather_config.get("units", "metric")
        self.update_interval = weather_config.get("update_interval_seconds", 600)
        self.color = create_graphics_color(weather_config.get("color", {"r": 255, "g": 200, "b": 0}))
        
        # Load fonts
        self.main_font = load_font("7x13.bdf")
        self.small_font = load_font("5x7.bdf")
        
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
            graphics.DrawText(self.canvas, self.small_font, 2, 16, self.color, msg)
        else:
            # Display temperature prominently
            temp_str = self.get_temperature()
            graphics.DrawText(self.canvas, self.main_font, 2, 12, self.color, temp_str)
            
            # Display condition
            condition = self.get_condition()
            graphics.DrawText(self.canvas, self.small_font, 2, 22, self.color, condition)
            
            # Display city name (truncated if needed)
            city_display = self.city[:10] if len(self.city) > 10 else self.city
            graphics.DrawText(self.canvas, self.small_font, 2, 30, self.color, city_display)
        
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

