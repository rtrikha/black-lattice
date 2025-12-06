"""
Clock module for LED matrix display.
Displays current time and optionally date.
Uses CSS-like styling system with class-based targeting.
"""

import time
from datetime import datetime

from rgbmatrix import RGBMatrix

from utils import (
    load_config,
    create_matrix,
)
from layout import LayoutEngine, Element


class Clock:
    """Displays current time on the LED matrix using CSS-like styling."""
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None, style_manager=None):
        """
        Initialize the Clock display.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
            style_manager: Optional StyleManager instance (should be created BEFORE matrix).
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        
        # Initialize layout engine with CSS-like styling
        # Pass the pre-created style_manager if available
        self.layout = LayoutEngine(self.matrix, style_manager=style_manager)
        
        clock_config = self.config.get("clock", {})
        self.format_24h = clock_config.get("format_24h", False)
        self.show_seconds = clock_config.get("show_seconds", True)
        self.show_date = clock_config.get("show_date", True)
    
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
        """Display the current time (and date if enabled) using CSS-like styling."""
        time_str = self.get_time_string()
        
        # Create elements with CSS-like classes
        # These classes match rules in config/styles.json
        elements = []
        
        if self.show_date:
            # Time element with class "time-display" (matches .time-display in stylesheet)
            time_element = Element(
                text=time_str,
                classes=["time-display"]
            )
            elements.append(time_element)
            
            # Date element with class "date-display" (matches .date-display in stylesheet)
            date_str = self.get_date_string()
            date_element = Element(
                text=date_str,
                classes=["date-display"]
            )
            elements.append(date_element)
        else:
            # Just time, centered
            time_element = Element(
                text=time_str,
                classes=["time-display"],
                style_overrides={"gravity": "center"}  # Override to center vertically
            )
            elements.append(time_element)
        
        # Render all elements using the layout engine
        # The layout engine will apply styles from stylesheet based on classes
        self.layout.render(elements)
    
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
        self.layout.clear()


def run():
    """Run the clock as a standalone module."""
    config = load_config()
    clock = Clock(config=config)
    clock.run()


if __name__ == "__main__":
    run()

