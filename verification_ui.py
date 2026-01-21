import os
import sys

# Ensure we can import pump_tui
sys.path.append(os.getcwd())

from pump_tui.ui.app import PumpApp
from textual.app import App

def verify_ui_load():
    print("Verifying UI Instantiation...")
    try:
        app = PumpApp()
        print("Success: App instantiated.")
        
        # Basic check of compose (not a full render)
        # Note: calling compose() directly generates a generator, need to iterate or inspect.
        # But instantiating without error is a good first step.
    except Exception as e:
        print(f"UI Verification Failed: {e}")

if __name__ == "__main__":
    verify_ui_load()
