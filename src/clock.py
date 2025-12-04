"""
Clock module for LED matrix display.
Displays current time and optionally date.
"""

import time
from datetime import datetime

from rgbmatrix import RGBMatrix, graphics

from utils import (
    load_config,
    create_matrix,
    create_graphics_color,
    load_font,
)


class Clock:
    """Displays current time on the LED matrix."""
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the Clock display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        clock_config = self.config.get("clock", {})
        self.format_24h = clock_config.get("format_24h", False)
        self.show_seconds = clock_config.get("show_seconds", True)
        self.show_date = clock_config.get("show_date", True)
        self.color = create_graphics_color(clock_config.get("color", {"r": 0, "g": 255, "b": 128}))
        
        # Load fonts - use a larger font for time, smaller for date
        self.time_font = load_font("7x13.bdf")
        self.date_font = load_font("5x7.bdf")
    
    def get_time_string(self) -> str:
        """Get formatted time string based on config."""
        now = datetime.now()
        
        if self.format_24h:
            if self.show_seconds:
                return now.strftime("%H:%M:%S")
            else:
                return now.strftime("%H:%M")
        else:
            if self.show_seconds:
                return now.strftime("%I:%M:%S %p")
            else:
                return now.strftime("%I:%M %p")
    
    def get_date_string(self) -> str:
        """Get formatted date string."""
        now = datetime.now()
        return now.strftime("%b %d, %Y")
    
    def display(self):
        """Display the current time (and date if enabled)."""
        self.canvas.Clear()
        
        time_str = self.get_time_string()
        
        if self.show_date:
            # Time on top, date on bottom
            date_str = self.get_date_string()
            
            # Draw time centered at top
            time_x = max(0, (self.matrix.width - len(time_str) * 7) // 2)
            graphics.DrawText(self.canvas, self.time_font, time_x, 12, self.color, time_str)
            
            # Draw date centered at bottom
            date_x = max(0, (self.matrix.width - len(date_str) * 5) // 2)
            graphics.DrawText(self.canvas, self.date_font, date_x, 28, self.color, date_str)
        else:
            # Center time vertically
            time_x = max(0, (self.matrix.width - len(time_str) * 7) // 2)
            y_pos = (self.matrix.height // 2) + 5
            graphics.DrawText(self.canvas, self.time_font, time_x, y_pos, self.color, time_str)
        
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def run(self, update_interval: float = 0.5):
        """
        Run the clock display continuously.
        
        Args:
            update_interval: How often to refresh the display in seconds.
        """
        try:
            while True:
                self.display()
                time.sleep(update_interval)
        except KeyboardInterrupt:
            self.clear()
    
    def clear(self):
        """Clear the display."""
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


def run():
    """Run the clock as a standalone module."""
    config = load_config()
    clock = Clock(config=config)
    clock.run()


if __name__ == "__main__":
    run()

