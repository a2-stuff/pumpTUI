import os
import json
from typing import List, Dict, Optional

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

# --- Wallet Storage ---
def load_wallets() -> List[Dict[str, str]]:
    """Load list of wallets from json."""
    if not os.path.exists(WALLETS_FILE):
        return []
    try:
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_wallet(wallet: Dict[str, str]) -> None:
    """Add or update a wallet in the list."""
    wallets = load_wallets()
    # Check if exists by public key
    pub = wallet.get("walletPublicKey")
    if not pub: 
        return
        
    # Update existing or append
    found = False
    for i, w in enumerate(wallets):
        if w.get("walletPublicKey") == pub:
            wallets[i] = wallet
            found = True
            break
    
    if not found:
        wallets.append(wallet)
        
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=2)

def set_active_wallet(pub_key: str) -> None:
    """Set one wallet as active, others as inactive."""
    wallets = load_wallets()
    for w in wallets:
        if w.get("walletPublicKey") == pub_key:
            w["active"] = True
        else:
            w["active"] = False
            
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=2)

def delete_wallet(pub_key: str) -> None:
    """Remove wallet by public key."""
    wallets = load_wallets()
    wallets = [w for w in wallets if w.get("walletPublicKey") != pub_key]
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=2)

