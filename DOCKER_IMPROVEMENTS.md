# Docker Management Improvements

## Problem Fixed

**Original Issue**: The Docker startup was always running with `--build` flag, which could:
- Prompt to recreate containers when there were image reference issues
- Risk losing data during container recreation
- Take longer than necessary to start

## Solution Implemented

The `manage.py` script has been improved with intelligent container management:

### Smart Container Detection

The script now:
1. **Checks if containers are already running** → Simply attaches
2. **Checks if containers exist but are stopped** → Starts them (no rebuild)
3. **Only builds when necessary** → First time or when image is missing

### Key Benefits

✅ **Data Safety**: No more prompts to recreate containers  
✅ **Faster Startups**: Only rebuilds when actually needed  
✅ **Wallet Protection**: Your MongoDB data is always preserved in the `pumptui-mongodb` volume  
✅ **Better UX**: Clear messaging about what's happening

## New Commands

### `start --docker`
Intelligently starts your application:
- If running → Attaches
- If stopped → Restarts existing containers
- If missing → Creates new containers

```bash
python3 manage.py start --docker
# or with sudo
sudo python3 manage.py start --docker
```

### `stop --docker`
Stops containers while preserving ALL data:
```bash
python3 manage.py stop --docker
```

### `rebuild --docker` (NEW!)
When you actually want to rebuild with code changes:
```bash
python3 manage.py rebuild --docker
```

This command:
- Stops containers
- Removes old containers
- Rebuilds image with `--no-cache`
- **Preserves MongoDB data in volume**

### `clean --docker`
⚠️ **DESTRUCTIVE** - Removes everything including data:
```bash
python3 manage.py clean --docker
```

## Data Persistence

Your wallet and settings data is **ALWAYS SAFE** because it's stored in the Docker volume `pumptui-mongodb`, which persists through:
- Container stops
- Container recreation
- Image rebuilds
- System reboots

Only the `clean --docker` command will delete this data (and it asks for confirmation first).

## Verify Your Data Volume

To check your MongoDB volume exists:
```bash
sudo docker volume ls | grep pumptui
sudo docker volume inspect pumptui-mongodb
```

Your data is stored at: `/var/lib/docker/volumes/pumptui-mongodb/_data`

## Typical Workflow

### Daily Use
```bash
# Start the app
sudo python3 manage.py start --docker

# Use the app...

# Stop when done (or just detach with Ctrl+P, Ctrl+Q)
sudo python3 manage.py stop --docker
```

### After Code Changes
```bash
# Rebuild the image
sudo python3 manage.py rebuild --docker

# Start with new code
sudo python3 manage.py start --docker
```

### Complete Reset (Fresh Start)
```bash
# Remove everything
sudo python3 manage.py clean --docker

# Start fresh
sudo python3 manage.py start --docker
```

## What Changed in manage.py

1. **Container status detection** - Checks if containers are Up/Exited/Missing
2. **Image existence check** - Only builds if image doesn't exist
3. **Dynamic container name handling** - Works with prefixed container names
4. **Separate rebuild command** - Explicit control over when to rebuild
5. **Better error messages** - Clear feedback about what's happening

## Migration Notes

If you had issues before this fix:
1. Your data is safe in the `pumptui-mongodb` volume
2. Run `sudo python3 manage.py start --docker` - it will detect existing containers
3. If you get errors, run `sudo python3 manage.py rebuild --docker` to start fresh (data preserved)
