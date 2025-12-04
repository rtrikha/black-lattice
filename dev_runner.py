import os
import time
import subprocess
import sys
from pathlib import Path

# Which files trigger reloads
WATCH_EXTENSIONS = (".py", ".json", ".txt", ".yaml", ".yml")


def get_project_root(script_path: Path) -> Path:
    """
    Heuristic:
    - If the script lives in a 'src' folder, treat the parent as the project root
    - Otherwise, use the script's parent directory
    """
    if script_path.parent.name == "src":
        return script_path.parent.parent
    return script_path.parent


def get_latest_mtime(root: Path) -> float:
    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip junk dirs
        for skip in (".git", ".venv", "__pycache__"):
            if skip in dirnames:
                dirnames.remove(skip)

        for name in filenames:
            if name.endswith(WATCH_EXTENSIONS):
                path = Path(dirpath) / name
                try:
                    mtime = path.stat().st_mtime
                    if mtime > latest:
                        latest = mtime
                except FileNotFoundError:
                    # File may be mid-write; ignore
                    pass
    return latest


def run_loop(script_path: Path, script_args):
    project_root = get_project_root(script_path)

    print(f"Dev runner watching: {project_root}")
    print(f"Running script: {script_path}")
    print(f"With args: {' '.join(script_args) if script_args else '<none>'}")

    last_mtime = get_latest_mtime(project_root)

    while True:
        cmd = ["python3", str(script_path)] + script_args
        print("\n=== Starting process ===")
        print(" ".join(cmd))
        proc = subprocess.Popen(cmd)

        try:
            while True:
                time.sleep(0.5)

                # If script exited, wait for a change then restart
                if proc.poll() is not None:
                    print(f"Process exited with code {proc.returncode}. Waiting for file change to restart…")
                    while True:
                        time.sleep(0.5)
                        current_mtime = get_latest_mtime(project_root)
                        if current_mtime > last_mtime:
                            last_mtime = current_mtime
                            print("🔁 Change detected after exit. Restarting…")
                            break
                    break

                # Live reload: restart when any watched file changes
                current_mtime = get_latest_mtime(project_root)
                if current_mtime > last_mtime:
                    last_mtime = current_mtime
                    print("🔁 Change detected. Restarting process…")
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break

        except KeyboardInterrupt:
            print("\nStopping dev runner…")
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            break


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 dev_runner.py path/to/script.py [script args…]")
        sys.exit(1)

    script = Path(sys.argv[1]).resolve()
    if not script.exists():
        print(f"Script not found: {script}")
        sys.exit(1)

    args = sys.argv[2:]
    run_loop(script, args)