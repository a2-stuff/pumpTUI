from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Input, Label, DataTable
from textual.screen import Screen, ModalScreen
from ..helpers import save_env_var, get_env_var, load_wallets, save_wallet, delete_wallet
from ..api import PumpPortalClient
import asyncio

class WalletView(Static):
    """Screen for managing multiple wallets."""

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.api_client = PumpPortalClient()
        self.wallets_table = DataTable()

    def compose(self) -> ComposeResult:
        with Vertical(id="wallet_container"):
            yield Static("Wallet Manager", classes="title")
            
            # Action Bar
            with Horizontal(classes="wallet-actions"):
                yield Button("Generate New", id="btn_generate", classes="compact-btn", variant="warning")
                yield Button("Refresh All", id="btn_refresh", classes="compact-btn")
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
        self.wallets_table.add_columns("Address", "Balance (SOL)", "API Key")
        self.load_wallets_into_table()

    def load_wallets_into_table(self) -> None:
        """Load wallets from json and populate table."""
        self.wallets_table.clear()
        wallets = load_wallets()
        
        for w in wallets:
            pub = w.get("walletPublicKey", "Unknown")
            api_key = w.get("apiKey", "N/A")
            # Mask API Key
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 10 else api_key
            balance = w.get("balance", "Check...")
            
            self.wallets_table.add_row(pub, str(balance), masked_key, key=pub)
            
        # Trigger balance check for all
        self.check_all_balances()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_generate":
            self.generate_wallet()
        elif event.button.id == "btn_import":
            self.import_wallet()
        elif event.button.id == "btn_refresh":
            self.check_all_balances()
        elif event.button.id == "btn_delete":
            self.delete_selected()

    def generate_wallet(self) -> None:
        asyncio.create_task(self._generate_task())

    async def _generate_task(self):
        self.query_one("#status_msg", Static).update("Generating wallet...")
        try:
            data = await self.api_client.create_wallet()
            if "walletPublicKey" in data:
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

        wallet_data = {
            "walletPublicKey": pub.strip(), 
            "privateKey": pk.strip(),
            "apiKey": "Imported"
        }
        save_wallet(wallet_data)
        self.load_wallets_into_table()
        self.query_one("#input_pk", Input).value = ""
        self.query_one("#input_pub", Input).value = ""
        self.query_one("#status_msg", Static).update("Wallet Imported.")

    def delete_selected(self) -> None:
        try:
            row_key = self.wallets_table.get_cursor_row_key()
            if row_key:
                pub_key = row_key.value
                delete_wallet(pub_key)
                self.load_wallets_into_table()
                self.query_one("#status_msg", Static).update(f"Deleted {pub_key}")
        except:
            self.query_one("#status_msg", Static).update("Select a wallet to delete.")

    def check_all_balances(self) -> None:
        wallets = load_wallets()
        for w in wallets:
            pub = w.get("walletPublicKey")
            if pub and not pub.startswith("Imported"):
                asyncio.create_task(self._update_balance(pub))

    async def _update_balance(self, pub_key: str):
        try:
            bal = await self.api_client.get_sol_balance(pub_key)
            # Update json?
            # Ideally we don't save volatile balance to json, just update UI.
            # But updating UI requires finding the row.
            self.wallets_table.update_cell(pub_key, "Balance (SOL)", f"{bal:.4f}")
        except:
             self.wallets_table.update_cell(pub_key, "Balance (SOL)", "Error")
