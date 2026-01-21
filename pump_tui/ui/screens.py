from textual.widgets import Label, Input, Button, Markdown, Static
from textual.containers import Vertical, Container, Horizontal, Grid
from textual.screen import ModalScreen, Screen
from textual.app import ComposeResult
from typing import Dict, Any, Callable
from typing import Dict, Any, Callable
from rich.text import Text
from datetime import datetime
import traceback

from ..config import config

class SettingsView(Container):
    can_focus = True
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
        
        # RPC Configuration Section
        yield Label("RPC Configuration", classes="setting-title")
        yield Vertical(
            Label("RPC URL:", classes="setting-label"),
            Input(placeholder="https://api.mainnet-beta.solana.com", value=config.rpc_url, id="rpc_url"),
            Button("Save RPC", variant="primary", id="save_rpc"),
            classes="setting-section"
        )
        
        # Trading Wallet: Managed in Wallets tab now
        yield Label("Trading Wallet", classes="setting-title")
        yield Static("Manage wallets in the 'Wallets' (w) tab.", classes="info-text")
        
        # Trading Defaults Section
        yield Label("Trading Defaults", classes="setting-title")
        yield Horizontal(
            Vertical(Label("Slippage %", classes="small-label"), Input(value=str(config.default_slippage), id="default_slippage"), classes="thresh-input"),
            Vertical(Label("Priority Fee", classes="small-label"), Input(value=str(config.default_priority_fee), id="default_priority_fee"), classes="thresh-input"),
            classes="setting-row"
        )
        yield Button("Save Trading Defaults", variant="primary", id="save_trading_defaults")

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
        
        elif event.button.id == "save_rpc":
            rpc_url = self.query_one("#rpc_url", Input).value.strip()
            if rpc_url:
                config.update_rpc(rpc_url)
                self.app.notify("RPC URL saved!")
            else:
                self.app.notify("Error: RPC URL cannot be empty.", variant="error")
        
        elif event.button.id == "save_trading_defaults":
            try:
                slippage = float(self.query_one("#default_slippage", Input).value)
                priority_fee = float(self.query_one("#default_priority_fee", Input).value)
                config.update_trading_defaults(slippage, priority_fee)
                self.app.notify("Trading defaults saved!")
            except ValueError:
                self.app.notify("Error: Please enter valid numbers.", variant="error")

class InfoView(Container):
    can_focus = True
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
    can_focus = True
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


