"""
StarStream Downloader - Cache & Temp Files Cleaner
清理下载残留临时切片、分块碎片文件与历史记录
"""
import os
import shutil
import time
from .config import config, APP_DIR, ROOT_DIR, get_temp_segments_dir
from .task_manager import task_manager


TEMP_EXTENSIONS = {".tmp", ".part", ".aria2", ".ytdl", ".ts.tmp"}


def is_segment_folder(dir_path):
    """判断某个目录是否为 N_m3u8DL-RE 或流媒体下载产生的临时分片目录"""
    if not os.path.isdir(dir_path):
        return False
    try:
        names = os.listdir(dir_path)
        # N_m3u8DL-RE 特征：包含 meta.json, raw.m3u8, 0____ 或多个 .ts 切片
        if any(fn in names for fn in ["meta.json", "meta_selected.json", "raw.m3u8", "0____"]):
            return True
        ts_count = sum(1 for fn in names if fn.lower().endswith(".ts") or fn.lower().endswith(".m4s"))
        if ts_count > 0:
            return True
        for sub in names:
            sub_p = os.path.join(dir_path, sub)
            if os.path.isdir(sub_p):
                sub_names = os.listdir(sub_p)
                if any(fn.lower().endswith(".ts") or fn.lower().endswith(".m4s") for fn in sub_names):
                    return True
    except Exception:
        pass
    return False


def get_fragment_folders():
    """
    全面扫描专用分片目录 Temp_Segments 以及根目录残留的分片文件夹
    返回列表: [{ "name", "path", "size", "ts_count", "mod_time", "is_orphan" }]
    """
    temp_dir = get_temp_segments_dir()
    results = []

    def inspect_dir(d_path, is_orphan=False):
        try:
            total_sz = 0
            ts_cnt = 0
            for root, _, files in os.walk(d_path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_sz += os.path.getsize(fp)
                    except Exception:
                        pass
                    if f.lower().endswith(".ts") or f.lower().endswith(".m4s"):
                        ts_cnt += 1
            mtime = os.path.getmtime(d_path)
            mod_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            results.append({
                "name": os.path.basename(d_path),
                "path": d_path,
                "size": total_sz,
                "ts_count": ts_cnt,
                "mod_time": mod_str,
                "is_orphan": is_orphan
            })
        except Exception:
            pass

    # 1. 扫描专用 Temp_Segments 目录下的所有子文件夹
    if os.path.exists(temp_dir):
        try:
            for item in os.listdir(temp_dir):
                item_p = os.path.join(temp_dir, item)
                if os.path.isdir(item_p):
                    inspect_dir(item_p, is_orphan=False)
        except Exception:
            pass

    # 2. 扫描软件根目录下的残留未整理分片文件夹
    try:
        ignore_names = {"catcatch_app", "m3u8-sniffer-extension", "Downloads", "Logs", "Temp_Segments",
                        "build", "dist", "docs", ".claude", ".superpowers", "__pycache__"}
        for item in os.listdir(ROOT_DIR):
            if item in ignore_names:
                continue
            item_p = os.path.join(ROOT_DIR, item)
            if os.path.isdir(item_p) and is_segment_folder(item_p):
                inspect_dir(item_p, is_orphan=True)
    except Exception:
        pass

    return results


def delete_fragment_folder(folder_path):
    """删除指定的分片文件夹"""
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)
        return True
    return False


def clean_all_fragment_folders():
    """一键清空全部残留的分片临时切片文件夹"""
    folders = get_fragment_folders()
    freed = 0
    cnt = 0
    for f in folders:
        p = f["path"]
        sz = f["size"]
        if delete_fragment_folder(p):
            freed += sz
            cnt += 1
    return {"freed_bytes": freed, "deleted_count": cnt}


