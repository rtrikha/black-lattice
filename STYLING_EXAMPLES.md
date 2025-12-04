# Styling Elements Guide

## How to Style Elements in Your Clock Script

### Method 1: Using CSS-like Classes (Recommended)

**Step 1:** Define styles in `config/styles.json`:
```json
{
  "classes": {
    ".time-display": {
      "font_size": "large",
      "color": "#FFFF80",
      "gravity": "top-center"
    },
    ".date-display": {
      "font_size": "small",
      "color": "#FFFF80",
      "gravity": "bottom-center"
    }
  }
}
```

**Step 2:** Use classes in your Python code:
```python
time_element = Element(
    text=time_str,
    classes=["time-display"]  # Automatically applies .time-display styles
)
```

### Method 2: Per-Element Style Overrides

Override styles for specific elements:
```python
time_element = Element(
    text=time_str,
    classes=["time-display"],
    style_overrides={
        "color": "#FF0000",        # Red instead of yellow
        "font_size": "small",      # Smaller font
        "gravity": "top-left"      # Different position
    }
)
```

### Method 3: Multiple Classes

Apply multiple classes (styles merge):
```python
# Add to styles.json:
# ".highlight": { "color": "#00FF00" }
# ".bold": { "font_size": "large" }

time_element = Element(
    text=time_str,
    classes=["time-display", "highlight", "bold"]
)
```

### Method 4: Direct Positioning

Set exact pixel coordinates:
```python
time_element = Element(
    text=time_str,
    classes=["time-display"],
    x=10,  # Exact X position (overrides gravity)
    y=15   # Exact Y position
)
```

### Method 5: Using Grid Layouts

Layout multiple elements in a grid:
```python
elements = [
    Element(text=time_str, classes=["time-display"]),
    Element(text=date_str, classes=["date-display"])
]

# Use grid from styles.json
from style_parser import load_stylesheet
stylesheet = load_stylesheet()
grid_config = stylesheet["grids"]["two-row"]

self.layout.render(elements, use_grid=True, grid_config=grid_config)
```

## Available Style Properties

- `font_size`: "small", "medium", or "large"
- `color`: Hex color string (e.g., "#FF0000")
- `background_color`: Hex color string
- `gravity`: "top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"
- `gap`: Integer (pixels between elements)
- `margin`: Integer (pixels from edges)
- `padding`: Integer (internal spacing)

## Example: Enhanced Clock Display

```python
def display(self):
    time_str = self.get_time_string()
    elements = []
    
    if self.show_date:
        # Time with custom styling
        time_element = Element(
            text=time_str,
            classes=["time-display"],
            style_overrides={"margin": 5}  # Add margin
        )
        elements.append(time_element)
        
        # Date with different color
        date_str = self.get_date_string()
        date_element = Element(
            text=date_str,
            classes=["date-display"],
            style_overrides={"color": "#00FF00"}  # Green date
        )
        elements.append(date_element)
    else:
        # Centered time with large font
        time_element = Element(
            text=time_str,
            classes=["time-display"],
            style_overrides={
                "gravity": "center",
                "font_size": "large"
            }
        )
        elements.append(time_element)
    
    self.layout.render(elements)
```




