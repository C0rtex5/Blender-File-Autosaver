# ================================================
# Imports
# ================================================

import os
import time
import json
import gzip
import shutil
import glob
from pathlib import Path

# ================================================
# History Manager Functions
# ================================================

def _ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def project_dir_for(blend_path, root_dir):
    """
    root_dir: user-configured base directory for autosaves
    blend_path: absolute path to current .blend file. If empty (unsaved), use 'unsaved' id.
    returns: path for the project history folder
    """
    if not blend_path:
        proj_name = "unsaved_project"
    else:
        proj_name = Path(blend_path).stem
    safe_name = proj_name.replace(" ", "_")
    proj_dir = Path(root_dir) / safe_name
    _ensure_dir(proj_dir)
    return str(proj_dir)

def index_file_for(project_dir):
    return os.path.join(project_dir, "index.json")

def load_index(project_dir):
    idx = index_file_for(project_dir)
    if os.path.exists(idx):
        try:
            with open(idx, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # corrupt index -> rebuild
            return {"versions": []}
    else:
        return {"versions": []}

def save_index(project_dir, data):
    idx = index_file_for(project_dir)
    with open(idx, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def register_version(project_dir, filename, note="auto", compressed=False):
    data = load_index(project_dir)
    entry = {
        "file": os.path.basename(filename),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "size_MB": round(os.path.getsize(filename) / (1024 * 1024), 2) if os.path.exists(filename) else None,
        "note": note,
        "status": "active",
        "compressed": bool(compressed)
    }
    data["versions"].append(entry)
    save_index(project_dir, data)
    return entry

def list_versions(project_dir, include_deleted=False):
    data = load_index(project_dir)
    versions = data.get("versions", [])
    if include_deleted:
        return versions
    return [v for v in versions if v.get("status") != "deleted"]

def save_versioned_copy(bpy_module, project_dir, note="auto"):
    """
    Creates a copy of current .blend into project_dir/history/
    Returns target path or None
    """
    history_dir = os.path.join(project_dir, "history")
    _ensure_dir(history_dir)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    base_name = (Path(bpy_module.data.filepath).stem if bpy_module.data.filepath else "unsaved_project")
    filename = f"{base_name}_{timestamp}.blend"
    target = os.path.join(history_dir, filename)

    # Use Blender operator to save a copy (must be called from main thread / correct context)
    try:
        bpy_module.ops.wm.save_as_mainfile(filepath=target, copy=True)
    except Exception as e:
        # fallback: try saving bpy.data.libraries? but for now just return None
        print(f"[UltimateAutosaver] Failed save_as_mainfile copy: {e}")
        return None

    register_version(project_dir, target, note=note, compressed=False)
    return target

def manual_backup(bpy_module, target_dir, note="manual"):
    _ensure_dir(target_dir)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    base_name = (Path(bpy_module.data.filepath).stem if bpy_module.data.filepath else "unsaved_project")
    filename = f"{base_name}_backup_{timestamp}.blend"
    target = os.path.join(target_dir, filename)
    try:
        bpy_module.ops.wm.save_as_mainfile(filepath=target, copy=True)
    except Exception as e:
        print(f"[UltimateAutosaver] Manual backup failed: {e}")
        return None
    # manual backups stored under /backups in project dir if target_dir is project_dir/backups
    return target

def compress_file(path):
    gz_path = path + ".gz"
    try:
        with open(path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(path)
        return gz_path
    except Exception as e:
        print(f"[UltimateAutosaver] Compression failed for {path}: {e}")
        return None

def compress_old_versions(project_dir, keep_uncompressed=3):
    history_dir = os.path.join(project_dir, "history")
    files = sorted(glob.glob(os.path.join(history_dir, "*.blend")), key=os.path.getmtime, reverse=True)
    for f in files[keep_uncompressed:]:
        gz = compress_file(f)
        if gz:
            # update index entry
            data = load_index(project_dir)
            name = os.path.basename(f)
            for v in data.get("versions", []):
                if v["file"] == name:
                    v["compressed"] = True
                    v["file"] = os.path.basename(gz)
                    v["status"] = v.get("status", "active")
                    break
            save_index(project_dir, data)

def move_to_deleted(project_dir, file_basename):
    history_dir = os.path.join(project_dir, "history")
    deleted_dir = os.path.join(project_dir, "deleted")
    _ensure_dir(deleted_dir)
    src = os.path.join(history_dir, file_basename)
    if not os.path.exists(src):
        # maybe it's compressed already in history
        src = os.path.join(history_dir, file_basename)
        if not os.path.exists(src):
            print(f"[UltimateAutosaver] File not found in history: {file_basename}")
            return False
    dst = os.path.join(deleted_dir, file_basename)
    try:
        shutil.move(src, dst)
    except Exception as e:
        print(f"[UltimateAutosaver] Move to deleted failed: {e}")
        return False
    # update index
    data = load_index(project_dir)
    for v in data.get("versions", []):
        if v["file"] == file_basename:
            v["status"] = "deleted"
            break
    save_index(project_dir, data)
    return True

def restore_deleted(project_dir, file_basename):
    deleted_dir = os.path.join(project_dir, "deleted")
    history_dir = os.path.join(project_dir, "history")
    src = os.path.join(deleted_dir, file_basename)
    if not os.path.exists(src):
        print(f"[UltimateAutosaver] Deleted file not found: {file_basename}")
        return False
    _ensure_dir(history_dir)
    dst = os.path.join(history_dir, file_basename)
    try:
        shutil.move(src, dst)
    except Exception as e:
        print(f"[UltimateAutosaver] Restore failed: {e}")
        return False
    data = load_index(project_dir)
    found = False
    for v in data.get("versions", []):
        if v["file"] == file_basename:
            v["status"] = "active"
            found = True
            break
    if not found:
        # add entry
        data.get("versions", []).append({
            "file": file_basename,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "size_MB": round(os.path.getsize(dst) / (1024 * 1024), 2),
            "note": "restored",
            "status": "active",
            "compressed": dst.endswith(".gz")
        })
    save_index(project_dir, data)
    return True

def purge_deleted_older_than(project_dir, days):
    ddir = os.path.join(project_dir, "deleted")
    now = time.time()
    removed = []
    for f in glob.glob(os.path.join(ddir, "*")):
        if now - os.path.getmtime(f) > days * 86400:
            try:
                os.remove(f)
                removed.append(os.path.basename(f))
            except Exception as e:
                print(f"[UltimateAutosaver] Purge failed for {f}: {e}")
    # update index
    if removed:
        data = load_index(project_dir)
        for name in removed:
            for v in data.get("versions", []):
                if v.get("file") == name:
                    v["status"] = "purged"
        save_index(project_dir, data)
    return removed
