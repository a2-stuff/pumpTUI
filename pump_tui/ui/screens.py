from textual.widgets import Label, Input, Button, Markdown, Static
from textual.containers import Vertical, Container, Horizontal
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
