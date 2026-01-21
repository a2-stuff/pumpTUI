import asyncio
import json
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Placeholder, DataTable
from textual.containers import Container
from textual.binding import Binding
from ..api import PumpPortalClient
from ..helpers import get_env_var
from .widgets import TokenTable, TokenDetail
from .screens import SettingsView, InfoView
from .wallet_screen import WalletView

class PumpApp(App):
    """A Textual app to view Pump.fun tokens."""

    TITLE = "pumpTUI"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh Data"),
        ("ctrl+p", "switch_to_settings", "Preferences"),
    ]

    def __init__(self):
        super().__init__()
        # User provided key
        self.api_key = get_env_var("API_KEY")
        if not self.api_key:
             self.api_key = "8hw2peb2a92q0ya475gkgnbdb4nmev9r9134gjkra9m4pc3m6ttqebup9dw6rwvh98tq8ub389jpcckg91pn2t3he8r34wb298r6yvb465vn4c9nat75euhgf1n62nbd84rn0mu7a4ykuathppthqa8rpcnbt6d87jbuh7471672yj65d2p4h3natpqjpb3ax2mwrba8hkkuf8"
        self.api_client = PumpPortalClient(api_key=self.api_key)

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        # Start the WebSocket stream background task
        asyncio.create_task(self.stream_tokens())

    async def action_switch_to_settings(self) -> None:
        """Switch to settings tab."""
        self.query_one(TabbedContent).active = "settings"

    async def stream_tokens(self) -> None:
        """Listen to WS and update table."""
        with open("debug_stream.log", "a") as f:
            f.write("Stream started.\n")
        
        try:
             # Subscribe to new tokens (single connection)
             await self.api_client.subscribe_new_tokens()
             self.notify("Connected to Stream.")
             with open("debug_stream.log", "a") as f:
                 f.write("Subscribed.\n")
             
             table = self.query_one("#table_new", TokenTable)
             async for event in self.api_client.listen():
                 if event:
                     with open("debug_stream.log", "a") as f:
                         f.write(f"Event: {json.dumps(event)}\n")
                     
                     # Filter out subscription confirmation messages
                     if "message" in event and "Successfully subscribed" in event["message"]:
                         continue
                     
                     # Handle event via helper
                     self.handle_stream_event(event)

        except Exception as e:
            with open("debug_stream.log", "a") as f:
                f.write(f"Error: {e}\n")
            self.notify(f"Stream error: {e}", severity="error")

    def handle_stream_event(self, event: dict) -> None:
         """Process a stream event synchronously to ensure order."""
         table = self.query_one("#table_new", TokenTable)
         
         # 1. Update Table (and Data Store)
         table.process_event(event)
         
         # 2. Subscribe if New Token
         if "mint" in event and event.get("txType") in [None, "create"]:
             mint = event.get("mint")
             if mint:
                 asyncio.create_task(self.api_client.subscribe_token_trade([mint]))
         
         # 3. Update Detail View (if applicable)
         detail_view = self.query_one("#detail_view", TokenDetail)
         if detail_view.current_token:
             current_mint = detail_view.current_token.get("mint")
             event_mint = event.get("mint")
             
             if current_mint and event_mint == current_mint:
                 # Fetch latest data from store (which process_event just updated)
                 updated_data = table.data_store.get(current_mint)
                 if updated_data:
                     # Direct call to update
                     detail_view.update_token(updated_data)
                     


    async def on_unmount(self):
        await self.api_client.close()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="new"):
            with TabPane("New Tokens", id="new"):
                # Split Container
                with Container(classes="split-container"):
                    yield TokenTable(title="New Tokens", id="table_new")
                    yield TokenDetail(id="detail_view")
            
            # Other tabs (placeholders or settings)
            with TabPane("Wallet Manager", id="wallet"):
                yield WalletView(id="wallet_view")
            with TabPane("Trending", id="trending"):
                yield Placeholder("Trending view unavailable in this mode")
            with TabPane("Settings", id="settings"):
                yield SettingsView()
            with TabPane("Info", id="info"):
                yield InfoView()
        yield Footer()

    async def action_refresh(self) -> None:
        """Refresh the current view."""
        self.notify("Streaming is active. No manual refresh needed.")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection from the table."""
        try:
            row_key = event.row_key.value
            table = self.query_one("#table_new", TokenTable)
            
            # Retrieve data from table store
            token_data = table.data_store.get(row_key)
            if token_data:
                self.query_one("#detail_view", TokenDetail).update_token(token_data)
            else:
                self.notify("Token detail not found.", severity="warning")
        except Exception as e:
            self.notify(f"Selection error: {e}", severity="error")


if __name__ == "__main__":
    app = PumpApp()
    app.run()
