bl_info = {
    "name": "Ultimate File Saver",
    "author": "Cortex",
    "blender": (4, 5, 0),
    "version": (2, 0, alpha),
    "location": "View3D > Sidebar > Ultimate File Saver",
    "description": "This add-on make the file saving in Blender better and more convenient. Placing you on the control of your files. No Internet connection is required for the main functions.",
    "category": "System",
}

# ================================================
# Import from section
# ================================================

from .core import register, unregister