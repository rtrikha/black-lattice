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
    
    Args:
        config: Optional config dict. If None, loads from settings.json.
    
    Returns:
        Configured RGBMatrix instance.
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
    
    return RGBMatrix(options=options)


def parse_color(color_dict: dict) -> tuple:
    """
    Parse a color dictionary to RGB tuple.
    
    Args:
        color_dict: Dictionary with 'r', 'g', 'b' keys.
    
    Returns:
        Tuple of (r, g, b) values.
    """
    return (
        color_dict.get("r", 255),
        color_dict.get("g", 255),
        color_dict.get("b", 255)
    )


def create_graphics_color(color_dict: dict) -> graphics.Color:
    """
    Create an rgbmatrix graphics Color from a color dictionary.
    
    Args:
        color_dict: Dictionary with 'r', 'g', 'b' keys.
    
    Returns:
        graphics.Color instance.
    """
    r, g, b = parse_color(color_dict)
    return graphics.Color(r, g, b)


def load_font(font_name: str) -> graphics.Font:
    """
    Load a BDF font file.
    
    Args:
        font_name: Name of the font file (e.g., '7x13.bdf').
    
    Returns:
        graphics.Font instance.
    """
    font = graphics.Font()
    
    # First check the local fonts directory
    local_font_path = get_project_root() / "fonts" / font_name
    if local_font_path.exists():
        font.LoadFont(str(local_font_path))
        return font
    
    # Fall back to the rpi-rgb-led-matrix fonts directory
    system_font_paths = [
        f"/usr/share/fonts/truetype/{font_name}",
        f"/usr/local/share/fonts/{font_name}",
        f"~/rpi-rgb-led-matrix/fonts/{font_name}",
        os.path.expanduser(f"~/rpi-rgb-led-matrix/fonts/{font_name}"),
    ]
    
    for path in system_font_paths:
        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
            font.LoadFont(expanded_path)
            return font
    
    # If no font found, try loading anyway (will use default)
    try:
        font.LoadFont(str(local_font_path))
    except Exception:
        pass
    
    return font


def get_text_width(font: graphics.Font, text: str) -> int:
    """
    Calculate the pixel width of text with a given font.
    
    Args:
        font: The graphics.Font to use.
        text: The text string to measure.
    
    Returns:
        Width in pixels.
    """
    width = 0
    for char in text:
        width += font.CharacterWidth(ord(char))
    return width

