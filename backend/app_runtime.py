"""Frontend build/watch and runtime-monitor helpers extracted from main.py.

These were module-level globals and functions in main.py. Behavior is unchanged;
main.py now delegates frontend-watcher startup and runtime-monitor stop to the
helper functions at the bottom of this module.
"""
import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


# Frontend file watcher
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


def _start_runtime_monitor():
    """Log warning-only threshold crossings for thread growth and AI queue buildup."""
    global runtime_monitor_thread, runtime_monitor_running

    if runtime_monitor_running:
        return

    def monitor_loop():
        from services.ai_stream_service import get_ai_runtime_stats

        thread_level = 0
        task_queue_level = 0
        bg_queue_level = 0

        def get_threshold_level(value: int, thresholds: tuple[int, ...]) -> int:
            level = 0
            for idx, threshold in enumerate(thresholds, start=1):
                if value >= threshold:
                    level = idx
                else:
                    break
            return level

        while runtime_monitor_running:
            try:
                thread_count = _get_current_thread_count()
                ai_stats = get_ai_runtime_stats()

                next_thread_level = get_threshold_level(thread_count, THREAD_WARNING_THRESHOLDS) if thread_count >= 0 else 0
                if next_thread_level > thread_level:
                    threshold = THREAD_WARNING_THRESHOLDS[next_thread_level - 1]
                    logger.warning(
                        "[RuntimeMonitor] Thread count crossed threshold: threads=%s threshold=%s ai_running=%s ai_task_queue=%s ai_bg_queue=%s",
                        thread_count,
                        threshold,
                        ai_stats["running_tasks"],
                        ai_stats["task_queue"],
                        ai_stats["background_queue"],
                    )
                thread_level = next_thread_level

                next_task_queue_level = get_threshold_level(ai_stats["task_queue"], AI_QUEUE_WARNING_THRESHOLDS)
                if next_task_queue_level > task_queue_level:
                    threshold = AI_QUEUE_WARNING_THRESHOLDS[next_task_queue_level - 1]
                    logger.warning(
                        "[RuntimeMonitor] AI task queue crossed threshold: queue=%s threshold=%s running=%s workers=%s threads=%s",
                        ai_stats["task_queue"],
                        threshold,
                        ai_stats["running_tasks"],
                        ai_stats["task_max_workers"],
                        ai_stats["task_threads"],
                    )
                task_queue_level = next_task_queue_level

                next_bg_queue_level = get_threshold_level(ai_stats["background_queue"], AI_QUEUE_WARNING_THRESHOLDS)
                if next_bg_queue_level > bg_queue_level:
                    threshold = AI_QUEUE_WARNING_THRESHOLDS[next_bg_queue_level - 1]
                    logger.warning(
                        "[RuntimeMonitor] AI background queue crossed threshold: queue=%s threshold=%s workers=%s threads=%s",
                        ai_stats["background_queue"],
                        threshold,
                        ai_stats["background_max_workers"],
                        ai_stats["background_threads"],
                    )
                bg_queue_level = next_bg_queue_level

            except Exception as e:
                print(f"[runtime-monitor] non-fatal monitor error: {e}", flush=True)

            time.sleep(RUNTIME_MONITOR_INTERVAL_SECONDS)

    runtime_monitor_running = True
    runtime_monitor_thread = threading.Thread(target=monitor_loop, daemon=True, name="runtime-monitor")
    runtime_monitor_thread.start()

def build_frontend():
    """Build frontend and copy to static directory"""
    global last_build_time
    current_time = time.time()

    # Prevent rapid rebuilds (minimum 5 seconds between builds)
    if current_time - last_build_time < 5:
        return

    try:
        print("Frontend files changed, rebuilding...")
        frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
        static_dir = os.path.join(os.path.dirname(__file__), "static")

        # Build frontend
        result = subprocess.run(
            ["pnpm", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Copy to static directory
            dist_dir = os.path.join(frontend_dir, "dist")
            if os.path.exists(dist_dir):
                # Clear static directory
                if os.path.exists(static_dir):
                    import shutil
                    shutil.rmtree(static_dir)

                # Copy dist to static
                shutil.copytree(dist_dir, static_dir)
                print("Frontend rebuilt and deployed successfully")
                last_build_time = current_time
            else:
                print("ERROR: Frontend dist directory not found after build")
        else:
            print(f"ERROR: Frontend build failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("ERROR: Frontend build timed out")
    except Exception as e:
        print(f"ERROR: Frontend build failed: {e}")

def watch_frontend_files():
    """Watch frontend files for changes"""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if not os.path.exists(frontend_dir):
        return

    # Simple file watcher using modification times
    file_times = {}
    watch_extensions = {'.tsx', '.ts', '.jsx', '.js', '.css', '.html', '.json'}

    def get_file_times():
        times = {}
        for root, dirs, files in os.walk(frontend_dir):
            # Skip node_modules and dist directories
            dirs[:] = [d for d in dirs if d not in ['node_modules', 'dist', '.git']]

            for file in files:
                if any(file.endswith(ext) for ext in watch_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        times[file_path] = os.path.getmtime(file_path)
                    except OSError:
                        pass
        return times

    file_times = get_file_times()

    while True:
        try:
            time.sleep(2)  # Check every 2 seconds
            current_times = get_file_times()

            # Check for changes
            changed = False
            for file_path, mtime in current_times.items():
                if file_path not in file_times or file_times[file_path] != mtime:
                    changed = True
                    break

            # Check for deleted files
            if not changed:
                for file_path in file_times:
                    if file_path not in current_times:
                        changed = True
                        break

            if changed:
                file_times = current_times
                build_frontend()

        except Exception as e:
            print(f"Frontend watcher error: {e}")
            time.sleep(5)


def start_frontend_watcher():
    """Start the frontend file watcher in a background daemon thread."""
    global frontend_watcher_thread
    frontend_watcher_thread = threading.Thread(target=watch_frontend_files, daemon=True)
    frontend_watcher_thread.start()


def stop_runtime_monitor():
    """Signal the runtime monitor loop to stop."""
    global runtime_monitor_running
    runtime_monitor_running = False
