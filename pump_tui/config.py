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
        from .helpers import get_env_var
        self.rpc_url = get_env_var("RPC_URL") or "https://api.mainnet-beta.solana.com"
        self.mongo_uri = get_env_var("MONGO_URI") or "mongodb://localhost:27017"
        self.default_slippage = float(get_env_var("DEFAULT_SLIPPAGE") or "10")
        self.default_priority_fee = float(get_env_var("DEFAULT_PRIORITY_FEE") or "0.005")
        self.current_theme = "Dolphine"

    async def load_from_db(self):
        """Load configuration from MongoDB."""
        from .database import db
        if not db.connected: return
        
        try:
            # Load thresholds
            t = await db.get_setting("thresholds")
            if t and isinstance(t, dict):
                for key, val in t.items():
                    if key in self.thresholds:
                        self.thresholds[key].update(val)
            
            # Load RPC
            rpc = await db.get_setting("rpc_url")
            if rpc: self.rpc_url = rpc
            
            # Load defaults
            slip = await db.get_setting("default_slippage")
            if slip: self.default_slippage = float(slip)
            
            fee = await db.get_setting("default_priority_fee")
            if fee: self.default_priority_fee = float(fee)

            # Load Theme
            theme = await db.get_setting("current_theme")
            if theme in ["Dolphine", "Cyber"]:
                self.current_theme = theme
            
        except Exception:
            pass 

    async def save_to_db(self):
        """Save current config to MongoDB."""
        from .database import db
        if not db.connected: return
        
        await db.save_setting("thresholds", self.thresholds)
        await db.save_setting("rpc_url", self.rpc_url)
        await db.save_setting("default_slippage", self.default_slippage)
        await db.save_setting("default_priority_fee", self.default_priority_fee)
        await db.save_setting("current_theme", self.current_theme)

    def update_thresholds(self, category: str, red: float, yellow: float):
        if category in self.thresholds:
            self.thresholds[category] = {"red": red, "yellow": yellow}
            # Fire and forget save
            import asyncio
            asyncio.create_task(self.save_to_db())
    
    def update_rpc(self, rpc_url: str):
        self.rpc_url = rpc_url
        import asyncio
        asyncio.create_task(self.save_to_db())
    
    def update_trading_defaults(self, slippage: float, priority_fee: float):
        self.default_slippage = slippage
        self.default_priority_fee = priority_fee
        import asyncio
        asyncio.create_task(self.save_to_db())

# Global config instance
config = Config()
