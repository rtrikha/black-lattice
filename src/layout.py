"""
Layout engine for LED matrix display.
Provides CSS-like positioning with gravity and grid layouts.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum

from rgbmatrix import RGBMatrix, graphics

from style import Style, StyleManager
from style_parser import create_style_manager
from utils import get_text_width


class Gravity(Enum):
    """Gravity positioning options."""
    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    CENTER_LEFT = "center-left"
    CENTER = "center"
    CENTER_RIGHT = "center-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


@dataclass
class Element:
    """Represents a positioned element on the canvas."""
    
    text: str
    classes: Optional[List[str]] = None
    style_overrides: Optional[Dict[str, Any]] = None
    gravity: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    grid_cell: Optional[Tuple[int, int]] = None  # (row, col) for grid positioning
    
    def __post_init__(self):
        """Initialize classes list if not provided."""
        if self.classes is None:
            self.classes = []


class LayoutEngine:
    """Manages layout and positioning of elements on the canvas."""
    
    def __init__(self, matrix: RGBMatrix, style_manager: Optional[StyleManager] = None):
        """
        Initialize LayoutEngine.
        
        Args:
            matrix: RGBMatrix instance.
            style_manager: Optional StyleManager. Creates one if not provided.
        """
        self.matrix = matrix
        self.canvas = matrix.CreateFrameCanvas()
        self.style_manager = style_manager or create_style_manager()
        self.width = matrix.width
        self.height = matrix.height
    
    def calculate_position(
        self,
        element: Element,
        style: Style,
        text_width: int,
        text_height: int
    ) -> Tuple[int, int]:
        """
        Calculate absolute position for an element based on gravity or explicit position.
        
        Args:
            element: Element to position.
            style: Resolved style for the element.
            text_width: Width of the text in pixels.
            text_height: Height of the text in pixels (typically font height).
        
        Returns:
            Tuple of (x, y) absolute pixel coordinates.
        """
        # Explicit position takes precedence
        if element.x is not None and element.y is not None:
            return (element.x, element.y)
        
        # Use element gravity or style gravity
        gravity_str = element.gravity or style.gravity
        
        try:
            gravity = Gravity(gravity_str)
        except ValueError:
            # Invalid gravity, default to center
            gravity = Gravity.CENTER
        
        # Calculate position based on gravity
        if gravity == Gravity.TOP_LEFT:
            x = style.margin
            y = text_height + style.margin
        elif gravity == Gravity.TOP_CENTER:
            x = (self.width - text_width) // 2
            y = text_height + style.margin
        elif gravity == Gravity.TOP_RIGHT:
            x = self.width - text_width - style.margin
            y = text_height + style.margin
        elif gravity == Gravity.CENTER_LEFT:
            x = style.margin
            y = (self.height + text_height) // 2
        elif gravity == Gravity.CENTER:
            x = (self.width - text_width) // 2
            y = (self.height + text_height) // 2
        elif gravity == Gravity.CENTER_RIGHT:
            x = self.width - text_width - style.margin
            y = (self.height + text_height) // 2
        elif gravity == Gravity.BOTTOM_LEFT:
            x = style.margin
            y = self.height - style.margin
        elif gravity == Gravity.BOTTOM_CENTER:
            x = (self.width - text_width) // 2
            y = self.height - style.margin
        elif gravity == Gravity.BOTTOM_RIGHT:
            x = self.width - text_width - style.margin
            y = self.height - style.margin
        else:
            # Fallback to center
            x = (self.width - text_width) // 2
            y = (self.height + text_height) // 2
        
        return (x, y)
    
    def render_element(self, element: Element) -> None:
        """
        Render a single element on the canvas.
        
        Args:
            element: Element to render.
        """
        # Resolve style
        style = self.style_manager.resolve_style(
            classes=element.classes,
            overrides=element.style_overrides
        )
        
        # Calculate text dimensions
        text_width = get_text_width(style.font, element.text)
        # Font height - estimate based on font size preset
        # BDF fonts: xs (4x6) ≈ 6px, small (5x7) ≈ 7px, medium/large (7x13) ≈ 13px
        font_size = style.font_size
        if font_size == "xs":
            text_height = 6
        elif font_size == "small":
            text_height = 7
        elif font_size == "large":
            text_height = 13
        else:  # medium or default
            text_height = 13
        
        # Calculate position
        x, y = self.calculate_position(element, style, text_width, text_height)
        
        # Draw background if specified
        if style.background_color:
            # For now, just fill the entire canvas if background is set
            # In the future, could be more sophisticated
            pass
        
        # Draw text
        graphics.DrawText(self.canvas, style.font, x, y, style.color, element.text)
    
    def render_grid(
        self,
        elements: List[Element],
        columns: int = 1,
        rows: int = 1,
        gap: int = 2
    ) -> None:
        """
        Render elements in a grid layout.
        
        Args:
            elements: List of elements to render.
            columns: Number of grid columns.
            rows: Number of grid rows.
            gap: Gap between grid cells in pixels.
        """
        if not elements:
            return
        
        # Calculate cell dimensions
        total_gap_width = gap * (columns - 1) if columns > 1 else 0
        total_gap_height = gap * (rows - 1) if rows > 1 else 0
        cell_width = (self.width - total_gap_width) // columns
        cell_height = (self.height - total_gap_height) // rows
        
        for i, element in enumerate(elements):
            # Determine grid position
            if element.grid_cell:
                row, col = element.grid_cell
            else:
                # Auto-assign based on element index
                row = i // columns
                col = i % columns
            
            # Calculate cell bounds
            cell_x = col * (cell_width + gap)
            cell_y = row * (cell_height + gap)
            
            # Resolve style
            style = self.style_manager.resolve_style(
                classes=element.classes,
                overrides=element.style_overrides
            )
            
            # Calculate text dimensions
            text_width = get_text_width(style.font, element.text)
            # Font height - estimate based on font size preset
            font_size = style.font_size
            if font_size == "xs":
                text_height = 6
            elif font_size == "small":
                text_height = 7
            elif font_size == "large":
                text_height = 13
            else:  # medium or default
                text_height = 13
            
            # Calculate position within cell (center by default)
            cell_center_x = cell_x + cell_width // 2
            cell_center_y = cell_y + cell_height // 2
            
            x = cell_center_x - text_width // 2
            y = cell_center_y + text_height // 2
            
            # Draw text
            graphics.DrawText(self.canvas, style.font, x, y, style.color, element.text)
    
    def render(self, elements: List[Element], use_grid: bool = False, grid_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Render a list of elements on the canvas.
        
        Args:
            elements: List of elements to render.
            use_grid: Whether to use grid layout.
            grid_config: Optional grid configuration (columns, rows, gap).
        """
        self.canvas.Clear()
        
        if use_grid:
            if grid_config:
                self.render_grid(
                    elements,
                    columns=grid_config.get("columns", 1),
                    rows=grid_config.get("rows", 1),
                    gap=grid_config.get("gap", 2)
                )
            else:
                self.render_grid(elements)
        else:
            # Render elements individually with gravity positioning
            for element in elements:
                self.render_element(element)
        
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def clear(self) -> None:
        """Clear the canvas."""
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

