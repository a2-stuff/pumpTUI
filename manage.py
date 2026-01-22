#!/usr/bin/env python3
import subprocess
import sys
import os

def start(use_docker=False):
    """Start the pumpTUI application."""
    if use_docker:
        start_docker()
    else:
        start_local()

def start_local():
    """Start the app locally."""
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

def start_docker():
    """Start the app in Docker."""
    print("Starting pumpTUI in Docker...")
    
    # Check if Docker is installed
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        subprocess.run(["docker-compose", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Docker or docker-compose is not installed.")
        print("Please install Docker Desktop or Docker Engine + docker-compose.")
        sys.exit(1)
    
    # Check if .env file exists
    if not os.path.exists(".env"):
        print("⚠️  Warning: .env file not found. Creating from .env.example...")
        if os.path.exists(".env.example"):
            subprocess.run(["cp", ".env.example", ".env"])
            print("✅ Created .env file. Please configure it before running again.")
            sys.exit(0)
        else:
            print("❌ Error: Neither .env nor .env.example found.")
            sys.exit(1)
    
    # Check if container already exists
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=pumptui-app", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    
    container_exists = "pumptui-app" in result.stdout
    
    if container_exists:
        # Check if it's running
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=pumptui-app", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        is_running = "pumptui-app" in result.stdout
        
        if is_running:
            print("✅ Container is already running. Attaching...")
            print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
            subprocess.run(["docker", "attach", "pumptui-app"])
        else:
            print("🔄 Starting existing container...")
            subprocess.run(["docker-compose", "start", "app"])
            print("✅ Container started. Attaching...")
            print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
            subprocess.run(["docker", "attach", "pumptui-app"])
    else:
        print("🔨 Building and creating containers for the first time...")
        print("   This may take a few minutes...")
        
        # Build and start with compose
        result = subprocess.run(["docker-compose", "up", "-d", "--build"])
        
        if result.returncode == 0:
            print("✅ Containers created and started successfully!")
            print("🔗 Attaching to pumpTUI app...")
            print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
            
            # Wait a moment for the container to fully start
            import time
            time.sleep(2)
            
            subprocess.run(["docker", "attach", "pumptui-app"])
        else:
            print("❌ Failed to start containers. Check logs with: docker-compose logs")
            sys.exit(1)

def stop(use_docker=False):
    """Stop any running pumpTUI processes."""
    if use_docker:
        stop_docker()
    else:
        stop_local()

def stop_local():
    """Stop local processes."""
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

def stop_docker():
    """Stop Docker containers."""
    print("Stopping pumpTUI Docker containers...")
    result = subprocess.run(["docker-compose", "stop"])
    
    if result.returncode == 0:
        print("✅ Containers stopped successfully.")
        print("💡 Data is preserved. Run 'python3 manage.py start --docker' to restart.")
    else:
        print("❌ Failed to stop containers.")
        sys.exit(1)

def clean_docker():
    """Clean up Docker containers and volumes."""
    print("⚠️  This will remove all pumpTUI containers, networks, and volumes.")
    print("⚠️  All data including MongoDB database will be DELETED.")
    
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    print("🗑️  Removing containers and volumes...")
    subprocess.run(["docker-compose", "down", "-v"])
    
    # Also remove the built image
    subprocess.run(["docker", "rmi", "pumptui:latest"], capture_output=True)
    
    print("✅ Cleanup complete. All Docker resources removed.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 manage.py [start|stop|clean] [--docker]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    use_docker = "--docker" in sys.argv
    
    if cmd == "start":
        start(use_docker)
    elif cmd == "stop":
        stop(use_docker)
    elif cmd == "clean":
        if use_docker:
            clean_docker()
        else:
            print("The 'clean' command is only available with --docker flag.")
            print("Usage: python3 manage.py clean --docker")
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 manage.py [start|stop|clean] [--docker]")
        sys.exit(1)

if __name__ == "__main__":
    main()

