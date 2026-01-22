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
                     ws = self.app.api_client.websocket
                     if hasattr(ws, "latency"):
                         latency_ms = int(ws.latency * 1000)
                 except:
                     latency_ms = 0

            # Identify colors based on thresholds
            v_color = "red" if velocity < 10 else "yellow" if velocity <= 15 else "green"
            l_color = "green" if latency_ms <= 100 else "yellow" if latency_ms <= 180 else "red"
            c_color = "green" if cpu <= 60 else "yellow" if cpu <= 80 else "red"
            m_color = "green" if mem <= 60 else "yellow" if mem <= 80 else "red"
            
            # RPC Latency colors
            rpc_lat = getattr(self.app, "rpc_latency", 0)
            if rpc_lat < 0:
                rpc_color = "red"
                rpc_str = "Error"
            else:
                rpc_color = "green" if rpc_lat <= 150 else "yellow" if rpc_lat <= 300 else "red"
                rpc_str = f"{rpc_lat}ms"

            stats_msg = (
                f"Velocity: [{v_color}]{velocity} tpm[/]  "
                f"RPC: [{rpc_color}]{rpc_str}[/]  "
                f"Latency: [{l_color}]{latency_ms}ms[/]  "
                f"CPU: [{c_color}]{cpu:.0f}%[/] "
                f"Mem: [{m_color}]{mem:.0f}%[/]  "
                f"{time_str}"
            )
            self.query_one("#header_stats", Label).update(Text.from_markup(stats_msg))


