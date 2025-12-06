#!/usr/bin/env python3
"""
Web Controller for LED Matrix Display

Flask-based web interface to control LED matrix display modes remotely.
Runs on Raspberry Pi and accessible from any device on the network.
"""

import os
import subprocess
import signal
import json
from collections import deque
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from pathlib import Path

app = Flask(__name__)

# In-memory log buffer (keeps last 500 lines)
log_buffer = deque(maxlen=500)
LOG_FILE = Path("/tmp/black_lattice_display.log")

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Handle OPTIONS requests for CORS preflight
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        return response

# Valid display modes
VALID_MODES = ["clock", "weather", "time_weather_calendar", "flight_tracker", "text"]

# Track active processes - only one can run at a time
active_process = None
active_mode = None

# Get project root directory (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.resolve()
MAIN_SCRIPT = PROJECT_ROOT / "src" / "main.py"


def add_log(message: str, level: str = "INFO"):
    """Add a log message to the buffer and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    log_buffer.append(log_entry)
    
    # Also append to file
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + "\n")
    except Exception:
        pass


def read_process_output():
    """Read output from the running process log file."""
    global active_process
    if active_process is None:
        return
    
    try:
        # Read from log file
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                # Read last 100 lines
                lines = f.readlines()[-100:]
                for line in lines:
                    line = line.strip()
                    if line and line not in log_buffer:
                        log_buffer.append(line)
    except Exception:
        pass


def stop_active_mode():
    """Stop the currently active display mode."""
    global active_process, active_mode
    
    if active_process is not None:
        try:
            # Use sudo pkill to kill all main.py processes (handles sudo processes properly)
            subprocess.run(
                ["sudo", "pkill", "-f", "python3.*main.py"],
                timeout=5,
                capture_output=True
            )
            # Wait for the process to terminate
            try:
                active_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                subprocess.run(
                    ["sudo", "pkill", "-9", "-f", "python3.*main.py"],
                    timeout=5,
                    capture_output=True
                )
                active_process.wait(timeout=2)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired) as e:
            # Process already terminated or timeout
            print(f"Process cleanup: {e}")
        finally:
            active_process = None
            active_mode = None
    
    # Also clear the display
    try:
        clear_cmd = ["sudo", "python3", "-c", 
            "import sys; sys.path.insert(0, 'src'); "
            "from utils import load_config, create_matrix; "
            "matrix = create_matrix(load_config()); "
            "matrix.Clear()"]
        subprocess.run(clear_cmd, cwd=PROJECT_ROOT, timeout=10, capture_output=True)
    except Exception as e:
        print(f"Could not clear display: {e}")


def start_mode(mode, message=None, scroll=True, speed=None):
    """
    Start a display mode.
    
    Args:
        mode: Display mode name (must be in VALID_MODES)
        message: Optional message for text mode
        scroll: Whether to scroll text (for text mode)
        speed: Scroll speed in seconds per pixel (for text mode)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    global active_process, active_mode
    
    # Validate mode
    if mode not in VALID_MODES:
        return False, f"Invalid mode: {mode}"
    
    # Stop any currently running mode
    if active_process is not None:
        stop_active_mode()
    
    # Build command - use sudo to run as root for hardware access
    # File permissions should allow root to read config files
    cmd = ["sudo", "python3", str(MAIN_SCRIPT), "--mode", mode]
    
    # Add text mode specific arguments
    if mode == "text":
        if message:
            cmd.extend(["--message", message])
        if not scroll:
            cmd.append("--no-scroll")
        if speed is not None:
            cmd.extend(["--speed", str(speed)])
    
    try:
        add_log(f"Starting command: {' '.join(cmd)}")
        
        # Clear old log file for fresh output
        try:
            with open(LOG_FILE, 'w') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] === Starting {mode} mode ===\n")
        except Exception:
            pass
        
        # Open log file for appending process output
        log_file_handle = open(LOG_FILE, 'a')
        
        # Start process in new process group for proper signal handling
        # Capture output to log file for remote viewing
        active_process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            preexec_fn=os.setsid,  # Create new process group
            stdout=log_file_handle,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
        )
        active_mode = mode
        
        # Process started - we can't easily tell if it will succeed without waiting
        add_log(f"Process started with PID: {active_process.pid}")
        return True, f"Started {mode} mode"
    except Exception as e:
        active_process = None
        active_mode = None
        error_msg = str(e)
        print(f"Error starting {mode}: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, f"Failed to start {mode}: {error_msg}"


@app.route("/")
def index():
    """Serve the main web interface."""
    return render_template("index.html")


@app.route("/api/pi_status")
def pi_status():
    """Check if Pi is online (trivial - if server responds, Pi is online)."""
    return jsonify({"status": "online"})


@app.route("/api/status")
def status():
    """Get status of all modes (which are running)."""
    modes_status = {}
    for mode in VALID_MODES:
        modes_status[mode] = {
            "running": active_mode == mode,
            "active": active_mode == mode
        }
    
    return jsonify({
        "active_mode": active_mode,
        "modes": modes_status
    })


@app.route("/api/start/<mode>", methods=["POST"])
def start(mode):
    """Start a display mode."""
    # Validate mode
    if mode not in VALID_MODES:
        return jsonify({"success": False, "error": f"Invalid mode: {mode}"}), 400
    
    # Get optional parameters for text mode
    message = None
    scroll = True
    speed = None
    
    if mode == "text":
        data = request.get_json() or {}
        message = data.get("message")
        scroll = data.get("scroll", True)
        speed = data.get("speed")
    
    success, msg = start_mode(mode, message=message, scroll=scroll, speed=speed)
    
    if success:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "error": msg}), 500


