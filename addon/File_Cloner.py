bl_info = {
    "name": "File Handler",
    "author": "Cortex",
    "blender": (4, 2, 0),
    "category": "System",
    "version": (1, 0, 0),
    "description": "Automatically clones the current file at regular intervals in a folder of our choice.",
}

# =====================
# Imports
# =====================

import bpy
import os
import time

# =====================
# Status Flag
# =====================

cloning_enabled = False

# =====================
# Configuration
# =====================

class CloningSettings(bpy.types.PropertyGroup):
    save_directory: bpy.props.StringProperty(
        name="Cloning Directory",
        description="Directory to save clones",
        default="//cloning/",
        subtype='DIR_PATH'
    )
    save_interval: bpy.props.FloatProperty(
        name="Cloning Interval (minutes)",
        description="Interval between clones",
        default=5.0,
        min=1.0,
        max=60.0
    )

# =====================
# Cloning Function
# =====================

def cloning():
    global cloning_enabled

    if not cloning_enabled:
        print("Cloning is disabled.")
        return None

    settings = bpy.context.scene.cloning_settings
    directory = bpy.path.abspath(settings.save_directory)
    interval = settings.save_interval

    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"Directory created: {directory}")
        except Exception as e:
            print(f"Failed to create directory: {e}")
            return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"clone_{timestamp}.blend"
    save_path = os.path.join(directory, filename)

    try:
        bpy.ops.wm.save_as_mainfile(filepath=save_path, copy=True)
        print(f"Clone saved at: {save_path}")
    except Exception as e:
        print(f"Failed to save clone: {e}")

    return interval * 60.0


# =====================
# Panel UI
# =====================

class CLONER_PT_Panel(bpy.types.Panel):
    bl_label = "File Cloner"
    bl_idname = "CLONER_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "File Cloner"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.cloning_settings

        layout.label(text="Cloning Settings")
        layout.prop(settings, "save_directory")
        layout.prop(settings, "save_interval")

        row = layout.row()
        toggle_text = "Disable Cloning" if cloning_enabled else "Enable Cloning"
        toggle_icon = "PAUSE" if cloning_enabled else "PLAY"
        row.operator("cloning.toggle", text=toggle_text, icon=toggle_icon)

# =====================
# Operator for on/off
# =====================

class CLONER_OT_Toggle(bpy.types.Operator):
    bl_idname = "cloning.toggle"
    bl_label = "Toggle Cloning"

    def execute(self, context):
        global cloning_enabled

        if cloning_enabled:
            bpy.app.timers.unregister(cloning)
            cloning_enabled = False
            self.report({'INFO'}, "Cloning Disabled")
        else:
            bpy.app.timers.register(cloning, first_interval=context.scene.cloning_settings.save_interval * 60.0)
            cloning_enabled = True
            self.report({'INFO'}, "Cloning Enabled")

        return {'FINISHED'}

# =====================
# Register
# =====================

classes = (
    CloningSettings,
    CLONER_PT_Panel,
    CLONER_OT_Toggle,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.cloning_settings = bpy.props.PointerProperty(type=CloningSettings)

def unregister():
    try:
        bpy.app.timers.unregister(cloning)
    except:
        pass

    del bpy.types.Scene.cloning_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
