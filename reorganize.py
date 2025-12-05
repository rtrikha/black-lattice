#!/usr/bin/env python3
"""Script to reorganize project structure."""

import shutil
from pathlib import Path

project_root = Path("/home/pi/black-lattice")
assets_dir = project_root / "assets"
fonts_source = project_root / "fonts"
fonts_dest = assets_dir / "fonts"

# Create assets directory
assets_dir.mkdir(exist_ok=True)
print(f"Created: {assets_dir}")

# Move fonts to assets
if fonts_source.exists() and not fonts_dest.exists():
    shutil.move(str(fonts_source), str(fonts_dest))
    print(f"Moved fonts from {fonts_source} to {fonts_dest}")
else:
    print(f"Fonts already in place or source doesn't exist")

print("Done!")









