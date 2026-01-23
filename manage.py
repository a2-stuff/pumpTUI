#!/usr/bin/env python3
import subprocess
import sys
import os
import time

def start(use_docker=False):
    """Start the pumpTUI application."""
    if use_docker:
        start_docker()
    else:
        start_local()

def check_dependencies(python_exec):
    """Check if critical dependencies are installed."""
    print("Checking dependencies...")
    required = ["textual", "motor", "websockets", "httpx", "psutil", "rich"]
    missing = []
    
    for pkg in required:
        try:
            subprocess.run(
                [python_exec, "-c", f"import {pkg}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except subprocess.CalledProcessError:
            missing.append(pkg)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print(f"\n💡 Install with: pip install {' '.join(missing)}")
        print("   Or: poetry install")
        return False
    
    print("✅ All dependencies installed")
    return True

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
    
    # Check dependencies
    if not check_dependencies(python_exec):
        sys.exit(1)

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
        subprocess.run(["docker", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["docker-compose", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Docker or docker-compose is not installed.")
        print("Please install Docker Desktop or Docker Engine + docker-compose.")
        sys.exit(1)
    
    # Test Docker permissions
    docker_prefix = []
    try:
        subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        print("❌ Error: Permission denied accessing Docker.")
        print("\n💡 Solution: Run with sudo")
        print("   sudo python3 manage.py start --docker")
        print("\nAttempting to continue with sudo...")
        docker_prefix = ["sudo"]
        
        # Test sudo works
        try:
            subprocess.run(["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError:
            # Need password
            print("Please enter your password:")
            try:
                subprocess.run(["sudo", "true"], check=True)
            except:
                print("❌ Authentication failed")
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
    
    # Check container status
    check_result = subprocess.run(
        docker_prefix + ["docker", "ps", "-a", "--filter", "name=app", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True
    )
    
    container_info = check_result.stdout.strip()
    container_name = None
    container_status = ""
    
    if container_info:
        # Parse the container name and status
        lines = container_info.split('\n')
        for line in lines:
            if 'app' in line:
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    container_name = parts[0]
                    container_status = parts[1]
                    break
    
    # Check if image exists
    image_check = subprocess.run(
        docker_prefix + ["docker", "images", "-q", "pumptui:latest"],
        capture_output=True,
        text=True
    )
    image_exists = bool(image_check.stdout.strip())
    
    if container_status.startswith("Up"):
        print("✅ PumpTUI is already running!")
        print("🔗 Attaching to session...")
        print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
        try:
            subprocess.run(docker_prefix + ["docker", "attach", container_name])
        except KeyboardInterrupt:
            print("\nDetached from session. App is still running.")
    elif container_status.startswith("Exited") or container_status.startswith("Created"):
        print("🔄 Starting existing containers...")
        result = subprocess.run(docker_prefix + ["docker-compose", "start"])
        if result.returncode == 0:
            print("✅ PumpTUI is running!")
            print("🔗 Attaching to session...")
            print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
            import time
            time.sleep(2)
            # Get the container name again after starting
            check_result2 = subprocess.run(
                docker_prefix + ["docker", "ps", "--filter", "name=app", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            container_name = check_result2.stdout.strip().split('\n')[0]
            try:
                subprocess.run(docker_prefix + ["docker", "attach", container_name])
            except KeyboardInterrupt:
                print("\nDetached from session. App is still running.")
        else:
            print("❌ Failed to start containers.")
            cmd_prefix = "sudo " if docker_prefix else ""
            print(f"Check logs with: {cmd_prefix}docker-compose logs")
            sys.exit(1)
    else:
        # No existing container or image needs building
        if not image_exists:
            print("📦 Building Docker image (first time setup)...")
        else:
            print("🔄 Creating containers...")
        
        # Remove any old containers with stale image references
        subprocess.run(
            docker_prefix + ["docker-compose", "rm", "-f"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Build and start
        build_flag = ["--build"] if not image_exists else []
        result = subprocess.run(docker_prefix + ["docker-compose", "up", "-d"] + build_flag)
        
        if result.returncode == 0:
            print("✅ PumpTUI is running!")
            print("🔗 Attaching to session...")
            print("💡 Tip: Press Ctrl+P then Ctrl+Q to detach without stopping.")
            
            # Wait a moment for startup
            import time
            time.sleep(2)
            
            # Get the actual container name
            check_result3 = subprocess.run(
                docker_prefix + ["docker", "ps", "--filter", "name=app", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            container_name = check_result3.stdout.strip().split('\n')[0]
            
            try:
                subprocess.run(docker_prefix + ["docker", "attach", container_name])
            except KeyboardInterrupt:
                print("\nDetached from session. App is still running.")
        else:
            print("❌ Failed to start containers.")
            cmd_prefix = "sudo " if docker_prefix else ""
            print(f"Check logs with: {cmd_prefix}docker-compose logs")
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
    
    # Check if we need sudo
    docker_prefix = []
    try:
        subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        docker_prefix = ["sudo"]
    
    result = subprocess.run(docker_prefix + ["docker-compose", "stop"])
    
    if result.returncode == 0:
        print("✅ Containers stopped successfully.")
        print("💡 Data is preserved. Run 'python3 manage.py start --docker' to restart.")
    else:
        print("❌ Failed to stop containers.")
        sys.exit(1)

def rebuild_docker():
    """Rebuild the Docker image with latest code changes."""
    print("🔨 Rebuilding pumpTUI Docker image...")
    
    # Check if we need sudo
    docker_prefix = []
    try:
        subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        docker_prefix = ["sudo"]
        try:
            subprocess.run(["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError:
            print("Please enter your password:")
            try:
                subprocess.run(["sudo", "true"], check=True)
            except:
                print("❌ Authentication failed")
                sys.exit(1)
    
    print("📦 Stopping containers...")
    subprocess.run(docker_prefix + ["docker-compose", "stop"])
    
    print("🗑️  Removing old containers...")
    subprocess.run(docker_prefix + ["docker-compose", "rm", "-f"])
    
    print("🔨 Building new image...")
    result = subprocess.run(docker_prefix + ["docker-compose", "build", "--no-cache"])
    
    if result.returncode == 0:
        print("✅ Rebuild complete!")
        print("\n💡 Start the app with: python3 manage.py start --docker")
    else:
        print("❌ Build failed.")
        sys.exit(1)

def clean_docker():
    """Clean up Docker containers and volumes."""
    print("⚠️  This will remove all pumpTUI containers, networks, and volumes.")
    print("⚠️  All data including MongoDB database will be DELETED.")
    
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    # Check if we need sudo
    docker_prefix = []
    try:
        subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        docker_prefix = ["sudo"]
    
    print("🗑️  Removing containers and volumes...")
    subprocess.run(docker_prefix + ["docker-compose", "down", "-v"])
    
    # Also remove the built image
    subprocess.run(docker_prefix + ["docker", "rmi", "pumptui:latest"], capture_output=True)
    
    print("✅ Cleanup complete. All Docker resources removed.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 manage.py [start|stop|rebuild|clean] [--docker]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    use_docker = "--docker" in sys.argv
    
    if cmd == "start":
        start(use_docker)
    elif cmd == "stop":
        stop(use_docker)
    elif cmd == "rebuild":
        if use_docker:
            rebuild_docker()
        else:
            print("The 'rebuild' command is only available with --docker flag.")
            print("Usage: python3 manage.py rebuild --docker")
    elif cmd == "clean":
        if use_docker:
            clean_docker()
        else:
            print("The 'clean' command is only available with --docker flag.")
            print("Usage: python3 manage.py clean --docker")
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 manage.py [start|stop|rebuild|clean] [--docker]")
        sys.exit(1)

if __name__ == "__main__":
    main()
