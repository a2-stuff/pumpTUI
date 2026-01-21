from textual.widgets import DataTable, Button, Label, Input, Pretty
from textual.containers import Horizontal, Vertical
from textual.app import ComposeResult
from textual.widget import Widget
from typing import Callable, Awaitable, List, Dict, Any

class TokenTable(Widget):
    """A widget to display a list of tokens with search."""

    def __init__(self, fetch_method: Callable[[], Awaitable[List[Dict[str, Any]]]] = None, title: str = "Tokens", id: str = None):
        super().__init__(id=id)
        self.fetch_method = fetch_method
        self.table_title = title
        self.table = DataTable()
        self.data_store: Dict[str, Dict[str, Any]] = {} # Store full token data
        self.column_keys = {} # Store ColumnKey objects
        
        # Pagination & Search
        self.history: List[Dict[str, Any]] = []
        self.filtered_history: List[Dict[str, Any]] = []
        self.current_filter = ""
        self.current_page = 1
        self.page_size = 35
        self.max_history = 1000

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search by Name, Ticker, or Mint...", id="search_input")
        yield self.table
        with Horizontal(classes="pagination-controls"):
            yield Button("< Newer", id="btn_newer", disabled=True)
            yield Label(f"Page {self.current_page}", id="page_label")
            yield Button("Older >", id="btn_older")

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        cols = self.table.add_columns("Token CA", "Name", "Ticker", "MC (SOL)", "Created")
        # Store MC column key specifically
        if len(cols) >= 4:
            self.column_keys["MC (SOL)"] = cols[3]
        
        if self.fetch_method:
            self.load_data()

    async def load_data(self) -> None:
        if not self.fetch_method:
            return
        try:
            items = await self.fetch_method()
            for item in items:
                self.process_event(item)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the list when input changes."""
        self.current_filter = event.value.lower()
        self.current_page = 1
        self.filter_history()
        self.render_page()

    def filter_history(self) -> None:
        """Re-build filtered_history based on current_filter."""
        if not self.current_filter:
            self.filtered_history = list(self.history)
        else:
            term = self.current_filter
            self.filtered_history = [
                item for item in self.history
                if term in item.get("name", "").lower()
                or term in item.get("symbol", "").lower()
                or term in item.get("mint", "").lower()
            ]

    def process_event(self, event: Dict[str, Any]) -> None:
        """Handle incoming event (New Token or Trade)."""
        # Distinguish between New Token and Trade
        # New Token has 'name', 'symbol', 'uri'.
        # Trade has 'txType', 'solAmount', 'marketCapSol', 'mint'.
        
        if "txType" in event and event["txType"] != "create":
            self.update_token_trade(event)
        else:
            # Assume new token if not a trade (and has mint)
            # OR if txType == "create"
            if "mint" in event:
                self.add_new_token(event)

    def update_token_trade(self, trade: Dict[str, Any]) -> None:
        """Update existing token data from a trade event."""
        mint = trade.get("mint")
        if not mint or mint not in self.data_store:
            return

        # Update store
        stored_item = self.data_store[mint]
        
        # Update Market Cap
        if "marketCapSol" in trade:
            new_mc = trade["marketCapSol"]
            stored_item["marketCapSol"] = new_mc
            stored_item["market_cap"] = new_mc # Normalized
            
            # Update Table if visible (mint is the row key)
            try:
                col_key = self.column_keys.get("MC (SOL)", "MC (SOL)")
                self.table.update_cell(mint, col_key, f"{new_mc:.2f}")
            except Exception:
                # Silently fail if row not in table (paginated out)
                pass

        # --- Aggregation Logic ---
        # Increment Tx Count
        stored_item["tx_count"] = stored_item.get("tx_count", 0) + 1
        
        # Update Volume
        sol_amt = trade.get("solAmount", 0)
        stored_item["volume_sol"] = stored_item.get("volume_sol", 0.0) + float(sol_amt)
        
        # Check Dev Sold
        creator = stored_item.get("creator")
        trader = trade.get("traderPublicKey")
        tx_type = trade.get("txType")
        
        if creator and trader and creator == trader and tx_type == "sell":
            stored_item["dev_sold"] = True
        # -------------------------

    def add_token(self, item: Dict[str, Any]) -> None:
        """Wrapper for backward compatibility or direct calls."""
        self.process_event(item)

    def add_new_token(self, item: Dict[str, Any]) -> None:
        """Add a token to the top of the history and update view if relevant."""
        mint = item.get("mint", "N/A")
        
        # Check if already exists?
        if mint in self.data_store:
            return # Ignore duplicates or update?

        # Store data
        # Initialize Aggregated Metrics
        item["tx_count"] = 1
        item["volume_sol"] = 0.0
        item["dev_sold"] = False
        item["creator"] = item.get("traderPublicKey", None)
        
        self.data_store[mint] = item

        
        # Add to history
        self.history.insert(0, item)
        if len(self.history) > self.max_history:
            removed = self.history.pop()
        
        # If matches current filter (or no filter), add to filtered list
        match = True
        if self.current_filter:
            term = self.current_filter
            match = (
                term in item.get("name", "").lower() 
                or term in item.get("symbol", "").lower() 
                or term in item.get("mint", "").lower()
            )
        
        if match:
            self.filtered_history.insert(0, item)
            # If filtered list gets too big? It's just a view.
            
            # Update view if we are on the first page
            if self.current_page == 1:
                # We can just prepend if it's the very first item
                # But to maintain page size accurately with pre-pending logic is tricky.
                # Easiest is to re-render page 1 if we are there.
                self.render_page()

    def render_page(self):
        """Render the current page from filtered history."""
        self.table.clear()
        
        source_list = self.filtered_history
        
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_items = source_list[start_idx:end_idx]
        
        for item in page_items:
            mint = item.get("mint", "N/A")
            name = item.get("name", "N/A")
            raw_symbol = item.get("symbol", "N/A")
            symbol = f"${raw_symbol}" if raw_symbol != "N/A" else "N/A"
            market_cap = f"{item.get('market_cap', 0):.2f}"
            if "marketCapSol" in item:
                 market_cap = f"{item.get('marketCapSol', 0):.2f}"
            
            created = str(item.get("created_timestamp", "N/A"))
            if "timestamp" in item:
                 try:
                     from datetime import datetime
                     ts = item.get("timestamp")
                     if isinstance(ts, (int, float)):
                         created = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                 except:
                     pass
            
            if created == "N/A":
                 created = item.get("_received_at", "?") 
                 if created == "?":
                     from datetime import datetime
                     created = datetime.now().strftime("%H:%M:%S")

            display_mint = mint
            if len(mint) > 10:
                display_mint = f"{mint[:4]}...{mint[-4:]}"
                
            self.table.add_row(display_mint, name, symbol, market_cap, created, key=mint)
        
        # Update controls
        self.query_one("#page_label", Label).update(f"Page {self.current_page} (Total: {len(source_list)})")
        self.query_one("#btn_newer", Button).disabled = (self.current_page <= 1)
        self.query_one("#btn_older", Button).disabled = (end_idx >= len(source_list))
        
        # self.table.cursor_type = "row" 
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        source_len = len(self.filtered_history)
        if event.button.id == "btn_newer":
            if self.current_page > 1:
                self.current_page -= 1
                self.render_page()
        elif event.button.id == "btn_older":
            if (self.current_page * self.page_size) < source_len:
                self.current_page += 1
                self.render_page()

    async def load_data(self) -> None:
        if not self.fetch_method:
            return
        # Initial load (if any)
        try:
            items = await self.fetch_method()
            for item in items:
                self.add_token(item)
        except Exception:
            pass
            
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        pass

from textual.widgets import Static

from .image_utils import fetch_token_metadata
import asyncio

class TokenDetail(Static):
    """Widget to display details of a selected token."""
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.current_token = None

    def compose(self) -> ComposeResult:
        with Vertical(id="detail_container"):
             yield Static("Select a token to view expanded details.", id="detail_content")

    def update_token(self, token_data: Dict[str, Any]) -> None:
        """Update the detail view with new token data."""
        self.current_token = token_data
        
        # Build content
        lines = [f"[b][u]Token Details[/u][/b]\n"]
        
        priority_keys = ["name", "symbol", "mint", "marketCapSol", "created_timestamp", "uri"]
        
        for key in priority_keys:
            if key in token_data:
                val = token_data[key]
                lines.append(f"[b]{key}:[/b] {val}")
        
        # Extended Metrics
        lines.append("") # Spacer
        
        # Tx Count
        tx_count = token_data.get("tx_count", 1)
        lines.append(f"[b]Tx Count:[/b] {tx_count}")
        
        # Volume
        vol = token_data.get("volume_sol", 0.0)
        lines.append(f"[b]Volume:[/b] {vol:.4f} SOL")
        
        # Dev Sold?
        dev_sold = token_data.get("dev_sold", False)
        dev_status = "[red]YES (SOLD)[/]" if dev_sold else "[green]NO (HOLDING)[/]"
        lines.append(f"[b]Dev Sold:[/b] {dev_status}")

        
        # Metadata / Image
        if "metadata" in token_data:
            meta = token_data["metadata"]
            lines.append("\n[b][u]Metadata (Live)[/u][/b]")
            
            if "image" in meta:
                 lines.append(f"[b]Image:[/b] [link={meta['image']}]View Token Image[/link]")
            
            if "description" in meta:
                desc = meta["description"]
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                lines.append(f"[b]Description:[/b] {desc}")
            
            # Socials
            social_links = []
            for s_key in ["twitter", "telegram", "website"]:
                if s_key in meta:
                    social_links.append(f"[link={meta[s_key]}]{s_key.capitalize()}[/link]")
            if social_links:
                lines.append(f"[b]Socials:[/b] {' | '.join(social_links)}")
        elif "uri" in token_data and "metadata_fetching" not in token_data:
            # Trigger fetch if URI exists and not already fetching/fetched
            token_data["metadata_fetching"] = True
            asyncio.create_task(self.fetch_and_update(token_data))
            lines.append("\n[i]Fetching metadata...[/i]")

        lines.append("\n[b]--- All Data ---[/b]")
        for k, v in token_data.items():
            if k not in priority_keys and k != "metadata" and k != "metadata_fetching":
                lines.append(f"[b]{k}:[/b] {v}")
                
        content = "\n".join(lines)
        self.query_one("#detail_content", Static).update(content)

    async def fetch_and_update(self, token_data: Dict[str, Any]) -> None:
        """Async fetch metadata."""
        uri = token_data.get("uri")
        if uri:
            try:
                metadata = await fetch_token_metadata(uri)
                with open("debug_stream.log", "a") as f:
                    f.write(f"Fetched metadata for {uri[:20]}...: {str(metadata)[:100]}\n")
            except Exception as e:
                with open("debug_stream.log", "a") as f:
                    f.write(f"Error fetching metadata {uri}: {e}\n")
                metadata = None
                
            if metadata:
                token_data["metadata"] = metadata
            else:
                token_data["metadata"] = {"error": "Failed to fetch"}
            
            # Remove fetching flag
            if "metadata_fetching" in token_data:
                del token_data["metadata_fetching"]
            
            # Refresh view if this is still the current token
            if self.current_token and self.current_token.get("mint") == token_data.get("mint"):
                self.update_token(token_data)
