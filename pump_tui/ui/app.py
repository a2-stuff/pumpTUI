import asyncio
import json
import psutil
import csv
import os
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Placeholder, DataTable, Label, Static
from textual.containers import Container
from textual.binding import Binding
from textual.reactive import reactive
from ..api import PumpPortalClient
from ..helpers import get_env_var
from .widgets import TokenTable, TokenDetail
from .screens import SettingsView, InfoView, WalletTrackerView, QuitScreen, StartupScreen, ShutdownScreen, TradeModal
from .wallet_screen import WalletView
from ..dex_api import DexScreenerClient
from rich.text import Text

class SystemHeader(Container):
    """Custom header with system stats."""
    
    DEFAULT_CSS = """
    SystemHeader {
        layout: horizontal;
        height: 1;
        dock: top;
        background: #1e1e2e;
        color: #89b4fa;
        margin-bottom: 1;
    }
    .header-title {
        content-align: center middle;
        width: 1fr;
        text-style: bold;
    }
    .header-stats {
        content-align: right middle;
        padding-right: 1;
        width: auto;
        color: #a6adc8;
    }
    """

    def __init__(self, title: str = "PumpTUI"):
        super().__init__()
        self.app_title = title

    def compose(self) -> ComposeResult:
        yield Label(self.app_title, classes="header-title")
        yield Label("", id="header_stats", classes="header-stats")

    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_stats)
        self.update_stats()

    def update_stats(self) -> None:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        time_str = datetime.now().time().strftime("%X")
        if self.is_mounted:
            # Calculate Velocity (Tokens Per Minute)
            velocity = 0
            if hasattr(self.app, "token_timestamps"):
                now = datetime.now().timestamp()
                # Filter timestamps older than 60s
                recent = [ts for ts in self.app.token_timestamps if now - ts <= 60]
                velocity = len(recent)
                # Clean up app's list occasionally (optional, but good practice to keep it clean)
                if len(self.app.token_timestamps) > len(recent):
                     self.app.token_timestamps = recent
            
            # Latency from WebSocket (Manual Ping)
            latency_ms = 0
            if hasattr(self.app, "api_client") and self.app.api_client.websocket and self.app.api_client.running:
                 try:
                     import time
                     start = time.perf_counter()
                     # sending a ping and waiting for pong (if supported by lib version, otherwise might need await)
                     # Since this is sync, we can't await. We can check if the library has updated latency from background pings
                     # or we just rely on the property if it eventually updates.
                     # If the property is 0, let's try to assume it's just very fast or not updated yet.
                     
                     # Check if we can get it from the protocol state
                     ws = self.app.api_client.websocket
                     if hasattr(ws, "latency"):
                         latency_ms = int(ws.latency * 1000)
                     
                 except Exception:
                     latency_ms = 0

                     latency_ms = 0

            self.query_one("#header_stats", Label).update(f"Velocity: {velocity} tpm  Latency: {latency_ms}ms  CPU: {cpu:.0f}% Mem: {mem:.0f}%  {time_str}")

