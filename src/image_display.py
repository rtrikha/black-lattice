"""
Image display module for LED matrix display.
Displays an image file on the LED matrix.
Supports common image formats (PNG, JPEG, GIF, etc.).
"""

import time
import sys
from pathlib import Path
from PIL import Image

from rgbmatrix import RGBMatrix

from utils import (
    load_config,
    create_matrix,
    get_project_root,
)


class ImageDisplay:
    """Displays an image file on the LED matrix."""
    
    def __init__(self, matrix: RGBMatrix = None, config: dict = None):
        """
        Initialize the ImageDisplay.
        
        Args:
            matrix: Optional RGBMatrix instance. Creates one if not provided.
            config: Optional config dict. Loads from file if not provided.
        """
        self.config = config or load_config()
        self.matrix = matrix or create_matrix(self.config)
        
        # Get matrix dimensions from config
        matrix_config = self.config.get("matrix", {})
        self.width = matrix_config.get("cols", 64)
        self.height = matrix_config.get("rows", 32)
    
    def load_and_resize_image(self, image_path: Path) -> Image.Image:
        """
        Load an image and resize it to match the matrix dimensions.
        
        Args:
            image_path: Path to the image file.
        
        Returns:
            Resized PIL Image object.
        
        Raises:
            FileNotFoundError: If the image file doesn't exist.
            ValueError: If the image cannot be opened.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            # Open and convert to RGB (handles RGBA, P, etc.)
            img = Image.open(image_path)
            img = img.convert("RGB")
            
            # Resize to matrix dimensions, using LANCZOS for better quality
            img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            
            return img
        except Exception as e:
            raise ValueError(f"Failed to open image: {e}")
    
    def display_image(self, image_path: Path):
        """
        Display an image on the LED matrix.
        
        Args:
            image_path: Path to the image file.
        """
        img = self.load_and_resize_image(image_path)
        
        # Get the canvas from the matrix
        canvas = self.matrix.CreateFrameCanvas()
        
        # Draw each pixel
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = img.getpixel((x, y))
                canvas.SetPixel(x, y, r, g, b)
        
        # Swap the canvas to display
        canvas = self.matrix.SwapOnVSync(canvas)
    
    def display_image_continuous(self, image_path: Path, duration: float = None):
        """
        Display an image continuously (or for a specified duration).
        
        Args:
            image_path: Path to the image file.
            duration: How long to display the image in seconds. 
                     If None, displays until interrupted.
        """
        try:
            if duration:
                end_time = time.time() + duration
                while time.time() < end_time:
                    self.display_image(image_path)
                    time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            else:
                # Display indefinitely
                while True:
                    self.display_image(image_path)
                    time.sleep(0.1)
        except KeyboardInterrupt:
            self.clear()
    
    def clear(self):
        """Clear the display."""
        canvas = self.matrix.CreateFrameCanvas()
        # Fill with black
        for y in range(self.height):
            for x in range(self.width):
                canvas.SetPixel(x, y, 0, 0, 0)
        self.matrix.SwapOnVSync(canvas)


def run():
    """Run the image display as a standalone module."""
    if len(sys.argv) < 2:
        print("Usage: python3 image_display.py <image_path> [duration_seconds]")
        print("\nExample:")
        print("  python3 image_display.py /path/to/image.png")
        print("  python3 image_display.py /path/to/image.jpg 10  # Display for 10 seconds")
        sys.exit(1)
    
    image_path = Path(sys.argv[1]).expanduser().resolve()
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else None
    
    config = load_config()
    display = ImageDisplay(config=config)
    
    print(f"Displaying image: {image_path}")
    if duration:
        print(f"Duration: {duration} seconds")
    else:
        print("Press Ctrl+C to stop")
    
    display.display_image_continuous(image_path, duration)


if __name__ == "__main__":
    run()









