"""
Stylesheet parser for LED matrix display.
Loads and parses styles.json configuration file.
"""

import json
from pathlib import Path
from typing import Dict, Any

from utils import get_project_root


def load_stylesheet() -> Dict[str, Any]:
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

