from textual.widgets import Label, Input, Button, Markdown, Static
from textual.containers import Vertical, Container
from textual.app import ComposeResult

class SettingsView(Container):
    def compose(self) -> ComposeResult:
        yield Label("Settings", classes="title")
        yield Label("API Token (Optional):")
        yield Input(placeholder="Enter JWT Token here...", password=True, id="api_token")
        yield Button("Save Token", variant="primary", id="save_token")
        yield Static("Other settings can be added here.", classes="info-text")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_token":
            token = self.query_one("#api_token", Input).value
            # In a real app, save this to a config file.
            # For now, we'll just notify.
            self.app.notify("Token saved (in memory only)!")
            # We could actually update the api client if we wanted
            # self.app.api_client.update_token(token)

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
