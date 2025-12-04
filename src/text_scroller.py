"""
Text scroller module for LED matrix display.
Provides scrolling and static text display functionality.
"""

import time

from rgbmatrix import RGBMatrix, graphics

from utils import (
    load_config,
    create_matrix,
    create_graphics_color,
    load_font,
    get_text_width,
)


class TextScroller:
    """Handles scrolling text display on the LED matrix."""
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the TextScroller.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        scroller_config = self.config.get("text_scroller", {})
        self.scroll_speed = scroller_config.get("scroll_speed", 0.03)
        self.color = create_graphics_color(scroller_config.get("color", {"r": 255, "g": 255, "b": 255}))
        self.font = load_font(scroller_config.get("font", "7x13.bdf"))
    
    def display_static(self, text: str, x: int = 0, y: int = None, color: graphics.Color = None):
        """
        Display static (non-scrolling) text.
        
        Args:
            text: The text to display.
            x: X position (default 0).
            y: Y position (default: vertically centered).
            color: Optional color override.
        """
        if y is None:
            # Center vertically - assume font height is roughly 10-13 pixels
            y = (self.matrix.height // 2) + 5
        
        if color is None:
            color = self.color
        
        self.canvas.Clear()
        graphics.DrawText(self.canvas, self.font, x, y, color, text)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def scroll(self, text: str, speed: float = None, color: graphics.Color = None, loops: int = 0):
        """
        Scroll text across the display.
        
        Args:
            text: The text to scroll.
            speed: Scroll speed in seconds per pixel (lower = faster).
            color: Optional color override.
            loops: Number of times to loop (0 = infinite).
        """
        if speed is None:
            speed = self.scroll_speed
        
        if color is None:
            color = self.color
        
        text_width = get_text_width(self.font, text)
        pos_x = self.matrix.width
        y_pos = (self.matrix.height // 2) + 5
        
        loop_count = 0
        
        try:
            while loops == 0 or loop_count < loops:
                self.canvas.Clear()
                
                # Draw the text at current position
                text_len = graphics.DrawText(self.canvas, self.font, pos_x, y_pos, color, text)
                
                # Move position for next frame
                pos_x -= 1
                
                # Reset position when text has scrolled off
                if pos_x + text_len < 0:
                    pos_x = self.matrix.width
                    loop_count += 1
                
                self.canvas = self.matrix.SwapOnVSync(self.canvas)
                time.sleep(speed)
                
        except KeyboardInterrupt:
            pass
    
    def scroll_once(self, text: str, speed: float = None, color: graphics.Color = None):
        """
        Scroll text across the display once.
        
        Args:
            text: The text to scroll.
            speed: Scroll speed in seconds per pixel.
            color: Optional color override.
        """
        self.scroll(text, speed, color, loops=1)
    
    def clear(self):
        """Clear the display."""
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


def run(text: str = None, scroll: bool = True, speed: float = None):
    """
    Run the text scroller as a standalone module.
    
    Args:
        text: Text to display. Uses config default if not provided.
        scroll: Whether to scroll (True) or display static (False).
        speed: Optional scroll speed override.
    """
    config = load_config()
    scroller = TextScroller(config=config)
    
    if text is None:
        text = config.get("text_scroller", {}).get("default_text", "Hello World!")
    
    try:
        if scroll:
            scroller.scroll(text, speed=speed)
        else:
            scroller.display_static(text)
            # Keep display on until interrupted
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        scroller.clear()


if __name__ == "__main__":
    run()

