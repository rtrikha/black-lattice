"""
Utility functions for LED matrix operations.
Provides matrix initialization, config loading, and helper functions.
"""

import json
import os
from pathlib import Path

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_config() -> dict:
    """Load configuration from settings.json."""
    config_path = get_project_root() / "config" / "settings.json"
    with open(config_path, "r") as f:
        return json.load(f)

def create_matrix(config: dict = None) -> RGBMatrix:
    """
    Initialize and return an RGBMatrix instance.
    """
    if config is None:
        config = load_config()
    
    matrix_config = config.get("matrix", {})
    
    options = RGBMatrixOptions()
    options.rows = matrix_config.get("rows", 32)
    options.cols = matrix_config.get("cols", 64)
    options.chain_length = matrix_config.get("chain_length", 1)
    options.parallel = matrix_config.get("parallel", 1)
    options.hardware_mapping = "adafruit-hat"
    options.disable_hardware_pulsing = True
    options.brightness = matrix_config.get("brightness", 50)
    options.gpio_slowdown = matrix_config.get("gpio_slowdown", 4)
    options.pwm_bits = matrix_config.get("pwm_bits", 11)
    options.pwm_lsb_nanoseconds = matrix_config.get("pwm_lsb_nanoseconds", 130)
    options.show_refresh_rate = matrix_config.get("show_refresh_rate", False)

    # 👇 NEW: tell the library how the panel’s LEDs are wired
    # Valid values: "RGB", "RBG", "GRB", "GBR", "BRG", "BGR"
    options.led_rgb_sequence = matrix_config.get("rgb_sequence", "RBG")
    
    return RGBMatrix(options=options)

def hex_to_rgb(hex_color: str) -> tuple:
    """
    Parse a hex color string to RGB tuple.
    
    Args:
        hex_color: Hex color string (e.g., "#FFFFFF" or "FFFFFF").
    
    Returns:
        Tuple of (r, g, b) values.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color format: {hex_color}")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16)
    )


def parse_color(color_input) -> tuple:
    """
    Parse a color input (hex string or RGB dict) to RGB tuple.
    
    Args:
        color_input: Either a hex color string (e.g., "#FFFFFF") or
                     a dictionary with 'r', 'g', 'b' keys.
    
    Returns:
        Tuple of (r, g, b) values.
    """
    if isinstance(color_input, str):
        return hex_to_rgb(color_input)
    elif isinstance(color_input, dict):
        return (
            color_input.get("r", 255),
            color_input.get("g", 255),
            color_input.get("b", 255)
        )
    else:
        raise ValueError(f"Invalid color format: {color_input}")


def create_graphics_color(color_input) -> graphics.Color:
    """
    Create an rgbmatrix graphics Color from a color input.
    
    Args:
        color_input: Either a hex color string (e.g., "#FFFFFF") or
                     a dictionary with 'r', 'g', 'b' keys.
    
    Returns:
        graphics.Color instance.
    """
    r, g, b = parse_color(color_input)
    return graphics.Color(r, g, b)


def load_font(font_name: str = "7x13.bdf") -> graphics.Font:
    """
    Load a BDF font file.
    
    Searches for fonts in the following order:
    1. Project assets/fonts directory (assets/fonts/)
    2. rpi-rgb-led-matrix fonts directory
    
    Args:
        font_name: Name of the font file (e.g., "7x13.bdf", "5x7.bdf").
    
    Returns:
        Loaded graphics.Font instance.
    
    Raises:
        FileNotFoundError: If font file cannot be found.
    """
    font = graphics.Font()
    
    # Try project assets/fonts directory first
    project_root = get_project_root()
    project_font_path = project_root / "assets" / "fonts" / font_name
    
    # Try rpi-rgb-led-matrix fonts directory as fallback
    system_font_path = Path("/home/pi/rpi-rgb-led-matrix/fonts") / font_name
    
    if project_font_path.exists():
        font_path = project_font_path
    elif system_font_path.exists():
        font_path = system_font_path
    else:
        # Last resort: try just the font name (might be in current directory)
        font_path = Path(font_name)
        if not font_path.exists():
            raise FileNotFoundError(
                f"Font file '{font_name}' not found. "
                f"Tried: {project_font_path}, {system_font_path}, {font_path}"
            )
    
    font.LoadFont(str(font_path))
    return font

def get_text_width(font: graphics.Font, text: str) -> int:
    """Calculate the pixel width of text with a given font."""
    width = 0
    for char in text:
        width += font.CharacterWidth(ord(char))
    return width


def fill_canvas_background(canvas, color: graphics.Color):
    """
    Fill the entire canvas with a background color.
    Uses DrawLine for each row, which is faster than SetPixel for each pixel.
    """
    for y in range(canvas.height):
        graphics.DrawLine(canvas, 0, y, canvas.width - 1, y, color)


def load_stylesheet() -> dict:
    """
    Load stylesheet from config/styles.json.
    
    Returns:
        Parsed stylesheet dictionary.
    
    Raises:
        FileNotFoundError: If styles.json doesn't exist.
        json.JSONDecodeError: If styles.json is invalid JSON.
    """
    config_path = get_project_root() / "config" / "styles.json"
    
    if not config_path.exists():
        # Return minimal default stylesheet
        return {
            "font_sizes": {
                "small": "5x7.bdf",
                "medium": "7x13.bdf",
                "large": "7x13.bdf"
            },
            "defaults": {
                "font_size": "medium",
                "color": "#FFFFFF",
                "background_color": "#000000",
                "gap": 2,
                "gravity": "center"
            },
            "classes": {},
            "grids": {}
        }
    
    with open(config_path, "r") as f:
        return json.load(f)


def get_font_size_mapping() -> dict:
    """
    Get font size preset mappings from stylesheet.
    
    Returns:
        Dictionary mapping font size presets (small, medium, large) to font filenames.
    """
    stylesheet = load_stylesheet()
    return stylesheet.get("font_sizes", {
        "small": "5x7.bdf",
        "medium": "7x13.bdf",
        "large": "7x13.bdf"
    })