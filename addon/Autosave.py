bl_info = {
    "name": "Blender File Autosave",
    "author": "Cortex",
    "blender": (4, 2, 0),
    "category": "System",
    "version": (1, 0, 0),
    "description": "Atuomatically autosaves Blender files at specified intervals.",
}

# ========================
# Imports
# ========================

import bpy
import os
import shutil
import time

# ========================
# Import from section
# ========================

from datetime import datetime

# ========================
# Status Flag
# ========================

autosave_enabled = False

# ========================
# History snapshot
# ========================

def get_history_dir():
    filepath = bpy.data.filepath
    if not filepath:
        return None
    basedir = os.path.dirname(filepath)
    history_dir = os.path.join(basedir, ".history")
    os.makedirs(history_dir, exist_ok=True)
    return history_dir

def save_snapshot():
    current_file = bpy.data.filepath
    if not current_file:
        print("No file is saved.")
        return
    history_dir = get_history_dir()
    if not history_dir:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(current_file).replace(".blend", "")
    snapshot_name = f"{base_name}_{timestamp}.blend"
    snapshot_path = os.path.join(history_dir, snapshot_name)
    shutil.copy2(current_file, snapshot_path)
    print(f"Snapshot saved: {snapshot_path}")

def list_snapshots():
    history_dir = get_history_dir()
    if not history_dir:
        return []
    return sorted([f for f in os.listdir(history_dir) if f.endswith(".blend")], reverse=True)

def restore_snapshot(snapshot_name):
    history_dir = get_history_dir()
    if not history_dir:
        return
    snapshot_path = os.path.join(history_dir, snapshot_name)
    if os.path.exists(snapshot_path):
        bpy.ops.wm.open_mainfile(filepath=snapshot_path)
    else:
        print(f"Snapshot not found: {snapshot_path}")

# ========================
# Settings
# ========================

class AutosaveSettings(bpy.types.PropertyGroup):
    save_directory: bpy.props.StringProperty(
        name="Autosave Directory",
        description="Directory to save",
        default="//autosave/",
        subtype='DIR_PATH'
    )
    save_interval: bpy.props.FloatProperty(
        name="Autosave Interval (minutes)",
        description="Interval between autosaves",
        default=5.0,
        min=1.0,
        max=60.0
    )

# ========================
# Autosave
# ========================

def autosave():
    global autosave_enabled

    if not autosave_enabled:
        print("Autosave is disabled.")
        return None

    settings = bpy.context.scene.autosave_settings
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

# ========================
# Operators
# ========================

class Autosave_OT_Toggle(bpy.types.Operator):
    bl_idname = "autosave.toggle"
    bl_label = "Toggle Autosave"
    bl_description = "Enable or disable the autosave system."

    def execute(self, context):
        global autosave_enabled
        if autosave_enabled:
            bpy.app.timers.unregister(autosave)
            autosave_enabled = False
            self.report({'INFO'}, "Autosave Disabled")
        else:
            bpy.app.timers.register(autosave, first_interval=context.scene.autosave_settings.save_interval * 60.0)
            autosave_enabled = True
            self.report({'INFO'}, "Autosave Enabled")
        return {'FINISHED'}

class Autosave_OT_SaveSnapshot(bpy.types.Operator):
    bl_idname = "autosave.save_snapshot"
    bl_label = "Save Snapshot"
    bl_description = "Creates a snapshot in the .history folder."

    def execute(self, context):
        save_snapshot()
        return {'FINISHED'}

class Autosave_OT_LoadSnapshot(bpy.types.Operator):
    bl_idname = "autosave.load_snapshot"
    bl_label = "Load Snapshot"
    bl_description = "Load a snapshot from .history folder."

    __annotations__ = {
        "filename": bpy.props.StringProperty()
    }

    def execute(self, context):
        restore_snapshot(self.filename)
        return {'FINISHED'}

# ========================
# Panel UI
# ========================

class Autosave_PT_Panel(bpy.types.Panel):
    bl_label = "File Autosaver"
    bl_idname = "AUTOSAVE_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "File Cloner"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.autosave_settings
        layout.label(text="Autosave Settings")
        layout.prop(settings, "save_directory")
        layout.prop(settings, "save_interval")
        row = layout.row()
        toggle_text = "Disable Autosave" if autosave_enabled else "Enable Autosave"
        toggle_icon = "PAUSE" if autosave_enabled else "PLAY"
        row.operator("autosave.toggle", text=toggle_text, icon=toggle_icon)

class Autosave_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "Snapshots History"
    bl_idname = "AUTOSAVE_PT_snapshots"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'UFH'

    def draw(self, context):
        layout = self.layout
        layout.operator("autosave.save_snapshot", icon="FILE_TICK")
        layout.separator()
        layout.label(text="Saved Snapshots:")
        snapshots = list_snapshots()
        for snap in snapshots:
            row = layout.row(align=True)
            row.label(text=snap, icon="FILE_BLEND")
            op = row.operator("autosave.load_snapshot", text="Restore", icon="IMPORT")
            op.filename = snap

# ========================
# Register
# ========================

classes = (
    AutosaveSettings,
    Autosave_OT_Toggle,
    Autosave_OT_SaveSnapshot,
    Autosave_OT_LoadSnapshot,
    Autosave_PT_SnapshotPanel,
    Autosave_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.autosave_settings = bpy.props.PointerProperty(type=AutosaveSettings)

def unregister():
    try:
        bpy.app.timers.unregister(autosave)
    except:
        pass
    del bpy.types.Scene.autosave_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()