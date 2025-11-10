bl_info = {
    "name": "Ultimate File Handler",
    "author": "Cortex",
    "blender": (4, 2, 0),
    "version": (2, 0, alpha),
    "location": "View3D > Sidebar > Ultimate File Handler",
    "description": "This add-on make the file saving in Blender better and more convenient. Placing you on the control of your files. No Internet connection is required for the main functions.",
    "category": "System",
}

# ================================================
# Import from section
# ================================================

from .core import register, unregister