from textual.widgets import Label, Input, Button, Markdown, Static
from textual.containers import Vertical, Container, Horizontal, Grid
from textual.screen import ModalScreen, Screen
from textual.app import ComposeResult

from ..config import config

class SettingsView(Container):
    def compose(self) -> ComposeResult:
        yield Label("Settings", classes="title")
        
        # API Token Section
        yield Vertical(
            Label("API Token (Optional):", classes="setting-label"),
            Input(placeholder="Enter JWT Token here...", password=True, id="api_token"),
            Button("Save Token", variant="primary", id="save_token"),
            classes="setting-section"
        )
        
        # Market Cap Thresholds
        mc = config.thresholds["mc"]
        yield Label("Market Cap (SOL) Thresholds", classes="setting-title")
        yield Horizontal(
            Vertical(Label("Red <", classes="small-label"), Input(value=str(mc["red"]), id="mc_red"), classes="thresh-input"),
            Vertical(Label("Yellow <", classes="small-label"), Input(value=str(mc["yellow"]), id="mc_yellow"), classes="thresh-input"),
            classes="setting-row"
        )
        
        # TX Count Thresholds
        tx = config.thresholds["tx"]
        yield Label("TX Count Thresholds", classes="setting-title")
        yield Horizontal(
            Vertical(Label("Red <", classes="small-label"), Input(value=str(tx["red"]), id="tx_red"), classes="thresh-input"),
            Vertical(Label("Yellow <", classes="small-label"), Input(value=str(tx["yellow"]), id="tx_yellow"), classes="thresh-input"),
            classes="setting-row"
        )
        
        # Holders Thresholds
        holders = config.thresholds["holders"]
        yield Label("Holders Thresholds", classes="setting-title")
        yield Horizontal(
            Vertical(Label("Red <", classes="small-label"), Input(value=str(holders["red"]), id="holders_red"), classes="thresh-input"),
            Vertical(Label("Yellow <", classes="small-label"), Input(value=str(holders["yellow"]), id="holders_yellow"), classes="thresh-input"),
            classes="setting-row"
        )
        
        yield Button("Save Coloring Layout", variant="success", id="save_colors")
        yield Static("Above 'Yellow <' value will be Green.", classes="info-text")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_token":
            token = self.query_one("#api_token", Input).value
            # In a real app, save this to a config file.
            self.app.notify("Token saved (in memory only)!")
            
        elif event.button.id == "save_colors":
            try:
                # Update MC
                config.update_thresholds("mc", 
                    float(self.query_one("#mc_red", Input).value),
                    float(self.query_one("#mc_yellow", Input).value)
                )
                # Update TX
                config.update_thresholds("tx", 
                    float(self.query_one("#tx_red", Input).value),
                    float(self.query_one("#tx_yellow", Input).value)
                )
                # Update Holders
                config.update_thresholds("holders", 
                    float(self.query_one("#holders_red", Input).value),
                    float(self.query_one("#holders_yellow", Input).value)
                )
                self.app.notify("Coloring thresholds saved!")
            except ValueError:
                self.app.notify("Error: Please enter valid numbers.", variant="error")

class InfoView(Container):
    MD_CONTENT = """
# PumpTUI
**A Textual TUI for Pump.fun**

Version: 0.1.0
Version: 0.1.0
Created by: @not_jarod

## Features
- **New Tokens**: See the latest mints.
- **Live**: Watch currently live tokens.
- **Trending**: Top performing coins.

## Credits
Built with [Textual](https://textual.textualize.io).
Design inspired by [Dolphie](https://github.com/charles-001/dolphie).
    """
    def compose(self) -> ComposeResult:
         yield Markdown(self.MD_CONTENT)

class WalletTrackerView(Container):
    def compose(self) -> ComposeResult:
        yield Label("Wallet Tracker", classes="title")
        yield Static("Enter a wallet address to track its activity (coming soon).", classes="info-text")
        yield Input(placeholder="Enter Solana Wallet Address...", id="tracker_address")
        yield Button("Track Wallet", variant="primary", id="btn_track")

class QuitScreen(ModalScreen):
    """Screen for confirming quit."""
    
    DEFAULT_CSS = """
    QuitScreen {
        align: center middle;
        background: $primary 10%;
    }
    #quit-dialog {
        padding: 1 2;
        width: 40;
        height: auto;
        border: solid $accent;
        background: $surface;
    }
    #quit-title {
        text-style: bold;
        content-align: center middle;
        padding-bottom: 1;
    }
    #quit-buttons {
        align: center middle;
        width: 100%;
        height: auto;
        padding-top: 1;
    }
    Button {
        margin: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Label("Are you sure you want to quit?", id="quit-title")
            with Horizontal(id="quit-buttons"):
                yield Button("Yes", variant="error", id="quit-yes")
                yield Button("No", variant="primary", id="quit-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

class ShutdownScreen(Screen):
    """Screen shown during shutdown."""
    DEFAULT_CSS = """
    ShutdownScreen {
        align: center middle;
        background: #1e1e2e;
    }
    Label {
        color: #f38ba8;
        text-style: bold;
    }
    """
    def compose(self) -> ComposeResult:
         yield Label("Closing connections... cleaning up...", id="shutdown-msg")

class StartupScreen(Screen):
    """Screen shown on startup with animation."""
    
    DEFAULT_CSS = """
    StartupScreen {
        align: center middle;
        background: #1e1e2e;
    }
    .logo {
        color: #89b4fa;
        text-style: bold;
        padding-bottom: 2;
        content-align: center middle;
    }
    #status {
        color: #a6adc8;
    }
    """
    
    from textual.reactive import reactive
    loading_text = reactive("Initializing...")

    def compose(self) -> ComposeResult:
        yield Label(
            "   ___                      _____ _   _ _____\n"
            "  / _ \ _   _ _ __ ___  _ _|_   _| | | |_   _|\n"
            " / /_)/| | | | '_ ` _ \| '_ \| | | | | | | |\n"
            "/ ___/ | |_| | | | | | | |_) | | | |_| |_| |_\n"
            "\/      \__,_|_| |_| |_| .__/|_|  \___/_____/\n"
            "                       |_|                    ",
            classes="logo"
        )
        yield Label(self.loading_text, id="status")

    def watch_loading_text(self, text: str) -> None:
        try:
            self.query_one("#status", Label).update(text)
        except Exception:
            pass

    async def start_loading(self):
        """Cycle through loading steps."""
        steps = [
            "Loading UI Components...",
            "Connecting to APIs...",
            "Loading Wallet Tracker...",
            "Preparing Token Stream...",
            "Ready!"
        ]
        import asyncio
        for step in steps:
            self.loading_text = step
            await asyncio.sleep(0.5)

