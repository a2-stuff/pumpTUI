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
from .widgets import TokenTable, TokenDetail, VolumeTable, RunnersTable, TradePanel
from .screens import SettingsView, InfoView, WalletTrackerView, QuitScreen, StartupScreen, ShutdownScreen, TradeModal
from .wallet_screen import WalletView
from ..dex_api import DexScreenerClient
from ..database import db
from ..config import config
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

            # Balance
            bal_str = getattr(self.app, "wallet_balance_str", " -- SOL")
            active_pub = getattr(self.app, "active_wallet_pub", "")
            if active_pub:
                 bal_display = f" [bold white]Bal:[/] [#a6e3a1]{bal_str}[/] "
            else:
                 bal_display = " [dim]No Wallet[/] "

            stats_msg = (
                f"{bal_display}  "
                f"Velocity: [{v_color}]{velocity} tpm[/]  "
                f"Lat: [{l_color}]{latency_ms}ms[/]  "
                f"RPC: [{rpc_color}]{rpc_str}[/]  "
                f"CPU: [{c_color}]{cpu}%[/]  "
                f"Mem: [{m_color}]{mem}%[/]"
            )
            self.query_one("#header_stats", Label).update(Text.from_markup(stats_msg))
        else:
            self.query_one("#header_stats", Label).update("")