@app.route("/api/stop/<mode>", methods=["POST"])
def stop(mode):
    """Stop a running mode."""
    # Validate mode
    if mode not in VALID_MODES:
        return jsonify({"success": False, "error": f"Invalid mode: {mode}"}), 400
    
    # Check if this mode is actually running
    if active_mode != mode:
        return jsonify({"success": False, "error": f"{mode} is not currently running"}), 400
    
    stop_active_mode()
    return jsonify({"success": True, "message": f"Stopped {mode} mode"})


@app.route("/api/stop", methods=["POST"])
def stop_all():
    """Stop any currently running mode."""
    if active_process is None:
        return jsonify({"success": False, "error": "No mode is currently running"}), 400
    
    mode = active_mode
    stop_active_mode()
    return jsonify({"success": True, "message": f"Stopped {mode} mode"})


@app.route("/api/clear", methods=["POST"])
def clear_display():
    """Clear/blank the LED display."""
    import subprocess
    try:
        # Stop any running mode first
        stop_active_mode()
        add_log("Display cleared by user request")
        
        # Clear the matrix display
        clear_script = """
import sys
sys.path.insert(0, 'src')
from utils import load_config, create_matrix
matrix = create_matrix(load_config())
matrix.Clear()
"""
        subprocess.run(
            ["sudo", "python3", "-c", clear_script],
            cwd="/home/pi/black-lattice",
            timeout=10,
            capture_output=True
        )
        return jsonify({"success": True, "message": "Display cleared"})
    except Exception as e:
        add_log(f"Failed to clear display: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logs")
def get_logs():
    """Get recent log entries."""
    # Number of lines to return (default 100, max 500)
    lines = request.args.get('lines', 100, type=int)
    lines = min(lines, 500)
    
    # Read from log file
    log_lines = []
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                log_lines = f.readlines()[-lines:]
                log_lines = [line.rstrip() for line in log_lines]
    except Exception as e:
        log_lines = [f"Error reading logs: {e}"]
    
    return jsonify({
        "logs": log_lines,
        "active_mode": active_mode,
        "log_file": str(LOG_FILE)
    })


@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    """Clear the log file."""
    try:
        with open(LOG_FILE, 'w') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Logs cleared\n")
        log_buffer.clear()
        return jsonify({"success": True, "message": "Logs cleared"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def cleanup_on_exit():
    """Cleanup function to stop active process on server shutdown."""
    stop_active_mode()


if __name__ == "__main__":
    import atexit
    atexit.register(cleanup_on_exit)
    
    # Run on all interfaces (0.0.0.0) so it's accessible from network
    # Port 8080 is used to avoid potential blocking of port 5000
    app.run(host="0.0.0.0", port=8080, debug=False)