class TradeModal(ModalScreen):
    """Modal screen for buying/selling tokens."""
    
    CSS = """
    TradeModal {
        align: center middle;
    }
    
    #trade_dialog {
        width: 60;
        height: auto;
        background: #1e1e2e;
        border: thick #89b4fa;
        padding: 1 2;
    }
    
    #trade_title {
        text-align: center;
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }
    
    #token_info {
        text-align: center;
        margin-bottom: 1;
        color: #a6adc8;
    }
    
    .trade_buttons {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    
    .trade_button {
        width: 1fr;
        margin: 0 1;
        background: #313244;
        color: #cdd6f4;
    }
    
    #buy_button.-active {
        background: #a6e3a1;
        color: #11111b;
        text-style: bold;
    }
    
    #sell_button.-active {
        background: #f38ba8;
        color: #11111b;
        text-style: bold;
    }
    
    .input_row {
        layout: horizontal;
        height: auto;
        margin: 1 0;
    }
    
    .input_label {
        width: 15;
        content-align: right middle;
        padding-right: 1;
        color: #cdd6f4;
    }
    
    .input_field {
        width: 1fr;
    }
    
    #estimated_amount {
        text-align: center;
        color: #fab387;
        margin-bottom: 1;
        text-style: bold;
        width: 100%;
    }
    
    #wallet_balance {
        text-align: center;
        color: #cdd6f4;
        margin-top: 1;
        border-top: solid #313244;
        padding-top: 1;
    }
    
    .action_buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    
    .action_button {
        width: 1fr;
        margin: 0 1;
    }
    
    #error_label {
        text-align: center;
        color: #f38ba8;
        margin: 1 0;
    }
    
    #success_label {
        text-align: center;
        color: #a6e3a1;
        margin: 1 0;
    }
    
    .trade_counts_row {
        text-align: center;
        margin-bottom: 1;
    }
    
    .count-label {
        width: 1fr;
        content-align: center middle;
    }
    
    .green { color: #a6e3a1; }
    .red { color: #f38ba8; }
    
    #execute_button {
        background: #a6e3a1;
        color: #1e1e2e;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        ("e", "execute_trade", "Execute"),
        ("c", "cancel_trade", "Cancel"),
        ("b", "toggle_buy", "Buy Mode"),
        ("s", "toggle_sell", "Sell Mode"),
    ]
    
    def __init__(self, token_data: Dict[str, Any], data_provider: Callable[[str], Dict[str, Any]] = None):
        super().__init__()
        self.token_data = token_data
        self.data_provider = data_provider
        self.trade_mode = "buy"  # "buy" or "sell"
        self.is_processing = False
        self.active_wallet = config.get_active_wallet()
    
    def compose(self) -> ComposeResult:
        mint = self.token_data.get("mint", "N/A")
        name = self.token_data.get("name", "Unknown")
        symbol = self.token_data.get("symbol", "???")
        mc_sol = self.token_data.get("marketCapSol", 0)
        
        # Calculate USD Stats
        sol_price = getattr(self.app, "sol_price", 0.0)
        mc_usd_str = ""
        if sol_price > 0:
            mc_usd = mc_sol * sol_price
            mc_usd_str = f"(${mc_usd:,.0f})"
        
        # Truncate mint for display
        display_mint = f"{mint[:4]}...{mint[-4:]}" if len(mint) > 10 else mint
        
        with Container(id="trade_dialog"):
            yield Label(f"Trade: {name} (${symbol})", id="trade_title")
            
            yield Label(f"Mint: {display_mint} | MC: {mc_sol:,.2f} SOL {mc_usd_str}", id="token_info")
            
            # Active Wallet Display
            active_pub = self.active_wallet.get("walletPublicKey", "No Wallet Found")
            active_display = f"{active_pub[:6]}...{active_pub[-6:]}" if len(active_pub) > 12 else active_pub
            yield Label(f"Active Wallet: [#f9e2af]{active_display}[/]", id="active_wallet_info")
            
            # Info Row: Tx and Holders
            with Horizontal(classes="trade_counts_row"):
                yield Label("Tx: 0", id="tx_label", classes="count-label")
                yield Label("Hold: 0", id="holders_label", classes="count-label")

            # Info Row 2: Trade Counts (Buys/Sells)
            with Horizontal(classes="trade_counts_row"):
                yield Label("Buys: 0", id="buys_label", classes="count-label green")
                yield Label("Sells: 0", id="sells_label", classes="count-label red")
            
            # Buy/Sell toggle buttons (Moved below counters)
            with Horizontal(classes="trade_buttons"):
                yield Button("BUY (b)", id="buy_button", classes="trade_button -active")
                yield Button("SELL (s)", id="sell_button", classes="trade_button")
            
            # Amount input
            with Horizontal(classes="input_row"):
                yield Label("Amount:", classes="input_label")
                yield Input(value="1.0", id="amount_input", classes="input_field", restrict=r"^[0-9.]*%?$")
            
            # Denomination label
            yield Label("(SOL for buy, Tokens or % for sell)", id="denom_label", classes="input_label")
            
            # Slippage input
            with Horizontal(classes="input_row"):
                yield Label("Slippage (%):", classes="input_label")
                yield Input(value=str(config.default_slippage) + "%", id="slippage_input", classes="input_field", restrict=r"^[0-9.]*%?$")
            
            # Priority fee input
            with Horizontal(classes="input_row"):
                yield Label("Priority Fee:", classes="input_label")
                yield Input(value=str(config.default_priority_fee), id="fee_input", classes="input_field", restrict=r"^[0-9.]*$")
            
            # Estimated amount
            yield Label("", id="estimated_amount")
            
            # Error/Success messages
            yield Label("", id="error_label")
            yield Label("", id="success_label")
            
            # Action buttons
            with Horizontal(classes="action_buttons"):
                yield Button("Execute Trade (e)", variant="success", id="execute_button", classes="action_button")
                yield Button("Cancel (c)", variant="error", id="cancel_button", classes="action_button")
            
            # Wallet Balance
            yield Label("Loading wallet...", id="wallet_balance")

    def on_mount(self) -> None:
        """Start updates on mount."""
        # Update estimation initially
        self.update_estimation()
        # Start real-time MC updates
        self.update_mc_ticker = self.set_interval(1.0, self.update_market_stats)
        # Fetch wallet balance
        self.run_worker(self.fetch_wallet_balance())

    def update_market_stats(self) -> None:
        """Update Market Cap with live SOL price."""
        try:
            mc_sol = self.token_data.get("marketCapSol", 0)
            sol_price = getattr(self.app, "sol_price", 0.0)
            
            mc_usd_str = ""
            mc_style = "white"
            
            if sol_price > 0:
                mc_usd = mc_sol * sol_price
                mc_usd_str = f"(${mc_usd:,.0f})"
                
                # Apply coloring logic from config like in table
                mc_thresh = config.thresholds["mc"]
                if mc_sol > mc_thresh["yellow"]:
                    mc_style = "green"
                elif mc_sol >= mc_thresh["red"]:
                    mc_style = "yellow"
                else:
                    mc_style = "red"
            
            self.query_one("#token_info", Label).update(
                Text.from_markup(f"Mint: {self.token_data.get('mint')[:4]}... | MC: [{mc_style}]{mc_sol:,.2f} SOL {mc_usd_str}[/]")
            )
            
            # Update Trade Counts (Fetch fresh from data provider)
            mint = self.token_data.get("mint")
            fresh_data = None
            
            if self.data_provider:
                fresh_data = self.data_provider(mint)
            
            if fresh_data:
                # Update Buys/Sells
                buys = fresh_data.get("buys_count", 0)
                sells = fresh_data.get("sells_count", 0)
                self.query_one("#buys_label", Label).update(f"Buys: {buys}")
                self.query_one("#sells_label", Label).update(f"Sells: {sells}")
                
                # Update Tx/Holders with coloring
                tx_count = fresh_data.get("tx_count", 0)
                tx_thresh = config.thresholds["tx"]
                tx_style = "green" if tx_count > tx_thresh["yellow"] else "yellow" if tx_count >= tx_thresh["red"] else "red"
                self.query_one("#tx_label", Label).update(Text.from_markup(f"Tx: [{tx_style}]{tx_count}[/]"))
                
                traders = fresh_data.get("traders", set())
                h_count = len(traders)
                h_thresh = config.thresholds["holders"]
                h_style = "green" if h_count > h_thresh["yellow"] else "yellow" if h_count >= h_thresh["red"] else "red"
                self.query_one("#holders_label", Label).update(Text.from_markup(f"Hold: [{h_style}]{h_count}[/]"))

                # Update MC variable for estimation reliability
                if "marketCapSol" in fresh_data:
                    self.token_data["marketCapSol"] = fresh_data["marketCapSol"]

            # Force re-run estimation as price/MC might change
            self.update_estimation()
            
        except Exception:
            pass

    async def fetch_wallet_balance(self) -> None:
        """Fetch and display wallet SOL balance."""
        if not self.active_wallet:
             self.query_one("#wallet_balance", Label).update("No active wallet selected")
             return
        
        pub_key = self.active_wallet.get("walletPublicKey")
        if not pub_key:
             self.query_one("#wallet_balance", Label).update("Invalid wallet data")
             return

        try:
            # Simple RPC call using the same logic as TradingClient
            from ..trading import TradingClient
            # Dummy key just for balance check if needed, but we used requests before.
            # Using httpx directly is cleaner.
            
            import httpx
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "getBalance",
                "params": [pub_key]
            }
            # Increased timeout to 10s as user reported issues
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                response = await http_client.post(config.rpc_url, json=payload)
                if response.status_code == 200:
                    val = response.json().get("result", {}).get("value")
                    if val is not None:
                         bal_sol = val / 1_000_000_000
                         self.query_one("#wallet_balance", Label).update(f"Balance ({pub_key[:4]}..): {bal_sol:.4f} SOL")
                    else:
                         self.query_one("#wallet_balance", Label).update("Balance: 0.00 SOL (Empty)")
                else:
                    self.query_one("#wallet_balance", Label).update(f"Error HTTP {response.status_code}")
        except ImportError:
             self.query_one("#wallet_balance", Label).update("Error: 'solders' module missing?")
        except Exception as e:
             # Clean up error message
             err_str = str(e)
             if "No module named" in err_str:
                 err_str = "Error: Missing dependencies"
             self.query_one("#wallet_balance", Label).update(f"Wallet Error: {err_str[:25]}")
    
    def action_toggle_buy(self) -> None:
        """Switch to Buy mode."""
        self.trade_mode = "buy"
        self.query_one("#buy_button", Button).add_class("-active")
        self.query_one("#sell_button", Button).remove_class("-active")
        self.query_one("#amount_input", Input).value = "1.0"
        self.query_one("#denom_label", Label).update("(SOL for buy)")
        self.update_estimation()
        
    def action_toggle_sell(self) -> None:
        """Switch to Sell mode."""
        self.trade_mode = "sell"
        self.query_one("#sell_button", Button).add_class("-active")
        self.query_one("#buy_button", Button).remove_class("-active")
        self.query_one("#amount_input", Input).value = "100%"
        self.query_one("#denom_label", Label).update("(Tokens or % for sell)")
        self.update_estimation()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if self.is_processing:
            return
        
        if event.button.id == "buy_button":
            self.trade_mode = "buy"
            self.query_one("#buy_button", Button).add_class("-active")
            self.query_one("#sell_button", Button).remove_class("-active")
            self.query_one("#amount_input", Input).value = "1.0"
            self.query_one("#denom_label", Label).update("(SOL for buy)")
            self.update_estimation()
        
        elif event.button.id == "sell_button":
            self.trade_mode = "sell"
            self.query_one("#sell_button", Button).add_class("-active")
            self.query_one("#buy_button", Button).remove_class("-active")
            self.query_one("#amount_input", Input).value = "100%"
            self.query_one("#denom_label", Label).update("(Tokens or % for sell)")
            self.update_estimation()
        
        elif event.button.id == "cancel_button":
            self.dismiss(None)
        
        elif event.button.id == "execute_button":
            self.execute_trade()
    
    def execute_trade(self):
        """Execute the trade asynchronously."""
        if self.is_processing:
            return
        
        # Clear previous messages
        self.query_one("#error_label", Label).update("")
        self.query_one("#success_label", Label).update("")
        
        # Validate config
        if not self.active_wallet or not self.active_wallet.get("privateKey"):
            self.query_one("#error_label", Label).update("❌ No active wallet selected in Wallets tab!")
            return
        
        # Get inputs
        try:
            amount_str = self.query_one("#amount_input", Input).value.strip()
            # Strip % for slippage and fee parsing
            slip_str = self.query_one("#slippage_input", Input).value.replace("%", "").strip()
            fee_str = self.query_one("#fee_input", Input).value.strip()
            
            slippage = float(slip_str) if slip_str else config.default_slippage
            priority_fee = float(fee_str) if fee_str else config.default_priority_fee
        except ValueError:
            self.query_one("#error_label", Label).update("❌ Invalid numeric values!")
            return
        
        # Parse amount
        denominated_in_sol = self.trade_mode == "buy"
        if self.trade_mode == "sell" and amount_str.endswith("%"):
            # For percentage sells, we need to get actual balance
            # For now, just pass the percentage string to the API
            amount_str = amount_str
        
        try:
            if amount_str.endswith("%"):
                amount = amount_str  # API supports percentage strings
            else:
                amount = float(amount_str)
        except ValueError:
            self.query_one("#error_label", Label).update("❌ Invalid amount!")
            return
        
        self.is_processing = True
        self.query_one("#execute_button", Button).disabled = True
        self.query_one("#execute_button", Button).label = "Processing..."
        
        # Run async trade
        import asyncio
        asyncio.create_task(self._execute_trade_async(
            mint=self.token_data.get("mint"),
            action=self.trade_mode,
            amount=amount,
            denominated_in_sol=denominated_in_sol,
            slippage=slippage,
            priority_fee=priority_fee
        ))
    
    async def _execute_trade_async(
        self,
        mint: str,
        action: str,
        amount: Any,
        denominated_in_sol: bool,
        slippage: float,
        priority_fee: float
    ):
        """Execute trade in background and update UI."""
        
        try:
            from ..trading import TradingClient
            # Initialize trading client
            priv_key = self.active_wallet.get("privateKey")
            client = TradingClient(
                rpc_url=config.rpc_url,
                wallet_private_key=priv_key
            )
            
            # Execute trade
            signature = await client.execute_trade(
                mint=mint,
                action=action,
                amount=amount,
                denominated_in_sol=denominated_in_sol,
                slippage=slippage,
                priority_fee=priority_fee
            )
            
            # Show success
            self.query_one("#success_label", Label).update(
                f"✅ Transaction sent!\nSignature: {signature[:8]}...{signature[-8:]}"
            )
            self.query_one("#error_label", Label).update("")
            
            # Log full signature for user reference
            with open("trades.log", "a") as f:
                f.write(f"{action.upper()} {mint} - https://solscan.io/tx/{signature}\n")
            
        except Exception as e:
            self.query_one("#error_label", Label).update(f"❌ Error: {str(e)[:60]}")
            self.query_one("#success_label", Label).update("")
            # Log full error for debugging
            with open("error.log", "a") as f:
                pubkey = self.active_wallet.get("walletPublicKey", "Unknown")
                f.write(f"\n--- Trade Error {datetime.now()} ---\n")
                f.write(f"Wallet: {pubkey} | Action: {action} | Mint: {mint}\n")
                traceback.print_exc(file=f)
        
        finally:
            self.is_processing = False
            self.query_one("#execute_button", Button).disabled = False
            self.query_one("#execute_button", Button).label = "Execute Trade (e)"
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Update estimation and handle automatic percentage suffixes."""
        input_id = event.input.id
        value = event.value
        
        # Prevent recursion if we update the value
        if hasattr(self, "_ignoring_input_change") and self._ignoring_input_change:
            return

        if input_id == "amount_input":
            # Auto-suffix % for Sell mode if it contains numbers and no %
            if self.trade_mode == "sell" and value and value[-1].isdigit() and "%" not in value:
                self._ignoring_input_change = True
                event.input.value = value + "%"
                self._ignoring_input_change = False
            self.update_estimation()
            
        elif input_id == "slippage_input":
            # Auto-suffix % for slippage
            if value and value[-1].isdigit() and "%" not in value:
                self._ignoring_input_change = True
                event.input.value = value + "%"
                self._ignoring_input_change = False
            self.update_estimation()

    def update_estimation(self) -> None:
        """Calculate and display estimated tokens/SOL."""
        try:
            amount_str = self.query_one("#amount_input", Input).value.strip()
            if not amount_str:
                self.query_one("#estimated_amount", Label).update("")
                return
            
            mc_sol = self.token_data.get("marketCapSol", 0)
            if mc_sol <= 0:
                return

            # Price per token (Total Supply 1B)
            price_sol = mc_sol / 1_000_000_000
            
            if self.trade_mode == "buy":
                # Input is SOL -> Calculate Tokens
                try:
                    sol_in = float(amount_str)
                    tokens_out = sol_in / price_sol
                    self.query_one("#estimated_amount", Label).update(f"Est. Tokens: {tokens_out:,.2f}")
                except ValueError:
                    self.query_one("#estimated_amount", Label).update("")
            
            else: # Sell
                # Input is Tokens (or %) -> Calculate SOL
                if amount_str.endswith("%"):
                    self.query_one("#estimated_amount", Label).update("Selling percentage of holdings")
                else:
                    try:
                        tokens_in = float(amount_str)
                        sol_out = tokens_in * price_sol
                        self.query_one("#estimated_amount", Label).update(f"Est. SOL: {sol_out:.4f}")
                    except ValueError:
                        self.query_one("#estimated_amount", Label).update("")
        except Exception:
            pass
            
    def action_execute_trade(self) -> None:
        """Execute trade via keybind."""
        self.execute_trade()
        
    def action_cancel_trade(self) -> None:
        """Cancel trade via keybind."""
        self.dismiss(None)
