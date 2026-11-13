import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger("storage_lifecycle")

RETENTION_SECONDS = 6 * 3600  # 6 Hours


def cleanup_expired_artifacts(base_storage_dir: str = None) -> Dict[str, Any]:
    """
    Purges video files, screenshots, and temporary deliverables older than 6 hours.
    Prevents server disk storage from filling up.
    """
    if not base_storage_dir:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_storage_dir = os.path.join(backend_root, "storage", "artifacts")

    now = time.time()
    cutoff_time = now - RETENTION_SECONDS

    stats = {
        "deleted_videos": 0,
        "deleted_screenshots": 0,
        "deleted_attachments": 0,
        "freed_bytes": 0,
    }

    target_dirs = [
        ("deleted_videos", os.path.join(base_storage_dir, "videos")),
        ("deleted_screenshots", os.path.join(base_storage_dir, "emergent_shots")),
        ("deleted_attachments", os.path.join(os.path.dirname(base_storage_dir), "attachments")),
    ]

    for stat_key, directory in target_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for entry in os.scandir(directory):
                if entry.is_file():
                    try:
                        mtime = entry.stat().st_mtime
                        size = entry.stat().st_size
                        if mtime < cutoff_time:
                            os.remove(entry.path)
                            stats[stat_key] += 1
                            stats["freed_bytes"] += size
                            logger.info(f"Purged expired artifact (>6h old): {entry.path} ({size} bytes)")
                    except Exception as fe:
                        logger.debug(f"Skipping file {entry.path}: {fe}")
        except Exception as de:
            logger.warning(f"Error scanning directory {directory} for cleanup: {de}")

    return stats

