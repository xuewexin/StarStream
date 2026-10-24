"""
StarStream Downloader - Cache & Temp Files Cleaner
清理下载残留临时切片、分块碎片文件与历史记录
"""
import os
import shutil
from .config import config, APP_DIR
from .task_manager import task_manager


TEMP_EXTENSIONS = {".tmp", ".part", ".aria2", ".ytdl", ".ts.tmp"}


def scan_cache(target_dir=None):
    """
    扫描目标目录中的下载缓存与分片临时文件
    """
    if not target_dir:
        target_dir = config.get("save_dir")

    found_files = []
    found_dirs = []
    total_bytes = 0

    if not target_dir or not os.path.exists(target_dir):
        return {
            "temp_files": [],
            "temp_dirs": [],
            "total_files": 0,
            "total_bytes": 0,
            "completed_tasks": sum(1 for t in task_manager.get_all_tasks() if t.get("status") == "completed"),
            "error_tasks": sum(1 for t in task_manager.get_all_tasks() if t.get("status") == "error")
        }

    try:
        for root, dirs, files in os.walk(target_dir):
            # 扫描临时文件夹 (如 _tmp, .tmp, temp)
            for d in list(dirs):
                d_lower = d.lower()
                if d_lower.endswith(".tmp") or "_tmp" in d_lower or d_lower == "temp" or d_lower.endswith("_chunks"):
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

            # 扫描临时文件
            for f in files:
                f_lower = f.lower()
                is_temp = False
                for ext in TEMP_EXTENSIONS:
                    if f_lower.endswith(ext) or ".part" in f_lower or f_lower.endswith(".downloading"):
                        is_temp = True
                        break
                
                # N_m3u8DL-RE 产生的临时切片目录内的 .ts 文件
                if not is_temp and f_lower.endswith(".ts") and ("tmp" in root.lower() or "temp" in root.lower()):
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
