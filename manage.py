#!/usr/bin/env python3
import subprocess
import sys
import os

def start():
    """Start the pumpTUI application."""
    print("Starting pumpTUI...")
    
    # Detect Virtual Environment
    python_exec = sys.executable
    venv_python = os.path.join(os.getcwd(), ".venv", "bin", "python")
    
    if os.path.exists(venv_python):
        print(f"Using Virtual Environment: {venv_python}")
        python_exec = venv_python
    else:
        print(f"Using System Python: {python_exec}")

    try:
        # Run the app's main entry point
        env = os.environ.copy()
        env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"
        subprocess.run([python_exec, "-m", "pump_tui.main"], env=env)
    except KeyboardInterrupt:
        print("\nExiting pumpTUI.")
    except Exception as e:
        print(f"Error starting app: {e}")

def stop():
    """Stop any running pumpTUI processes."""
    print("Searching for running pumpTUI processes...")
    try:
        # Use pkill -f to find processes matching the app module path
        result = subprocess.run(["pkill", "-f", "pump_tui.main"], capture_output=True, text=True)
        if result.returncode == 0:
            print("Successfully stopped pumpTUI.")
        else:
            print("No running pumpTUI processes found.")
    except Exception as e:
        print(f"Error stopping app: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 manage.py [start|stop]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 manage.py [start|stop]")
        sys.exit(1)

if __name__ == "__main__":
    main()