class PumpApp(App):
    """A Textual app to view Pump.fun tokens."""

    TITLE = "pumpTUI v1.1.8"
    CSS_PATH = config.THEMES.get(config.current_theme, "styles.tcss")
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("n", "switch_to_new", "New Tokens", show=False),
        # Binding("v", "switch_to_volume", "Volume", show=False), # Removed
        Binding("t", "switch_to_tracker", "Tracker", show=False),
        Binding("w", "switch_to_wallets", "Wallets", show=False),
        Binding("x", "switch_to_settings", "Settings", show=False),
        Binding("/", "focus_search", "Search", show=False),
        Binding("i", "switch_to_info", "Info", show=False),
        Binding("b", "trade_buy", "Buy (b)"),
        Binding("s", "trade_sell", "Sell (s)"),
        Binding("e", "trade_execute", "Execute (e)"),
        Binding("enter", "select_token_action", "Select", show=True),
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
        
        # Global Wallet State
        self.active_wallet = None
        self.active_wallet_pub = ""
        self.wallet_balance_str = "0.00 SOL"

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
        
        # Monitor DB Status
        self.set_interval(10.0, self.monitor_db_status)
        
        # Global Wallet Manager
        asyncio.create_task(self.load_global_wallet())
        self.set_interval(30.0, self.update_global_balance) # Refresh balance every 30s

        
        # Initial binding refresh
        self.call_after_refresh(self.refresh_bindings)

        # Run loading animation
        asyncio.create_task(self.run_startup_animation(startup))
        
        # Connect to DB
        asyncio.create_task(db.connect())

    async def run_startup_animation(self, startup_screen: StartupScreen):
        # 1. Check Database
        startup_screen.add_log("Checking Database Connection...", "#89b4fa") # Blue
        
        # Wait for DB (max 3s)
        wait_time = 0
        while wait_time < 3.0:
            if hasattr(db, "connected") and db.connected:
                break
            await asyncio.sleep(0.5)
            wait_time += 0.5
            
        if hasattr(db, "connected") and db.connected:
            startup_screen.add_log("  ✓ Database Connected", "#a6e3a1") # Green
            # Load config from DB
            from ..config import config
            await config.load_from_db()
        else:
             startup_screen.add_log("  ✗ Database Timeout - Continuing...", "#f38ba8") # Red
        
        await asyncio.sleep(0.5)

        # 2. Check API / RPC
        from ..helpers import get_env_var
        
        startup_screen.add_log("Loading Configuration...", "#89b4fa")
        if get_env_var("API_KEY"):
            startup_screen.add_log("  ✓ API Key Found", "#a6e3a1")
        else:
            startup_screen.add_log("  ! No API Key (View Only)", "#fab387") # Orange
            
        rpc = get_env_var("RPC_URL")
        if rpc:
             cleaned = rpc.replace("https://", "").split("/")[0]
             startup_screen.add_log(f"  ✓ RPC Configured ({cleaned})", "#a6e3a1")
        else:
             startup_screen.add_log("  ! No RPC URL (Public Mode)", "#fab387")
        
        await asyncio.sleep(0.5)

        # 3. Finalize
        startup_screen.add_log("Starting Token Stream...", "#89b4fa")
        await asyncio.sleep(2.0)
        
        self.pop_screen()
        
        # Focus token table on startup
        self.safe_focus("#table_new", ".data-table")
        
        # Start Price Ticker now
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

    async def monitor_db_status(self) -> None:
        """Check DB connection and notify if down."""
        if hasattr(db, "connected") and db.connected:
            # If we don't have a wallet loaded yet, retry loading it
            if not getattr(self, "active_wallet", None):
                 asyncio.create_task(self.load_global_wallet())
        elif hasattr(db, "connected") and not db.connected:
            self.notify("⚠️ Database Disconnected. History & Settings may act weird.", severity="error", timeout=5)
            # Try reconnect?
            asyncio.create_task(db.connect())

    async def load_global_wallet(self) -> None:
        """Load active wallet globally."""
        try:
            # Wait for DB connection if needed
            if not hasattr(db, "connected") or not db.connected:
                 # Check again in a bit
                 return
            
            active_doc = await db.settings.find_one({"key": "active_wallet"})
            if active_doc and "value" in active_doc:
                pub_key = active_doc["value"]
                
                # Fetch wallet
                wallet = await db.wallets.find_one({"walletPublicKey": pub_key})
                if not wallet:
                    # Attempt to fetch from get_wallets (decrypted cache issue?)
                     wallets = await db.get_wallets()
                     wallet = next((w for w in wallets if w["walletPublicKey"] == pub_key), None)
                
                if wallet:
                     self.active_wallet = wallet
                     self.active_wallet_pub = wallet.get("walletPublicKey")
                     self.notify(f"Loaded Wallet: {self.active_wallet_pub[:6]}..") # Debug notify
                else:
                    self.active_wallet = None
                    self.active_wallet_pub = ""
            
            await self.update_global_balance()
                         
        except Exception as e:
            with open("error.log", "a") as f: f.write(f"Wallet Load Error: {e}\n")

    async def update_global_balance(self) -> None:
        """Fetch balance for active wallet."""
        try:
            if not self.active_wallet:
                self.wallet_balance_str = "No Wallet"
                return
            
            pub_key = self.active_wallet.get("walletPublicKey")
            import httpx
            from ..config import config
            
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub_key]}
            async with httpx.AsyncClient(timeout=2.0) as http_client:
                response = await http_client.post(config.rpc_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    val = data.get("result", {}).get("value")
                    if val is not None:
                         bal_sol = val / 1_000_000_000
                         self.wallet_balance_str = f"{bal_sol:.4f} SOL"
        except: pass

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
                
                # Sorting bindings
                self.bind("m", "sort_new_mc", description="Sort MC", show=True)
                self.bind("v", "sort_new_vol", description="Sort Vol", show=True)
                self.bind("l", "sort_new_live", description="Live (Reset)", show=True)

            # Clean up Runners bindings if not in trending
            try:
                if active_tab != "new":
                     if "m" in self._bindings._map: self._bindings._map.pop("m")
                     if "v" in self._bindings._map: self._bindings._map.pop("v")
                     if "l" in self._bindings._map: self._bindings._map.pop("l")
                     
                # Handle Trading Bindings (Always show if in New Tokens tab)
                # "show_trading" check logic can be relaxed or used just for 'b' context
                # User wants global B/S hotkeys in this view
                self.bind("b", "trade_buy", description="Buy (b)", show=True)
                self.bind("s", "trade_sell", description="Sell (s)", show=True)
                self.bind("c", "copy_ca", description="Copy CA", show=True)
                self.bind("ctrl+shift+c", "copy_ca", show=False)
                
            except: pass

            
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

    # Removed action_switch_to_volume

    async def action_focus_search(self) -> None:
        """Switch to New Tokens tab and focus search."""
        self.query_one(TabbedContent).active = "new"
        try:
            self.query_one("#search_input").focus()
        except Exception:
            self.notify("Search input not found.", severity="error")
    
    async def action_trade_buy(self) -> None:
        """Switch Trade Panel to BUY mode and focus input."""
        try:
             panel = self.query_one("#trade_panel_view", TradePanel)
             panel.set_mode("buy")
             panel.query_one("#amount_input").focus()
        except: pass

    async def action_trade_sell(self) -> None:
        """Switch Trade Panel to SELL mode and focus input."""
        try:
             panel = self.query_one("#trade_panel_view", TradePanel)
             panel.set_mode("sell")
             panel.query_one("#amount_input").focus()
        except: pass

    async def action_trade_execute(self) -> None:
        """Trigger trade execution in the persistent Trade Panel."""
        try:
             panel = self.query_one("#trade_panel_view", TradePanel)
             panel.action_execute_trade()
        except: pass

    async def action_trade_token(self) -> None:
        """Focus the Trade Panel input for quick trading (Default)."""
        try:
             # Just focus the amount input in the panel
             panel = self.query_one("#trade_panel_view", TradePanel)
             panel.query_one("#amount_input").focus()
        except: pass


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
                            f.write(f"Event Handler Error: {e}\n{str(event)}\n")

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
         
         # 4. Update Database (Async / Fire-and-Forget)
         if hasattr(db, "connected") and db.connected:
             asyncio.create_task(db.update_token_event(event))
         
         # 3. Update Detail View (if applicable)
         try:
             detail_view = self.query_one("#trade_panel_view", TradePanel)
             if detail_view.token_data:
                 current_mint = detail_view.token_data.get("mint")
                 event_mint = event.get("mint")
                 
                 if current_mint and event_mint == current_mint:
                     # Fetch latest data from store (which process_event just updated)
                     updated_data = table.data_store.get(current_mint)
                     if updated_data:
                         # Direct call to update
                         detail_view.update_token(updated_data)
         except: pass
                     


    async def on_unmount(self):
        await self.api_client.close()
        await db.close()

    def compose(self) -> ComposeResult:
        yield SystemHeader(title=self.TITLE)
        with TabbedContent(initial="new"):
            with TabPane("New Tokens (n)", id="new"):
                # Split Container
                with Container(classes="split-container"):
                    yield TokenTable(title="New Tokens", id="table_new")
                    yield TradePanel(id="trade_panel_view")
             
             # Other tabs (placeholders or settings)
            with TabPane("Tracker (t)", id="tracker"):
                yield WalletTrackerView()
            with TabPane("Wallets (w)", id="wallets"):
                 yield WalletView(id="wallet_view")
            # Runners Tab Removed
            # with TabPane("Runners (v)", id="trending"):
            #    yield RunnersTable(id="table_trending")
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle token selection (Enter key or Click)."""
        self._handle_selection(event)

    async def action_select_token_action(self) -> None:
        """No-op action to display 'Select' in footer. Selection is handled by DataTable event."""
        pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Just update bindings or context, but DO NOT change Trade Panel data
        self.refresh_bindings()

    def _handle_selection(self, event: DataTable.RowSelected) -> None:
        """Handle explicit token selection."""
        self.refresh_bindings()
        try:
            row_key = event.row_key.value
            table_widget = self.query_one("#table_new", TokenTable)
            
            # 1. Update Checkbox State
            table_widget.select_token(row_key)
            
            # 2. Retrieve data
            token_data = table_widget.data_store.get(row_key)
            
            # 3. Update persistent Trade Panel
            if token_data:
                self.query_one("#trade_panel_view", TradePanel).update_token(token_data)
                
        except Exception as e:
            with open("debug_stream.log", "a") as f:
                 f.write(f"Selection Event Error: {e}\n")


    async def action_sort_new_mc(self):
        try:
             # Sort by marketCapSol
             self.query_one("#table_new", TokenTable).sort_data("marketCapSol", reverse=True)
        except: pass

    async def action_sort_new_vol(self):
        try:
             # Sort by volume_sol (implied need to track volume)
             # Note: volume_sol might be 0 for new tokens.
             self.query_one("#table_new", TokenTable).sort_data("volume_sol", reverse=True)
        except: pass

    async def action_sort_new_live(self):
        try:
             self.query_one("#table_new", TokenTable).reset_sort_live()
        except: pass


        
if __name__ == "__main__":
    app = PumpApp()
    app.run()
