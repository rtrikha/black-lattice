"""
Style system for LED matrix display.
Provides CSS-like styling with font sizes, colors, and layout properties.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

from rgbmatrix import graphics

from utils import (
    create_graphics_color,
    parse_color,
    load_font,
    get_project_root,
)


@dataclass
class Style:
    """Computed style properties for an element."""
    
    font_size: str = "medium"
    font: Optional[graphics.Font] = None
    color: graphics.Color = field(default_factory=lambda: graphics.Color(255, 255, 255))
    background_color: Optional[graphics.Color] = None
    gap: int = 2
    gravity: str = "center"
    padding: int = 0
    margin: int = 0
    
    def __post_init__(self):
        """Initialize font after object creation."""
        if self.font is None:
            self.font = load_font("7x13.bdf")


class StyleManager:
    """Manages font size mappings and style resolution."""
    
    def __init__(self, stylesheet: Dict[str, Any], preload_fonts: bool = True):
        """
        Initialize StyleManager with a stylesheet.
        
        Args:
            stylesheet: Parsed styles.json configuration.
            preload_fonts: If True, preload all fonts immediately (recommended to call before RGBMatrix init)
        """
        self.stylesheet = stylesheet
        self.font_sizes = stylesheet.get("font_sizes", {})
        self.defaults = stylesheet.get("defaults", {})
        self.class_rules = self._flatten_classes(stylesheet.get("classes", {}))
        
        # Cache loaded fonts
        self._font_cache: Dict[str, graphics.Font] = {}
        
        # Preload all fonts immediately (before matrix init breaks file access)
        if preload_fonts:
            self._preload_fonts()
    
    def _flatten_classes(self, classes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten nested class structure into a flat dictionary.
        
        Supports both flat structure:
            {".time-display": {...}}
        
        And nested structure (organized by feature):
            {"clock": {".time-display": {...}}}
        """
        flat = {}
        for key, value in classes.items():
            if key.startswith("."):
                # It's a class rule (flat structure)
                flat[key] = value
            elif isinstance(value, dict):
                # It's a feature group - extract nested classes
                for class_key, class_value in value.items():
                    if class_key.startswith(".") and isinstance(class_value, dict):
                        flat[class_key] = class_value
        return flat
    
    def _preload_fonts(self):
        """Preload all fonts defined in the stylesheet."""
        for font_size, font_file in self.font_sizes.items():
            if font_file not in self._font_cache:
                try:
                    self._font_cache[font_file] = load_font(font_file)
                except FileNotFoundError as e:
                    print(f"Warning: Could not preload font {font_file}: {e}")
    
    def get_font(self, font_size: str) -> graphics.Font:
        """
        Get a font for a given font size preset.
        
        Args:
            font_size: Font size preset (small, medium, large) or font filename.
        
        Returns:
            Loaded graphics.Font instance.
        """
        # If it's a preset, resolve to actual font file
        if font_size in self.font_sizes:
            font_file = self.font_sizes[font_size]
        else:
            # Assume it's already a font filename
            font_file = font_size
        
        # Check cache first
        if font_file in self._font_cache:
            return self._font_cache[font_file]
        
        # Load font
        font = load_font(font_file)
        self._font_cache[font_file] = font
        return font
    
    def resolve_style(
        self,
        classes: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Style:
        """
        Resolve a style by merging defaults, class rules, and overrides.
        
        Style resolution priority:
        1. Element-specific overrides
        2. Class rules (applied in order)
        3. Default styles
        
        Args:
            classes: List of CSS-like class names (e.g., ["time-display", "large-text"]).
            overrides: Element-specific style overrides.
        
        Returns:
            Resolved Style object.
        """
        # Start with defaults
        style_dict = self.defaults.copy()
        
        # Apply class rules in order
        if classes:
            for class_name in classes:
                # Remove leading dot if present
                class_key = class_name.lstrip(".")
                rule_key = f".{class_key}"
                
                if rule_key in self.class_rules:
                    class_rule = self.class_rules[rule_key]
                    style_dict.update(class_rule)
        
        # Apply element-specific overrides (highest priority)
        if overrides:
            style_dict.update(overrides)
        
        # Create Style object
        font_size = style_dict.get("font_size", "medium")
        font = self.get_font(font_size)
        
        color_input = style_dict.get("color", "#FFFFFF")
        brightness = style_dict.get("brightness", 100)
        brightness = max(0, min(100, brightness))  # Clamp between 0-100
        
        # Apply brightness to color
        r, g, b = parse_color(color_input)
        brightness_factor = brightness / 100.0
        r = int(r * brightness_factor)
        g = int(g * brightness_factor)
        b = int(b * brightness_factor)
        color = graphics.Color(r, g, b)
        
        background_color = None
        if "background_color" in style_dict:
            bg_color_input = style_dict["background_color"]
            bg_brightness = style_dict.get("background_brightness", brightness)
            bg_brightness = max(0, min(100, bg_brightness))
            bg_r, bg_g, bg_b = parse_color(bg_color_input)
            bg_brightness_factor = bg_brightness / 100.0
            bg_r = int(bg_r * bg_brightness_factor)
            bg_g = int(bg_g * bg_brightness_factor)
            bg_b = int(bg_b * bg_brightness_factor)
            background_color = graphics.Color(bg_r, bg_g, bg_b)
        
        return Style(
            font_size=font_size,
            font=font,
            color=color,
            background_color=background_color,
            gap=style_dict.get("gap", 2),
            gravity=style_dict.get("gravity", "center"),
            padding=style_dict.get("padding", 0),
            margin=style_dict.get("margin", 0),
        )

