from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Static, Button, Input, Label, DataTable
from textual.widget import Widget
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from ..helpers import save_env_var, get_env_var 
from ..api import PumpPortalClient
from ..database import db # Import DB
import asyncio
import os

class WalletView(Vertical):
    """Container for wallet management."""
    
    BINDINGS = [
        Binding("g", "generate_new", "Generate New"),
        Binding("r", "refresh_all", "Refresh All"),
        Binding("c", "copy_address", "Copy Address"),
        Binding("d", "delete_active", "Delete Active"),
    ]

    def __init__(self, id: str = None):
        # Allow passing custom ID, but default to wallet_container for CSS
        super().__init__(id=id or "wallet_container")
        self.api_client = PumpPortalClient()
        self.column_keys = {}
        self.selected_wallets = set() # Safety for legacy code

    def compose(self) -> ComposeResult:
        yield Static("Wallet Manager", classes="title")
            
        with Horizontal(classes="wallet-actions"):
            yield Button("Generate New [g]", id="btn_generate", classes="compact-btn", variant="warning")
            yield Button("Refresh All [r]", id="btn_refresh", classes="compact-btn")
            yield Button("Copy Address [c]", id="btn_copy", classes="compact-btn")
            yield Button("Delete Active [d]", id="btn_delete", classes="compact-btn", variant="error")
        
        # Table with explicit ID for CSS targets
        yield DataTable(id="wallets_table")

        with Horizontal(classes="import-area"):
            yield Input(placeholder="Private Key", password=True, id="input_pk", classes="input-pk")
            yield Input(placeholder="Public Key (Required)", id="input_pub", classes="input-pk")
            yield Button("Import", id="btn_import", classes="compact-btn")
            
        yield Static("", id="status_msg")

    # Action Wrappers
    def action_generate_new(self) -> None:
        self.generate_wallet()
        
    def action_refresh_all(self) -> None:
        self.check_all_balances()
        
    def action_copy_address(self) -> None:
        asyncio.create_task(self.copy_selected_address())
        
    def action_delete_active(self) -> None:
        self.delete_active()
        
    def delete_active(self) -> None:
        asyncio.create_task(self._delete_active_task())

    async def _delete_active_task(self):
        try:
            active_doc = await db.settings.find_one({"key": "active_wallet"})
            active_pub = active_doc.get("value") if active_doc else None
            
            if not active_pub:
                 self.app.notify("No active wallet found to delete.", severity="warning")
                 return
            
            await db.wallets.delete_one({"walletPublicKey": active_pub})
            await db.settings.delete_one({"key": "active_wallet"}) # Unset active
            
            self.load_wallets_into_table()
            self.app.notify(f"Deleted active wallet: {active_pub[:8]}...", severity="information")
        except Exception as e:
            self.app.notify(f"Delete Error: {e}", severity="error")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#wallets_table", DataTable)
            table.cursor_type = "row"
            cols = table.add_columns("Active", "Address", "Balance (SOL)", "Created", "Txs")
            self.column_keys = {
                "Active": cols[0],
                "Address": cols[1],
                "Balance (SOL)": cols[2],
                "Created": cols[3],
                "Txs": cols[4]
            }
            self.load_wallets_into_table()
        except Exception as e:
             self.app.notify(f"WalletView Mount Error: {e}", severity="error")

    def load_wallets_into_table(self) -> None:
        """Load wallets from DB and populate table."""
        asyncio.create_task(self._load_wallets_task())

    async def _load_wallets_task(self):
        try:
            # Wait for DB
            for _ in range(10):
                if db.connected: break
                await asyncio.sleep(0.5)
            
            table = self.query_one("#wallets_table", DataTable)
            table.clear()
            
            wallets = await db.get_wallets()
            active_key_doc = await db.settings.find_one({"key": "active_wallet"})
            active_pub = active_key_doc.get("value") if active_key_doc else None
            
            for w in wallets:
                pub = w.get("walletPublicKey", "Unknown")
                balance = w.get("balance", "Check...")
                
                # Format timestamp
                created_raw = w.get("created_at", "N/A")
                created_str = str(created_raw)
                if hasattr(created_raw, "strftime"):
                    created_str = created_raw.strftime("%Y-%m-%d %H:%M")
                
                txs = w.get("tx_count", "0")

                is_active = (pub == active_pub)
                active_str = "[green][X][/]" if is_active else "[ ]"
                
                table.add_row(active_str, pub, str(balance), created_str, str(txs), key=pub)
                
            self.check_all_balances()
        except Exception as e:
            try:
                msg = self.query_one("#status_msg", Static)
                msg.update(f"Load Error: {e}")
            except: pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_generate":
            self.generate_wallet()
        elif event.button.id == "btn_import":
            self.import_wallet()
        elif event.button.id == "btn_refresh":
            self.check_all_balances()
        elif event.button.id == "btn_copy":
            asyncio.create_task(self.copy_selected_address())
        elif event.button.id == "btn_delete":
            self.delete_active()
    
    # ... copy methods ...
    
    async def copy_selected_address(self) -> None:
        """Copy the selected wallet's address to clipboard without blocking."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            if table.cursor_row < 0:
                self.app.notify("Select a wallet row first.", severity="warning")
                return
                
            row_key = table.get_cursor_row_key()
            if not row_key: return
            pub_key = str(row_key.value).strip()

            # Attempt all methods
            success = await self._perform_copy(pub_key)

            if success:
                self.app.notify("Address Copied!", severity="information")
            else:
                self.app.notify(f"Clipboard restricted. Address: {pub_key}", timeout=10)
        except Exception as e:
            self.app.notify(f"Copy Error: {e}", severity="error")

    async def _perform_copy(self, text: str) -> bool:
        """Centralized copy logic used by both app and wallet view."""
        # Step 1: OSC 52
        try:
            import base64, sys
            enc = base64.b64encode(text.encode()).decode()
            # Try writing to sys.stdout and also the app console
            # In Textual, app.console is the safer place
            self.app.console.file.write(f"\033]52;c;{enc}\a")
            self.app.console.file.flush()
        except: pass

        # Step 2: System commands
        import os
        targets = []
        if os.getenv("WAYLAND_DISPLAY"): 
            targets.append(['wl-copy'])
        if os.getenv("DISPLAY"): 
            targets.append(['xclip', '-selection', 'clipboard'])
            targets.append(['xclip', '-selection', 'primary'])
            targets.append(['xsel', '-ib'])
        targets.append(['pbcopy'])

        for cmd in targets:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await asyncio.wait_for(proc.communicate(input=text.encode()), timeout=1.0)
                if proc.returncode == 0:
                    return True
            except: continue
        return False

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Handle cell clicks for active status."""
        try:
            row_key = event.row_key.value
            col_index = event.coordinate.column
            
            # Column 0 is "Active"
            if col_index == 0:
                self._set_active_wallet_action(str(row_key))
        except Exception:
            pass

    def _set_active_wallet_action(self, pub_key: str) -> None:
        asyncio.create_task(self._set_active_task(pub_key))

    async def _set_active_task(self, pub_key: str):
        await db.settings.update_one(
             {"key": "active_wallet"},
             {"$set": {"value": pub_key}},
             upsert=True
        )
        self.load_wallets_into_table()
        try:
            self.query_one("#status_msg", Static).update(f"Active wallet set: {pub_key}")
        except: pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key) to set active wallet."""
        try:
            row_key = event.row_key
            if row_key:
                pub_key = str(row_key.value)
                self._set_active_wallet_action(pub_key)
        except Exception:
            pass

    def generate_wallet(self) -> None:
        asyncio.create_task(self._generate_task())

    async def _generate_task(self):
        self.query_one("#status_msg", Static).update("Generating wallet...")
        try:
            data = await self.api_client.create_wallet()
            if "walletPublicKey" in data:
                # API usually gives raw privateKey, we use db.save_wallet which encrypts it
                pk = data.get("privateKey")
                pub = data.get("walletPublicKey")
                
                await db.save_wallet("Generated", pk, pub)
                self.load_wallets_into_table()
                self.query_one("#status_msg", Static).update("Wallet Generated!")
            else:
                self.query_one("#status_msg", Static).update(f"Error: {data}")
        except Exception as e:
            self.query_one("#status_msg", Static).update(f"Error: {e}")

    def import_wallet(self) -> None:
        asyncio.create_task(self._import_task())

    async def _import_task(self):
        pk = self.query_one("#input_pk", Input).value
        pub = self.query_one("#input_pub", Input).value
        
        if not pk or not pub:
            self.query_one("#status_msg", Static).update("Enter both Private and Public Keys.")
            return

        await db.save_wallet("Imported", pk.strip(), pub.strip())
        self.load_wallets_into_table()
        
        self.query_one("#input_pk", Input).value = ""
        self.query_one("#input_pub", Input).value = ""
        self.query_one("#status_msg", Static).update("Wallet Imported.")



    def check_all_balances(self) -> None:
        """Fetch balances via batch RPC and tx counts individually."""
        asyncio.create_task(self._balance_task())

    async def _balance_task(self):
        wallets = await db.get_wallets()
        pub_keys = [w.get("walletPublicKey") for w in wallets if w.get("walletPublicKey")]
        
        if not pub_keys:
            return
            
        await self._process_batch_updates(pub_keys)

    async def _process_batch_updates(self, pub_keys: list[str]) -> None:
        try:
            # 1. Batch fetch balances (Optimized)
            balances = await self.api_client.get_batch_balances(pub_keys)
            
            # Update Table with Balances
            table = self.query_one("#wallets_table", DataTable)
            bal_col = self.column_keys.get("Balance (SOL)")
            
            if bal_col:
                for pub, bal in balances.items():
                    try: 
                        table.update_cell(pub, bal_col, f"{bal:.4f}")
                    except: pass
            
            # 2. Fetch Tx Counts (Still individual for now, but parallel)
            # We can run these concurrently
            tx_col = self.column_keys.get("Txs")
            if tx_col:
                async def _update_tx(pub):
                    try:
                        count = await self.api_client.get_tx_count(pub)
                        try: table.update_cell(pub, tx_col, str(count))
                        except: pass
                    except: pass
                
                # Limit concurrency to avoid rate limits
                # chunks of 5
                chunk_size = 5
                for i in range(0, len(pub_keys), chunk_size):
                    chunk = pub_keys[i:i + chunk_size]
                    await asyncio.gather(*[_update_tx(p) for p in chunk])
                    
        except Exception as e:
            self.app.notify(f"Update error: {e}", severity="error")