def scan_cache(target_dir=None):
    """
    扫描目标目录、专用分片目录与残留项中的下载缓存与分片临时文件
    """
    if not target_dir:
        target_dir = config.get("save_dir")

    found_files = []
    found_dirs = []
    total_bytes = 0

    scan_roots = []
    if target_dir and os.path.exists(target_dir):
        scan_roots.append(target_dir)
    temp_dir = get_temp_segments_dir()
    if temp_dir and os.path.exists(temp_dir) and temp_dir not in scan_roots:
        scan_roots.append(temp_dir)

    for s_dir in scan_roots:
        try:
            for root, dirs, files in os.walk(s_dir):
                for d in list(dirs):
                    d_lower = d.lower()
                    if d_lower.endswith(".tmp") or "_tmp" in d_lower or d_lower == "temp" or d_lower.endswith("_chunks") or is_segment_folder(os.path.join(root, d)):
                        dir_path = os.path.join(root, d)
                        dir_sz = 0
                        try:
                            for sub_root, _, sub_files in os.walk(dir_path):
                                for sf in sub_files:
                                    try:
                                        dir_sz += os.path.getsize(os.path.join(sub_root, sf))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        found_dirs.append({
                            "path": dir_path,
                            "name": d,
                            "size": dir_sz
                        })
                        total_bytes += dir_sz

                for f in files:
                    f_lower = f.lower()
                    is_temp = False
                    for ext in TEMP_EXTENSIONS:
                        if f_lower.endswith(ext) or ".part" in f_lower or f_lower.endswith(".downloading"):
                            is_temp = True
                            break
                    if not is_temp and f_lower.endswith(".ts") and ("tmp" in root.lower() or "temp" in root.lower() or "segment" in root.lower()):
                        is_temp = True

                    if is_temp:
                        file_path = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(file_path)
                        except Exception:
                            sz = 0
                        found_files.append({
                            "path": file_path,
                            "name": f,
                            "size": sz
                        })
                        total_bytes += sz
        except Exception as e:
            print(f"[CacheCleaner] 扫描异常: {e}")

    # 同时将根目录残留的 orphan 分片纳入
    frag_folders = get_fragment_folders()
    for ff in frag_folders:
        if ff.get("is_orphan"):
            found_dirs.append({
                "path": ff["path"],
                "name": ff["name"],
                "size": ff["size"]
            })
            total_bytes += ff["size"]

    tasks = task_manager.get_all_tasks()
    completed_count = sum(1 for t in tasks if t.get("status") == "completed")
    error_count = sum(1 for t in tasks if t.get("status") == "error")

    return {
        "temp_files": found_files,
        "temp_dirs": found_dirs,
        "total_files": len(found_files) + len(found_dirs),
        "total_bytes": total_bytes,
        "completed_tasks": completed_count,
        "error_tasks": error_count
    }


def clean_cache(target_dir=None, clean_temp_files=True, clean_completed_tasks=False, clean_error_tasks=False):
    """
    执行缓存与临时文件清理
    """
    stats = scan_cache(target_dir)
    freed_bytes = 0
    deleted_files_count = 0
    cleared_tasks_count = 0

    if clean_temp_files:
        # 删除临时文件
        for item in stats["temp_files"]:
            p = item["path"]
            if os.path.exists(p):
                try:
                    os.remove(p)
                    freed_bytes += item["size"]
                    deleted_files_count += 1
                except Exception as e:
                    print(f"[CacheCleaner] 删除文件失败 {p}: {e}")

        # 删除临时文件夹
        for item in stats["temp_dirs"]:
            p = item["path"]
            if os.path.exists(p):
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    freed_bytes += item["size"]
                    deleted_files_count += 1
                except Exception as e:
                    print(f"[CacheCleaner] 删除目录失败 {p}: {e}")

    # 清理已完成或失败的任务列表记录
    if clean_completed_tasks or clean_error_tasks:
        tasks = task_manager.get_all_tasks()
        to_remove = []
        for t in tasks:
            st = t.get("status")
            if clean_completed_tasks and st == "completed":
                to_remove.append(t["id"])
            elif clean_error_tasks and st == "error":
                to_remove.append(t["id"])

        for t_id in to_remove:
            task_manager.remove_task(t_id, delete_file=False)
            cleared_tasks_count += 1

    return {
        "freed_bytes": freed_bytes,
        "deleted_files_count": deleted_files_count,
        "cleared_tasks_count": cleared_tasks_count
    }
