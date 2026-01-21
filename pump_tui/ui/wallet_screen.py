from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Input, Label, DataTable
from textual.widget import Widget
from textual.screen import Screen, ModalScreen
from ..helpers import save_env_var, get_env_var, load_wallets, save_wallet, delete_wallet, set_active_wallet
from ..api import PumpPortalClient
import asyncio

class WalletView(Vertical):
    """Screen for managing multiple wallets."""

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.api_client = PumpPortalClient()
        self.wallets_table = DataTable()

    def compose(self) -> ComposeResult:
        yield Static("Wallet Manager", classes="title")
            
        # Action Bar
        with Horizontal(classes="wallet-actions"):
            yield Button("Generate New", id="btn_generate", classes="compact-btn", variant="warning")
            yield Button("Refresh All", id="btn_refresh", classes="compact-btn")
            yield Button("Copy Address", id="btn_copy", classes="compact-btn")
            yield Button("Delete Selected", id="btn_delete", classes="compact-btn", variant="error")
        # Table
        yield self.wallets_table

        # Import Section
        with Horizontal(classes="import-area"):
            yield Input(placeholder="Private Key", password=True, id="input_pk", classes="input-pk")
            yield Input(placeholder="Public Key (Required)", id="input_pub", classes="input-pk")
            yield Button("Import", id="btn_import", classes="compact-btn")
            
        yield Static("", id="status_msg")

    def on_mount(self) -> None:
        self.wallets_table.cursor_type = "row"
        self.wallets_table.add_columns("Active", "Address", "Balance (SOL)", "Created", "Txs")
        self.load_wallets_into_table()

    def load_wallets_into_table(self) -> None:
        """Load wallets from json and populate table."""
        self.wallets_table.clear()
        wallets = load_wallets()
        
        for w in wallets:
            pub = w.get("walletPublicKey", "Unknown")
            balance = w.get("balance", "Check...")
            
            # Format timestamp
            created_raw = w.get("created_at", "N/A")
            created_str = created_raw
            if isinstance(created_raw, (int, float)):
                from datetime import datetime
                created_str = datetime.fromtimestamp(created_raw).strftime("%Y-%m-%d %H:%M")
            
            txs = w.get("tx_count", "...")

            is_active = w.get("active", False)
            active_str = "[green][X][/]" if is_active else "[ ]"
            
            self.wallets_table.add_row(active_str, pub, str(balance), created_str, str(txs), key=pub)
            
        # Trigger balance check for all
        self.check_all_balances()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_generate":
            self.generate_wallet()
        elif event.button.id == "btn_import":
            self.import_wallet()
        elif event.button.id == "btn_refresh":
            self.check_all_balances()
        elif event.button.id == "btn_copy":
            self.copy_selected_address()
        elif event.button.id == "btn_delete":
            self.delete_selected()

    def copy_selected_address(self) -> None:
        """Copy the selected wallet's address to clipboard."""
        try:
            # Check for current row
            if self.wallets_table.cursor_row < 0:
                self.app.notify("Select a wallet row first by clicking it.", variant="warning")
                return
                
            row_key = self.wallets_table.get_cursor_row_key()
            if row_key:
                pub_key = str(row_key.value)
                
                # Robust Copy Logic
                success = False
                try:
                    import base64
                    import sys
                    encoded = base64.b64encode(pub_key.encode('utf-8')).decode('utf-8')
                    sys.stdout.write(f"\033]52;c;{encoded}\a")
                    sys.stdout.flush()
                    success = True
                except: pass
                
                if not success:
                    try:
                        import subprocess
                        subprocess.run(['wl-copy'], input=pub_key.encode(), capture_output=True)
                        success = True
                    except: pass
                
                if not success:
                    try:
                        import subprocess
                        subprocess.run(['pbcopy'], input=pub_key.encode(), capture_output=True)
                        success = True
                    except: pass

                if success:
                    self.app.notify(f"Address Copied: {pub_key[:8]}...", variant="success")
                else:
                    self.app.notify(f"Clipboard Error. Address: {pub_key}", timeout=10)
            else:
                self.app.notify("Could not identify selected wallet key.", variant="error")
        except Exception as e:
            self.app.notify(f"Error copying address: {e}", variant="error")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to set active wallet."""
        try:
            row_key = event.row_key
            if row_key:
                pub_key = row_key.value
                set_active_wallet(str(pub_key))
                self.load_wallets_into_table()
                self.query_one("#status_msg", Static).update(f"Active wallet set: {pub_key}")
        except Exception:
            pass

    def generate_wallet(self) -> None:
        asyncio.create_task(self._generate_task())

    async def _generate_task(self):
        self.query_one("#status_msg", Static).update("Generating wallet...")
        try:
            data = await self.api_client.create_wallet()
            if "walletPublicKey" in data:
                # Remove apiKey from data before saving - we only want it in .env
                data.pop("apiKey", None)
                data["created_at"] = asyncio.get_event_loop().time() # Use real time if possible, but let's use time.time()
                import time
                data["created_at"] = time.time()
                save_wallet(data)
                self.load_wallets_into_table()
                self.query_one("#status_msg", Static).update("Wallet Generated!")
            else:
                self.query_one("#status_msg", Static).update(f"Error: {data}")
        except Exception as e:
            self.query_one("#status_msg", Static).update(f"Error: {e}")

    def import_wallet(self) -> None:
        pk = self.query_one("#input_pk", Input).value
        pub = self.query_one("#input_pub", Input).value
        
        if not pk or not pub:
            self.query_one("#status_msg", Static).update("Enter both Private and Public Keys.")
            return

        import time
        wallet_data = {
            "walletPublicKey": pub.strip(), 
            "privateKey": pk.strip(),
            "created_at": time.time()
        }
        save_wallet(wallet_data)
        self.load_wallets_into_table()
        self.query_one("#input_pk", Input).value = ""
        self.query_one("#input_pub", Input).value = ""
        self.query_one("#status_msg", Static).update("Wallet Imported.")

    def delete_selected(self) -> None:
        try:
            if self.wallets_table.cursor_row < 0:
                 self.app.notify("Select a wallet row first by clicking it.", variant="warning")
                 return
                 
            row_key = self.wallets_table.get_cursor_row_key()
            if row_key:
                pub_key = str(row_key.value)
                
                # Show status before cleanup
                self.query_one("#status_msg", Static).update(f"Deleting {pub_key[:8]}...")
                
                delete_wallet(pub_key)
                self.load_wallets_into_table()
                self.app.notify(f"Wallet Deleted: {pub_key[:8]}...", variant="success")
                self.query_one("#status_msg", Static).update("Wallet Deleted.")
            else:
                self.app.notify("Could not identify selected wallet to delete.", variant="error")
        except Exception as e:
            self.app.notify(f"Error deleting wallet: {e}", variant="error")

    def check_all_balances(self) -> None:
        wallets = load_wallets()
        for w in wallets:
            pub = w.get("walletPublicKey")
            if pub:
                asyncio.create_task(self._update_balance(pub))

    async def _update_balance(self, pub_key: str):
        try:
            # Update both balance and tx count
            bal_task = self.api_client.get_sol_balance(pub_key)
            tx_task = self.api_client.get_tx_count(pub_key)
            
            bal, tx_count = await asyncio.gather(bal_task, tx_task)
            
            # Update UI
            self.wallets_table.update_cell(pub_key, "Balance (SOL)", f"{bal:.4f}")
            self.wallets_table.update_cell(pub_key, "Txs", str(tx_count))
        except Exception:
             self.wallets_table.update_cell(pub_key, "Balance (SOL)", "Error")
             self.wallets_table.update_cell(pub_key, "Txs", "!")
