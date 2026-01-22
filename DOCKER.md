# Docker Deployment Guide

This guide explains how to run pumpTUI in Docker containers with zero localhost dependencies.

## Quick Start

### First Time Setup

1. **Ensure Docker is installed**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Configure environment**
   ```bash
   # Copy .env.example to .env (if not exists)
   cp .env.example .env
   
   # Edit .env with your configuration
   nano .env  # or your preferred editor
   ```

3. **Start the application**
   ```bash
   python3 manage.py start --docker
   ```
   
   This will:
   - Build the Alpine-based Docker image (~150MB)
   - Create a MongoDB container with persistent storage
   - Start the pumpTUI application
   - Attach you to the running TUI

### Subsequent Runs

After the first setup, simply run:
```bash
python3 manage.py start --docker
```

The system will detect existing containers and either:
- Attach if already running
- Start and attach if stopped
- Rebuild only if image is missing

## Container Management

### Detach Without Stopping

While running in Docker, you can detach without stopping the app:
```
Press: Ctrl+P, then Ctrl+Q
```

The app continues running in the background. Reconnect anytime with:
```bash
python3 manage.py start --docker
```

### Stop Containers

```bash
python3 manage.py stop --docker
```

This stops both containers but **preserves all data**.

### Complete Cleanup

⚠️ **Warning**: This removes ALL data including MongoDB database!

```bash
python3 manage.py clean --docker
```

You'll be asked to confirm before deletion.

## Architecture

### Containers

1. **pumptui-mongo** (MongoDB 7 Alpine)
   - Stores all token data, settings, and wallets
   - Data persists in Docker volume `pumptui-mongodb`

2. **pumptui-app** (Python 3.12 Alpine)
   - Runs the Textual TUI application
   - Connects to MongoDB via internal network

### Persistent Data

| Type | Location | Purpose |
|------|----------|---------|
| MongoDB Data | Volume: `pumptui-mongodb` | Database storage |
| CSV Tokens | Mount: `./tokensdb/` | Daily token CSV files |
| Logs | Mounts: `./error.log`, `./debug_*.log` | Application logs |
| Config | Mount: `./.env` (read-only) | Environment variables |

### Networking

- Containers communicate via `pumptui-net` network
- MongoDB accessible to app as `mongodb://mongodb:27017`
- Isolated from host network (no port exposure needed)

## Troubleshooting

### View Logs

```bash
# All services
docker-compose logs

# Just the app
docker-compose logs app

# Just MongoDB
docker-compose logs mongodb

# Follow live logs
docker-compose logs -f app
```

### Rebuild Image

If you modify the code or dependencies:
```bash
# Stop containers
python3 manage.py stop --docker

# Rebuild and start
docker-compose up -d --build

# Or use manage.py
python3 manage.py start --docker
```

### Check Container Status

```bash
# List all pumpTUI containers
docker ps -a | grep pumptui

# Check if running
docker ps | grep pumptui
```

### MongoDB Connection Issues

If the app can't connect to MongoDB:

1. Check MongoDB is healthy:
   ```bash
   docker-compose ps
   ```

2. Verify network:
   ```bash
   docker network inspect pumptui-net
   ```

3. Restart MongoDB:
   ```bash
   docker-compose restart mongodb
   ```

## Advanced Usage

### Access MongoDB Directly

```bash
# Connect to MongoDB shell
docker exec -it pumptui-mongo mongosh

# View databases
show dbs

# Use pumpTUI database
use pumptui

# Show collections
show collections
```

### Manual Container Management

```bash
# Start without attaching
docker-compose up -d

# Attach to running container
docker attach pumptui-app

# Execute commands in container
docker exec -it pumptui-app python3 --version

# View container environment
docker exec -it pumptui-app env
```

### Backup MongoDB Data

```bash
# Backup
docker exec pumptui-mongo mongodump --archive=/tmp/backup.archive

# Copy to host
docker cp pumptui-mongo:/tmp/backup.archive ./mongo-backup.archive

# Restore
docker cp ./mongo-backup.archive pumptui-mongo:/tmp/restore.archive
docker exec pumptui-mongo mongorestore --archive=/tmp/restore.archive
```

## Benefits of Docker Deployment

✅ **Zero localhost pollution** - No Python packages installed on your system  
✅ **Consistent environment** - Works identically on any machine  
✅ **Easy distribution** - Share with users via Git clone + docker start  
✅ **Persistent data** - Settings and database survive container restarts  
✅ **Isolated MongoDB** - No conflict with other MongoDB installations  
✅ **Simple cleanup** - One command removes everything  

## System Requirements

- Docker Engine 20.10+ or Docker Desktop
- docker-compose 1.29+ (usually included with Docker Desktop)
- 500MB free disk space for images
- 100MB+ for data (grows with usage)

## Comparison: Local vs Docker

| Feature | Local | Docker |
|---------|-------|--------|
| Dependencies on host | Yes (Python, MongoDB, etc.) | No |
| Setup complexity | Moderate | Simple |
| Data portability | Manual | Automatic (volumes) |
| MongoDB included | Must install separately | Yes |
| Cleanup | Manual uninstall | One command |
| Multi-user deployment | Complex | Git clone + start |
