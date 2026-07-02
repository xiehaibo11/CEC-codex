"""Runtime monitor and local frontend build watcher."""
import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

frontend_watcher_thread = None
runtime_monitor_thread = None
runtime_monitor_running = False
last_build_time = 0

THREAD_WARNING_THRESHOLDS = (200, 400, 800, 1200)
AI_QUEUE_WARNING_THRESHOLDS = (8, 16, 32)
RUNTIME_MONITOR_INTERVAL_SECONDS = int(os.getenv("RUNTIME_MONITOR_INTERVAL_SECONDS", "300"))


def _get_current_thread_count() -> int:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Threads:"):
                    return int(line.split()[1])
    except Exception:
        return -1
    return -1


def start_runtime_monitor() -> None:
    """Log warning-only threshold crossings for thread growth and AI queue buildup."""
    global runtime_monitor_thread, runtime_monitor_running

    if runtime_monitor_running:
        return

    runtime_monitor_running = True
    runtime_monitor_thread = threading.Thread(
        target=_runtime_monitor_loop,
        daemon=True,
        name="runtime-monitor",
    )
    runtime_monitor_thread.start()
    print("Runtime monitor started")


def stop_runtime_monitor() -> None:
    global runtime_monitor_running
    runtime_monitor_running = False


def _runtime_monitor_loop() -> None:
    from services.ai_stream_service import get_ai_runtime_stats

    thread_level = 0
    task_queue_level = 0
    bg_queue_level = 0

    while runtime_monitor_running:
        try:
            thread_count = _get_current_thread_count()
            ai_stats = get_ai_runtime_stats()

            thread_level = _log_thread_threshold(thread_count, ai_stats, thread_level)
            task_queue_level = _log_queue_threshold(
                "task",
                ai_stats["task_queue"],
                ai_stats,
                task_queue_level,
            )
            bg_queue_level = _log_queue_threshold(
                "background",
                ai_stats["background_queue"],
                ai_stats,
                bg_queue_level,
            )
        except Exception as err:
            print(f"[runtime-monitor] non-fatal monitor error: {err}", flush=True)

        time.sleep(RUNTIME_MONITOR_INTERVAL_SECONDS)


def _threshold_level(value: int, thresholds: tuple[int, ...]) -> int:
    level = 0
    for idx, threshold in enumerate(thresholds, start=1):
        if value >= threshold:
            level = idx
        else:
            break
    return level


def _log_thread_threshold(thread_count: int, ai_stats: dict, previous_level: int) -> int:
    next_level = _threshold_level(thread_count, THREAD_WARNING_THRESHOLDS) if thread_count >= 0 else 0
    if next_level > previous_level:
        threshold = THREAD_WARNING_THRESHOLDS[next_level - 1]
        logger.warning(
            "[RuntimeMonitor] Thread count crossed threshold: threads=%s threshold=%s ai_running=%s ai_task_queue=%s ai_bg_queue=%s",
            thread_count,
            threshold,
            ai_stats["running_tasks"],
            ai_stats["task_queue"],
            ai_stats["background_queue"],
        )
    return next_level


def _log_queue_threshold(queue_name: str, queue_size: int, ai_stats: dict, previous_level: int) -> int:
    next_level = _threshold_level(queue_size, AI_QUEUE_WARNING_THRESHOLDS)
    if next_level <= previous_level:
        return next_level

    threshold = AI_QUEUE_WARNING_THRESHOLDS[next_level - 1]
    if queue_name == "task":
        logger.warning(
            "[RuntimeMonitor] AI task queue crossed threshold: queue=%s threshold=%s running=%s workers=%s threads=%s",
            queue_size,
            threshold,
            ai_stats["running_tasks"],
            ai_stats["task_max_workers"],
            ai_stats["task_threads"],
        )
    else:
        logger.warning(
            "[RuntimeMonitor] AI background queue crossed threshold: queue=%s threshold=%s workers=%s threads=%s",
            queue_size,
            threshold,
            ai_stats["background_max_workers"],
            ai_stats["background_threads"],
        )
    return next_level


def build_frontend() -> None:
    """Build frontend and copy to static directory."""
    global last_build_time
    current_time = time.time()

    if current_time - last_build_time < 5:
        return

    try:
        print("Frontend files changed, rebuilding...")
        frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        result = subprocess.run(
            ["pnpm", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            _copy_frontend_dist(frontend_dir, static_dir)
        else:
            print(f"ERROR: Frontend build failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("ERROR: Frontend build timed out")
    except Exception as err:
        print(f"ERROR: Frontend build failed: {err}")


def _copy_frontend_dist(frontend_dir: str, static_dir: str) -> None:
    global last_build_time
    import shutil

    dist_dir = os.path.join(frontend_dir, "dist")
    if not os.path.exists(dist_dir):
        print("ERROR: Frontend dist directory not found after build")
        return

    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)
    shutil.copytree(dist_dir, static_dir)
    print("Frontend rebuilt and deployed successfully")
    last_build_time = time.time()


def start_frontend_watcher() -> None:
    global frontend_watcher_thread
    frontend_watcher_thread = threading.Thread(target=watch_frontend_files, daemon=True)
    frontend_watcher_thread.start()
    print("Frontend file watcher started")


def watch_frontend_files() -> None:
    """Watch frontend files for changes."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if not os.path.exists(frontend_dir):
        return

    file_times = _get_frontend_file_times(frontend_dir)
    while True:
        try:
            time.sleep(2)
            current_times = _get_frontend_file_times(frontend_dir)
            if _frontend_files_changed(file_times, current_times):
                file_times = current_times
                build_frontend()
        except Exception as err:
            print(f"Frontend watcher error: {err}")
            time.sleep(5)


def _get_frontend_file_times(frontend_dir: str) -> dict:
    watch_extensions = {".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".json"}
    times = {}
    for root, dirs, files in os.walk(frontend_dir):
        dirs[:] = [d for d in dirs if d not in ["node_modules", "dist", ".git"]]
        for file in files:
            if not any(file.endswith(ext) for ext in watch_extensions):
                continue
            file_path = os.path.join(root, file)
            try:
                times[file_path] = os.path.getmtime(file_path)
            except OSError:
                pass
    return times


def _frontend_files_changed(previous_times: dict, current_times: dict) -> bool:
    for file_path, mtime in current_times.items():
        if file_path not in previous_times or previous_times[file_path] != mtime:
            return True
    for file_path in previous_times:
        if file_path not in current_times:
            return True
    return False
