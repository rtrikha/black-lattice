"""
Stylesheet parser for LED matrix display.
Loads and parses styles.json configuration file.
"""

import json
from pathlib import Path
from typing import Dict, Any

from utils import get_project_root


def get_default_stylesheet() -> Dict[str, Any]:
    """Return default stylesheet when file cannot be loaded."""
    return {
        "font_sizes": {
            "xs": "4x6.bdf",
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


def load_stylesheet() -> Dict[str, Any]:
    """
    Load stylesheet from config/styles.json.
    
    Returns:
        Parsed stylesheet dictionary.
    """
    try:
        config_path = get_project_root() / "config" / "styles.json"
        
        # Use os.path.exists instead of pathlib.exists() to avoid permission issues
        import os
        if not os.path.exists(config_path):
            return get_default_stylesheet()
        
        with open(config_path, "r") as f:
            return json.load(f)
    except (PermissionError, IOError, OSError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load styles.json: {e}. Using defaults.")
        return get_default_stylesheet()


def create_style_manager():
    """
    Create a StyleManager instance with loaded stylesheet.
    
    Returns:
        Initialized StyleManager.
    """
    # Import here to avoid circular dependency
    from style import StyleManager
    stylesheet = load_stylesheet()
    return StyleManager(stylesheet)

