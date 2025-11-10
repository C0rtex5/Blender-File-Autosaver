# ================================================
# Imports
# ================================================

import bpy
import os
import threading
import time
from pathlib import Path

from . import history_manager as hm

# ================================================
# Settings / PropertyGroup
# ================================================

class UASettings(bpy.types.PropertyGroup):
    save_directory: bpy.props.StringProperty(
        name="Autosave Base Directory",
        description="Base folder where project history folders are stored",
        default="//autosave/",
        subtype='DIR_PATH'
    )
    autosave_interval: bpy.props.FloatProperty(
        name="Interval (minutes)",
        description="Minutes between automatic version saves",
        default=10.0,
        min=0.5, max=1440.0
    )
    keep_uncompressed: bpy.props.IntProperty(
        name="Keep Uncompressed",
        description="Number of newest versions to keep uncompressed (others will be gzipped)",
        default=3, min=1, max=100
    )
    purge_days: bpy.props.IntProperty(
        name="Purge Deleted After (days)",
        description="Automatically purge files in deleted/ older than this (0 disables)",
        default=30, min=0, max=3650
    )
    enabled: bpy.props.BoolProperty(
        name="Enable Autosave",
        description="Toggle automatic versioning",
        default=False
    )

# ---------- Timer & autosave function ----------
_timer_handle = None

def _autosave_worker():
    """
    Runs in main thread via bpy.app.timers.register. Performs save and schedules next call.
    """
    settings = bpy.context.scene.ua_settings
    # compute project dir based on current blend file
    base_dir = bpy.path.abspath(settings.save_directory)
    proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
    saved = hm.save_versioned_copy(bpy, proj_dir, note="auto")
    # compress older versions in background to avoid blocking UI if heavy
    def _compress():
        try:
            hm.compress_old_versions(proj_dir, keep_uncompressed=settings.keep_uncompressed)
            if settings.purge_days > 0:
                hm.purge_deleted_older_than(proj_dir, settings.purge_days)
        except Exception as e:
            print(f"[UltimateAutosaver] background compress/purge failed: {e}")
    t = threading.Thread(target=_compress, daemon=True)
    t.start()
    # next interval (minutes -> seconds)
    return settings.autosave_interval * 60.0

# ---------- Operators ----------
class UA_OT_ToggleAutosave(bpy.types.Operator):
    bl_idname = "ua.toggle_autosave"
    bl_label = "Toggle Autosave"

    def execute(self, context):
        settings = context.scene.ua_settings
        global _timer_handle
        if settings.enabled:
            # disable
            try:
                bpy.app.timers.unregister(_autosave_worker)
            except Exception:
                pass
            settings.enabled = False
            self.report({'INFO'}, "Autosave disabled")
        else:
            settings.enabled = True
            bpy.app.timers.register(_autosave_worker, first_interval=1.0)
            self.report({'INFO'}, "Autosave enabled")
        return {'FINISHED'}

class UA_OT_ManualBackup(bpy.types.Operator):
    bl_idname = "ua.manual_backup"
    bl_label = "Manual Backup"
    bl_description = "Create a manual backup into selected folder (opens file browser)"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        settings = context.scene.ua_settings
        base_dir = bpy.path.abspath(settings.save_directory)
        proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
        # directory chosen by invoke
        target_dir = self.directory if self.directory else os.path.join(proj_dir, "backups")
        _path = hm.manual_backup(bpy, target_dir, note="manual")
        if _path:
            # register in index if inside project_dir
            if os.path.commonpath([os.path.abspath(target_dir), os.path.abspath(proj_dir)]) == os.path.abspath(proj_dir):
                hm.register_version(proj_dir, _path, note="manual")
            self.report({'INFO'}, f"Backup saved: {os.path.basename(_path)}")
        else:
            self.report({'ERROR'}, "Backup failed (see console)")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        # open directory chooser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class UA_OT_ListHistory(bpy.types.Operator):
    bl_idname = "ua.list_history"
    bl_label = "List History"
    bl_description = "Print history to system console and update internal list"

    def execute(self, context):
        settings = context.scene.ua_settings
        base_dir = bpy.path.abspath(settings.save_directory)
        proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
        versions = hm.list_versions(proj_dir, include_deleted=True)
        print("---- Ultimate Autosaver History ----")
        for v in versions:
            print(f"{v.get('file')}  | {v.get('timestamp')} | {v.get('status')} | {v.get('note')}")
        print("---- End ----")
        self.report({'INFO'}, "History printed to system console")
        return {'FINISHED'}

