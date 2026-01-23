import os
import json
import httpx
from typing import List, Dict, Optional

_shared_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    """Get or create a shared httpx.AsyncClient for connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        # Increase limits for high-volume token data and trade execution
        _shared_client = httpx.AsyncClient(
            timeout=30.0, 
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
    return _shared_client

ENV_FILE = ".env"
WALLETS_FILE = "wallets.json"

# --- Env Helpers (Keep for other settings if needed) ---
def load_env() -> Dict[str, str]:
    """Load env vars from .env file."""
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip()
    return env

def get_env_var(key: str) -> Optional[str]:
    """Get a specific env var."""
    env = load_env()
    return env.get(key)

def save_env_var(key: str, value: str) -> None:
    """Save or update an env var in .env file."""
    env = load_env()
    env[key] = value
    
    with open(ENV_FILE, "w") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")

# --- Wallet Storage (Deprecated - Use Database) ---
# All wallet operations are now handled via database.py

