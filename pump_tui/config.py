import json
import os
from typing import Dict, Any

class Config:
    """Manages application configuration and persistence."""
    
    CONFIG_FILE = "config.json"
    
    DEFAULT_THRESHOLDS = {
        "mc": {"red": 30.0, "yellow": 40.0},
        "tx": {"red": 15.0, "yellow": 50.0},
        "holders": {"red": 20.0, "yellow": 50.0}
    }

    def __init__(self):
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
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
            except Exception:
                pass # Fallback to defaults

    def save(self):
        """Save configuration to file."""
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"thresholds": self.thresholds}, f, indent=4)
        except Exception:
            pass

    def update_thresholds(self, category: str, red: float, yellow: float):
        """Update thresholds for a category and save."""
        if category in self.thresholds:
            self.thresholds[category] = {"red": red, "yellow": yellow}
            self.save()

# Global config instance
config = Config()