class PumpApp(App):
    """A Textual app to view Pump.fun tokens."""

    TITLE = "pumpTUI v1.1.4"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "switch_to_new", "New Tokens"),
        Binding("v", "switch_to_volume", "Volume"),
        Binding("t", "switch_to_tracker", "Tracker"),
        Binding("w", "switch_to_wallets", "Wallets"),
        Binding("x", "switch_to_settings", "Settings"),
        Binding("s", "focus_search", "Search"),
        Binding("i", "switch_to_info", "Info"),
        Binding("r", "refresh", "Refresh Data"),
        Binding("b", "trade_token", "Trade"),
    ]
    
    def safe_focus(self, selector: str, sub_selector: str = None) -> None:
        """Safely focus a widget after refresh."""
        def _focus():
            try:
                widget = self.query_one(selector)
                if sub_selector:
                    widget = widget.query_one(sub_selector)
                widget.focus()
            except Exception:
                pass
        self.call_after_refresh(_focus)

    def __init__(self):
        super().__init__()
        # User provided key
        self.api_key = get_env_var("API_KEY")
        if not self.api_key:
             # Look for key in wallets if not in .env (some users might put it there)
             active_wallet = config.get_active_wallet()
             self.api_key = active_wallet.get("apiKey")
             
        self.api_client = PumpPortalClient(api_key=self.api_key or "")
        self.dex_client = DexScreenerClient()
        self.token_timestamps = [] # Track timestamps of new tokens
        self.sol_price = 0.0
        self.btc_price = 0.0

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        # Show startup screen
        startup = StartupScreen()
        self.push_screen(startup)
        
        # Start the WebSocket stream background task
        asyncio.create_task(self.stream_tokens())

        # Run loading animation
        asyncio.create_task(self.run_startup_animation(startup))

    async def run_startup_animation(self, startup_screen: StartupScreen):
        await startup_screen.start_loading()
        self.pop_screen()
        # Start Price Ticker
        self.set_interval(10.0, self.update_market_prices)
        asyncio.create_task(self.update_market_prices())

    async def update_market_prices(self) -> None:
        """Fetch and update SOL/BTC prices."""
        try:
            # log to a dedicated price log for clarity
            with open("price_debug.log", "a") as f:
                 f.write(f"--- Update cycle start {datetime.now()} ---\n")
            
            # Use a short timeout locally to avoid blocking
            sol = await self.dex_client.get_sol_price()
            with open("price_debug.log", "a") as f:
                 f.write(f"SOL fetch done: {sol}\n")
                 
            btc = await self.dex_client.get_btc_price()
            with open("price_debug.log", "a") as f:
                 f.write(f"BTC fetch done: {btc}\n")
            
            if sol: self.sol_price = sol
            if btc: self.btc_price = btc
            
            # Update Price Ticker
            price_str = f" [blue]◎[/] ${self.sol_price:.2f}   [#fab387]₿[/] ${self.btc_price:,.0f} "
            self.query_one("#price_ticker", Static).update(Text.from_markup(price_str))
            
            # Also log to debug_stream for consistency
            with open("debug_stream.log", "a") as f:
                 f.write(f"Prices Updated: SOL {self.sol_price} | BTC {self.btc_price}\n")
            
            with open("price_debug.log", "a") as f:
                 f.write(f"UI Update done: {price_str}\n")
                 
        except Exception as e:
            with open("price_debug.log", "a") as f:
                f.write(f"Price Update Error: {type(e).__name__}: {e}\n")

    async def action_quit(self) -> None:
        """Show quit confirmation."""
        def check_quit(should_quit: bool) -> None:
             if should_quit:
                 self.push_screen(ShutdownScreen())
                 asyncio.create_task(self.cleanup_and_exit())
        
        self.push_screen(QuitScreen(), check_quit)

    async def cleanup_and_exit(self) -> None:
        """Clean up resources and exit."""
        # Give time for shutdown screen to render
        await asyncio.sleep(1.0)
        
        if self.api_client:
             if self.api_client.websocket:
                 await self.api_client.close()
        self.exit()

    def save_token_to_csv(self, token_data: dict) -> None:
        """Save token to daily CSV file."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"tokensdb/tokens_{date_str}.csv"
            file_exists = os.path.isfile(filename)
            
            # Ensure directory exists
            os.makedirs("tokensdb", exist_ok=True)
            
            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Write header if new file
                if not file_exists:
                    writer.writerow(["timestamp", "mint", "name", "symbol", "dev_address", "bonding_curve"])
                
                # Extract fields safely
                timestamp = datetime.now().isoformat()
                mint = token_data.get("mint", "")
                name = token_data.get("name", "")
                symbol = token_data.get("symbol", "")
                dev = token_data.get("traderPublicKey", "")
                curve = token_data.get("bondingCurveKey", "")
                
                writer.writerow([timestamp, mint, name, symbol, dev, curve])
        except Exception as e:
            # Log error but don't crash app
            with open("error.log", "a") as f:
                f.write(f"CSV Error: {e}\n")

    async def action_switch_to_settings(self) -> None:
        """Switch to settings tab."""
        self.query_one(TabbedContent).active = "settings"
        self.safe_focus(SettingsView)

    async def action_switch_to_new(self) -> None:
        """Switch to New Tokens tab."""
        self.query_one(TabbedContent).active = "new"
        self.safe_focus("#table_new")

    async def action_switch_to_tracker(self) -> None:
        """Switch to Tracker tab."""
        self.query_one(TabbedContent).active = "tracker"
        self.safe_focus(WalletTrackerView)

    async def action_switch_to_wallets(self) -> None:
        """Switch to Wallets tab."""
        self.query_one(TabbedContent).active = "wallet"
        self.safe_focus(WalletView, DataTable)

    async def action_switch_to_info(self) -> None:
        """Switch to Info tab."""
        self.query_one(TabbedContent).active = "info"
        self.safe_focus(InfoView)

    async def action_switch_to_volume(self) -> None:
        """Switch to Volume/Trending tab."""
        self.query_one(TabbedContent).active = "trending"
        self.safe_focus("#table_trending")

    async def action_focus_search(self) -> None:
        """Switch to New Tokens tab and focus search."""
        self.query_one(TabbedContent).active = "new"
        try:
            self.query_one("#search_input").focus()
        except Exception:
            self.notify("Search input not found.", severity="error")
    
    async def action_trade_token(self) -> None:
        """Open trade modal for the currently selected token."""
        # Get the active tab's TokenTable
        try:
            active_tab = self.query_one(TabbedContent).active
            if active_tab in ["new", "trending"]:
                table_id = "#table_new" if active_tab == "new" else "#table_trending"
                token_table = self.query_one(table_id, TokenTable)
                
                # Get selected token data
                selected_token = token_table.get_selected_token()
                if selected_token:
                    # Create data provider lambda for live updates
                    data_provider = lambda m: token_table.data_store.get(m)
                    
                    # Open trade modal
                    await self.push_screen(TradeModal(selected_token, data_provider=data_provider))
                else:
                    self.notify("No token selected. Select a token first.", severity="warning")
            else:
                self.notify("Trading is only available from New Tokens or Volume tabs.", severity="warning")
        except Exception as e:
            self.notify(f"Error opening trade modal: {e}", severity="error")

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
             # Track for Velocity
             self.token_timestamps.append(datetime.now().timestamp())
             
             # Save to CSV
             self.save_token_to_csv(event)
             
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
        yield SystemHeader(title=self.TITLE)
        with TabbedContent(initial="new"):
            with TabPane("New Tokens", id="new"):
                # Split Container
                with Container(classes="split-container"):
                    yield TokenTable(title="New Tokens", id="table_new")
                    yield TokenDetail(id="detail_view")
             
             # Other tabs (placeholders or settings)
            with TabPane("Tracker", id="tracker"):
                yield WalletTrackerView()
            with TabPane("Wallets", id="wallet"):
                yield WalletView(id="wallet_view")
            with TabPane("Volume", id="trending"):
                yield Placeholder("Trending view unavailable in this mode")
            with TabPane("Settings", id="settings"):
                yield SettingsView()
            with TabPane("Info", id="info"):
                yield InfoView()
        
        # Custom Bottom Bar
        with Container(id="bottom_bar"):
            yield Footer()
            yield Static(" Loading Prices... ", id="price_ticker", markup=True)

    async def action_refresh(self) -> None:
        """Refresh the current view."""
        self.notify("Streaming is active. No manual refresh needed.")

    # We catch any DataTable events bubbling up from TokenTable
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._handle_row_event(event)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._handle_row_event(event)

    def _handle_row_event(self, event: DataTable.RowSelected | DataTable.RowHighlighted) -> None:
        """Centralized handler for row interactions."""
        try:
            row_key = event.row_key.value
            table_widget = self.query_one("#table_new", TokenTable)
            
            # Retrieve data from table's data_store
            token_data = table_widget.data_store.get(row_key)
            
            with open("debug_stream.log", "a") as f:
                f.write(f"WIDGET EVENT: {type(event).__name__} for {row_key}. Found: {token_data is not None}\n")
            
            if token_data:
                self.query_one("#detail_view", TokenDetail).update_token(token_data)
        except Exception as e:
            # Silently log errors to debug_stream
            with open("debug_stream.log", "a") as f:
                 f.write(f"Selection Event Error: {e}\n")


if __name__ == "__main__":
    app = PumpApp()
    app.run()