class PumpApp(App):
    """A Textual app to view Pump.fun tokens."""

    TITLE = "pumpTUI v1.1.5"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("n", "switch_to_new", "New Tokens", show=False),
        Binding("v", "switch_to_volume", "Volume", show=False),
        Binding("t", "switch_to_tracker", "Tracker", show=False),
        Binding("w", "switch_to_wallets", "Wallets", show=False),
        Binding("x", "switch_to_settings", "Settings", show=False),
        Binding("s", "focus_search", "Search", show=False),
        Binding("i", "switch_to_info", "Info", show=False),
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
        # User provided key strictly from .env
        self.api_key = get_env_var("API_KEY") or ""
        self.api_client = PumpPortalClient(api_key=self.api_key)
        self.dex_client = DexScreenerClient()
        self.token_timestamps = [] # Track timestamps of new tokens
        self.sol_price = 0.0
        self.btc_price = 0.0
        self.rpc_latency = 0 # New RPC latency tracker

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        # Show startup screen
        startup = StartupScreen()
        self.push_screen(startup)
        
        # Start background tasks
        self.set_interval(10.0, self.update_rpc_latency)
        asyncio.create_task(self.update_rpc_latency())
        # Start the WebSocket stream background task
        asyncio.create_task(self.stream_tokens())

        # Run loading animation
        asyncio.create_task(self.run_startup_animation(startup))

    async def run_startup_animation(self, startup_screen: StartupScreen):
        await startup_screen.start_loading()
        self.pop_screen()
        
        # Check for missing configuration and notify
        from ..helpers import get_env_var
        if not get_env_var("API_KEY"):
            self.notify("⚠️ No API_KEY found in .env. Trading features may be limited.", variant="warning", timeout=10)
        if not get_env_var("RPC_URL"):
            self.notify("⚠️ No RPC_URL found in .env. Using public Solana RPC (slower).", variant="warning", timeout=10)
            
        # Start Price Ticker
        self.set_interval(10.0, self.update_market_prices)
        asyncio.create_task(self.update_market_prices())

    async def update_rpc_latency(self) -> None:
        """Measure RPC Latency via getHealth call."""
        import time
        import httpx
        from ..config import config
        
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
                await client.post(config.rpc_url, json=payload)
            self.rpc_latency = int((time.perf_counter() - start) * 1000)
        except:
            self.rpc_latency = -1 # Error state

    async def update_market_prices(self) -> None:
        """Fetch and update SOL/BTC prices."""
        try:
            sol = await self.dex_client.get_sol_price()
            btc = await self.dex_client.get_btc_price()
            
            if sol: self.sol_price = sol
            if btc: self.btc_price = btc
            
            # Update Price Ticker
            price_str = f" [blue]◎[/] ${self.sol_price:.2f}   [#fab387]₿[/] ${self.btc_price:,.0f} "
            self.query_one("#price_ticker", Static).update(Text.from_markup(price_str))
        except Exception:
            pass


    async def action_quit(self) -> None:
        """Show quit confirmation."""
        def check_quit(should_quit: bool) -> None:
             if should_quit:
                 self.push_screen(ShutdownScreen())
                 asyncio.create_task(self.cleanup_and_exit())
        
        self.push_screen(QuitScreen(), check_quit)

    async def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab changes to update hotkey visibility."""
        self.refresh_bindings()

    def refresh_bindings(self) -> None:
        """Update hotkey visibility based on state."""
        try:
            tab_content = self.query_one(TabbedContent)
            active_tab = tab_content.active
            
            show_trading = False
            if active_tab == "new":
                try:
                    table_widget = self.query_one("#table_new", TokenTable)
                    if table_widget.table.cursor_row >= 0:
                        show_trading = True
                except:
                    pass
            
            if show_trading:
                # Dynamically bind to force visibility
                self.bind("b", "trade_token", description="Trade", show=True)
                self.bind("c", "copy_ca", description="Copy CA", show=True)
                self.bind("ctrl+shift+c", "copy_ca", show=False) # Alternate hidden hotkey
            else:
                # Remove from active bindings map to hide from footer
                try:
                    if "b" in self._bindings._map:
                        self._bindings._map.pop("b")
                    if "c" in self._bindings._map:
                        self._bindings._map.pop("c")
                except:
                    pass
            
            try:
                self.query_one(Footer).refresh()
            except:
                pass
                
            super().refresh_bindings()
        except:
             super().refresh_bindings()

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
        self.query_one(TabbedContent).active = "wallets"
        self.safe_focus(WalletView, "#wallets_table")

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
        try:
            active_tab = self.query_one(TabbedContent).active
            if active_tab == "new":
                table_id = "#table_new"
                token_table = self.query_one(table_id, TokenTable)
                
                # Get selected token data
                selected_token = token_table.get_selected_token()
                if selected_token:
                    # Create data provider lambda for live updates
                    data_provider = lambda m: token_table.data_store.get(m)
                    
                    
                    # Open trade modal
                    from .screens import TradeModal
                    await self.push_screen(TradeModal(
                        selected_token, 
                        data_provider=data_provider
                    ))
                else:
                    self.notify("No token selected. Focus the table and select a token first.", severity="warning")
            else:
                self.notify("Trading is only available from New Tokens or Volume tabs.", severity="warning")
        except Exception as e:
            self.notify(f"Error opening trade modal: {e}", severity="error")

    async def action_copy_ca(self) -> None:
        """Copy the selected token's contract address to clipboard without blocking."""
        try:
            tab_content = self.query_one(TabbedContent)
            if tab_content.active == "new":
                token_table = self.query_one("#table_new", TokenTable)
                selected_token = token_table.get_selected_token()
                
                if not selected_token:
                    self.notify("Select a token first.", variant="warning")
                    return

                ca = str(selected_token.get("mint", "")).strip()
                if not ca: return

                # Step 1: OSC 52
                try:
                    import base64
                    enc = base64.b64encode(ca.encode()).decode()
                    self.console.file.write(f"\033]52;c;{enc}\a")
                    self.console.file.flush()
                except: pass

                # Step 2: System commands (Async)
                import os
                targets = []
                if os.getenv("WAYLAND_DISPLAY"): 
                    targets.append(['wl-copy'])
                if os.getenv("DISPLAY"): 
                    targets.append(['xclip', '-selection', 'clipboard'])
                    targets.append(['xclip', '-selection', 'primary'])
                    targets.append(['xsel', '-ib'])
                targets.append(['pbcopy'])

                success = False
                for cmd in targets:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL
                        )
                        await asyncio.wait_for(proc.communicate(input=ca.encode()), timeout=1.0)
                        if proc.returncode == 0:
                            success = True
                            break
                    except: continue

                if success:
                    self.notify(f"CA Copied: {ca[:8]}...", severity="information")
                else:
                    self.notify(f"Clipboard restricted. CA: {ca}", timeout=10)
        except Exception as e:
            self.notify(f"Copy Error: {e}", severity="error")


    async def stream_tokens(self) -> None:
        """Listen to WS and update table with reconnection logic."""
        reconnect_delay = 1.0
        while True:
            try:
                # 1. Connect and Subscribe
                await self.api_client.connect()
                await self.api_client.subscribe_new_tokens()
                self.notify("Stream Connected", severity="information")
                reconnect_delay = 1.0 # Reset delay on success
                
                # 2. Listen loop
                async for event in self.api_client.listen():
                    if not event:
                        continue
                    
                    # Filter out subscription confirmation messages
                    if "message" in event and "Successfully subscribed" in event["message"]:
                        continue
                    
                    # Handle event via helper (Wrapped to protect the loop)
                    try:
                        self.handle_stream_event(event)
                    except Exception as e:
                        # Log specific event handling error but keep listening
                        with open("error.log", "a") as f:
                            f.write(f"Event Handler Error: {e}\n{json.dumps(event)}\n")

            except Exception as e:
                self.notify(f"Stream error: {e}. Reconnecting in {reconnect_delay}s...", severity="warning")
                with open("error.log", "a") as f:
                    f.write(f"Stream Loop Error: {e}\n")
                
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60.0) # Exponential backoff
            
            # If listen exits normally (connection closed)
            await asyncio.sleep(1.0)


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
            with TabPane("New Tokens (n)", id="new"):
                # Split Container
                with Container(classes="split-container"):
                    yield TokenTable(title="New Tokens", id="table_new")
                    yield TokenDetail(id="detail_view")
             
             # Other tabs (placeholders or settings)
            with TabPane("Tracker (t)", id="tracker"):
                yield WalletTrackerView()
            with TabPane("Wallets (w)", id="wallets"):
                 yield WalletView(id="wallet_view")
            with TabPane("Volume (v)", id="trending"):
                yield Placeholder("Trending view unavailable in this mode")
            with TabPane("Settings (x)", id="settings"):
                yield SettingsView()
            with TabPane("Info (i)", id="info"):
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
