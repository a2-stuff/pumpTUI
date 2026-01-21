import json
import os
from typing import Dict, Any

class Config:
    """Manages application configuration and persistence."""
    
    CONFIG_FILE = "config.json"
    
    DEFAULT_THRESHOLDS = {
        "mc": {"red": 30.0, "yellow": 40.0},
        "tx": {"red": 15.0, "yellow": 50.0},
        "holders": {"red": 20.0, "yellow": 50.0},
        "vol": {"red": 5000.0, "yellow": 15000.0}
    }

    def __init__(self):
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        # Trading configuration
        # Trading configuration
        self.rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
        # Wallet is now managed via Wallet Manager (wallets.json)
        self.default_slippage = float(os.getenv("DEFAULT_SLIPPAGE", "10"))
        self.default_priority_fee = float(os.getenv("DEFAULT_PRIORITY_FEE", "0.005"))
        self.load()

    def load(self):
        """Load configuration from file."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    if "thresholds" in data:
                        for key, val in data["thresholds"].items():
                            if key in self.thresholds:
                                self.thresholds[key].update(val)
                    # Load trading config (with env var fallback)
                    if "rpc_url" in data:
                        self.rpc_url = data["rpc_url"]
                    if "default_slippage" in data:
                        self.default_slippage = data["default_slippage"]
                    if "default_priority_fee" in data:
                        self.default_priority_fee = data["default_priority_fee"]
            except Exception:
                pass # Fallback to defaults

    def save(self):
        """Save configuration to file."""
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({
                    "thresholds": self.thresholds,
                    "rpc_url": self.rpc_url,
                    "default_slippage": self.default_slippage,
                    "default_priority_fee": self.default_priority_fee
                }, f, indent=4)
        except Exception:
            pass

    def update_thresholds(self, category: str, red: float, yellow: float):
        """Update thresholds for a category and save."""
        if category in self.thresholds:
            self.thresholds[category] = {"red": red, "yellow": yellow}
            self.save()
    
    def update_rpc(self, rpc_url: str):
        """Update RPC URL and save."""
        self.rpc_url = rpc_url
        self.save()
    
    def get_active_wallet(self) -> Dict[str, str]:
        """Get the currently active wallet from Wallet Manager."""
        from .helpers import load_wallets
        wallets = load_wallets()
        wallet = {}
        
        for w in wallets:
            if w.get("active"):
                wallet = w.copy()
                break
        
        if not wallet and wallets:
             wallet = wallets[0].copy()
        
        if wallet and not wallet.get("walletPublicKey") and wallet.get("privateKey"):
            try:
                from solders.keypair import Keypair
                kp = Keypair.from_base58_string(wallet["privateKey"])
                wallet["walletPublicKey"] = str(kp.pubkey())
            except Exception:
                pass
                
        return wallet
    
    def update_trading_defaults(self, slippage: float, priority_fee: float):
        """Update trading defaults and save."""
        self.default_slippage = slippage
        self.default_priority_fee = priority_fee
        self.save()

# Global config instance
config = Config()