class UA_OT_MoveToDeleted(bpy.types.Operator):
    bl_idname = "ua.move_to_deleted"
    bl_label = "Move To Deleted"
    filename: bpy.props.StringProperty(name="Filename (basename)")

    def execute(self, context):
        settings = context.scene.ua_settings
        base_dir = bpy.path.abspath(settings.save_directory)
        proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
        ok = hm.move_to_deleted(proj_dir, self.filename)
        if ok:
            self.report({'INFO'}, f"Moved {self.filename} to deleted/")
        else:
            self.report({'ERROR'}, "Move failed (see console)")
        return {'FINISHED'}

class UA_OT_RestoreDeleted(bpy.types.Operator):
    bl_idname = "ua.restore_deleted"
    bl_label = "Restore Deleted"
    filename: bpy.props.StringProperty(name="Filename (basename)")

    def execute(self, context):
        settings = context.scene.ua_settings
        base_dir = bpy.path.abspath(settings.save_directory)
        proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
        ok = hm.restore_deleted(proj_dir, self.filename)
        if ok:
            self.report({'INFO'}, f"Restored {self.filename} into history/")
        else:
            self.report({'ERROR'}, "Restore failed (see console)")
        return {'FINISHED'}

class UA_OT_PurgeDeleted(bpy.types.Operator):
    bl_idname = "ua.purge_deleted"
    bl_label = "Purge Deleted (older than days)"
    days: bpy.props.IntProperty(name="Older than (days)", default=30, min=0)

    def execute(self, context):
        settings = context.scene.ua_settings
        base_dir = bpy.path.abspath(settings.save_directory)
        proj_dir = hm.project_dir_for(bpy.data.filepath, base_dir)
        removed = hm.purge_deleted_older_than(proj_dir, self.days)
        self.report({'INFO'}, f"Purged {len(removed)} files")
        return {'FINISHED'}

# ---------- Panel ----------
class UA_PT_Panel(bpy.types.Panel):
    bl_label = "Ultimate Autosaver"
    bl_idname = "UA_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ultimate Autosaver"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ua_settings

        layout.prop(settings, "save_directory")
        layout.prop(settings, "autosave_interval")
        layout.prop(settings, "keep_uncompressed")
        layout.prop(settings, "purge_days")
        row = layout.row()
        row.operator("ua.toggle_autosave", text=("Disable Autosave" if settings.enabled else "Enable Autosave"), icon="PLAY")
        layout.operator("ua.manual_backup", icon="FILE_BACKUP")
        layout.separator()
        layout.operator("ua.list_history", icon="TEXT")
        layout.label(text="Manual history ops (use basename from printed list):")
        layout.operator("ua.move_to_deleted", text="Move to Deleted")
        layout.operator("ua.restore_deleted", text="Restore Deleted")
        layout.operator("ua.purge_deleted", text="Purge Deleted")

# ================================================
# Registration
# ================================================

classes = (
    UASettings := UASettings if 'UASettings' in globals() else None,
    UA_OT_ToggleAutosave,
    UA_OT_ManualBackup,
    UA_OT_ListHistory,
    UA_OT_MoveToDeleted,
    UA_OT_RestoreDeleted,
    UA_OT_PurgeDeleted,
    UA_PT_Panel,
)

# Fix UASettings declaration in globals:
def _fix_classes():
    # we created UASettings earlier; ensure correct list
    return (UASettings, UA_OT_ToggleAutosave, UA_OT_ManualBackup,
            UA_OT_ListHistory, UA_OT_MoveToDeleted, UA_OT_RestoreDeleted,
            UA_OT_PurgeDeleted, UA_PT_Panel)

def register():
    for cls in _fix_classes():
        bpy.utils.register_class(cls)
    bpy.types.Scene.ua_settings = bpy.props.PointerProperty(type=UASettings)

def unregister():
    try:
        bpy.app.timers.unregister(_autosave_worker)
    except Exception:
        pass
    for cls in reversed(_fix_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        del bpy.types.Scene.ua_settings
    except Exception:
        pass
