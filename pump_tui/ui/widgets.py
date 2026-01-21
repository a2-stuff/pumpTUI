from textual.widgets import DataTable, Button, Label, Input, Pretty, Static
from textual.containers import Horizontal, Vertical
from textual.app import ComposeResult
from textual.widget import Widget
from rich.text import Text
from rich.markup import escape
from typing import Callable, Awaitable, List, Dict, Any, Optional
import asyncio

class TokenTable(Widget):
    """A widget to display a list of tokens with search."""

    def __init__(self, fetch_method: Callable[[], Awaitable[List[Dict[str, Any]]]] = None, title: str = "Tokens", id: str = None):
        super().__init__(id=id)
        self.fetch_method = fetch_method
        self.table_title = title
        self.table = DataTable(id="tokens_data_table")
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
                # Store cursor and scroll position
                coord = self.table.cursor_coordinate
                scroll_x, scroll_y = self.table.scroll_offset
                
                self.render_page()
                
                # Restore cursor (shifted by 1 if we added a row above)
                if coord.row >= 0:
                    try:
                        new_row = coord.row + 1
                        # Wait a bit or use call_later to ensure table has processed rows
                        self.table.call_later(self._restore_table_state, new_row, coord.column, scroll_x, scroll_y)
                    except:
                        pass

    def _restore_table_state(self, row, col, scroll_x, scroll_y):
        """Helper to restore table state after re-render."""
        try:
            if row < self.table.row_count:
                self.table.cursor_coordinate = (row, col)
            self.table.scroll_to(scroll_x, scroll_y, animate=False)
        except:
            pass

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
            
    # Selection is handled by the App to coordinate between table and detail view.


from textual.widgets import Static


from .image_utils import fetch_token_metadata
from .image_renderer import render_image_to_ansi

class TokenDetail(Static):
    """Widget to display details of a selected token."""
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.current_token = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="detail_layout"):
             yield Vertical(
                 Static("Select a token to view expanded details.", id="detail_content"),
                 id="detail_text_container"
             )
             yield Static("", id="detail_image", classes="image-container")

    def update_token(self, token_data: Dict[str, Any]) -> None:
        """Update the detail view with new token data."""
        self.current_token = token_data
        
        # Use Text object for safe rendering (no markup issues)
        content = Text()
        content.append("Token Details\n", style="bold underline")
        
        priority_keys = ["name", "symbol", "mint", "marketCapSol", "created_timestamp", "uri"]
        
        for key in priority_keys:
            if key in token_data:
                val = token_data[key]
                content.append(f"{key}: ", style="bold")
                content.append(f"{val}\n")
        
        content.append("\n") # Spacer
        
        # Extended Metrics
        tx_count = token_data.get("tx_count", 1)
        content.append("Tx Count: ", style="bold")
        content.append(f"{tx_count}\n")
        
        vol = token_data.get("volume_sol", 0.0)
        content.append("Volume: ", style="bold")
        content.append(f"{vol:.4f} SOL\n")
        
        dev_sold = token_data.get("dev_sold", False)
        content.append("Dev Sold: ", style="bold")
        if dev_sold:
            content.append("YES (SOLD)\n", style="red")
        else:
            content.append("NO (HOLDING)\n", style="green")

        # Metadata / Image
        if "metadata" in token_data:
            meta = token_data["metadata"]
            content.append("\nMetadata (Live)\n", style="bold underline")
            
            # Update Image Widget separately
            image_widget = self.query_one("#detail_image", Static)
            if "ansi_image" in token_data:
                image_widget.update(Text.from_ansi(token_data["ansi_image"]))
                image_widget.display = True
            elif "image" in meta:
                 content.append("Image: ", style="bold")
                 content.append("View Original Image\n", style="link " + meta['image'] if isinstance(meta['image'], str) else "")
                 image_widget.display = False
            else:
                 image_widget.display = False
            
            if "description" in meta:
                desc = meta["description"]
                if desc:
                    if len(desc) > 300:
                        desc = desc[:297] + "..."
                    content.append("Description: ", style="bold")
                    content.append(f"{desc}\n")
            
            # Socials & Others
            social_links_found = False
            known_socials = ["twitter", "telegram", "website", "discord", "github", "medium", "instagram"]
            
            # First collect all valid links
            all_links = []
            for s_key in known_socials:
                s_val = meta.get(s_key)
                if s_val and isinstance(s_val, str) and s_val.strip():
                    all_links.append((s_key.capitalize(), s_val))
            
            links_dict = meta.get("links")
            if isinstance(links_dict, dict):
                for l_key, l_val in links_dict.items():
                    if l_val and isinstance(l_val, str) and l_key not in known_socials:
                        all_links.append((l_key.capitalize(), l_val))

            if all_links:
                content.append("Links: ", style="bold")
                for i, (label, url) in enumerate(all_links):
                    content.append(label, style="link " + url)
                    if i < len(all_links) - 1:
                        content.append(" | ")
                content.append("\n")
            
            if "error" in meta:
                content.append(f"\nMetadata Fetch Error: {meta['error']}\n", style="red")
                 
        elif "uri" in token_data and "metadata_fetching" not in token_data:
            # Trigger fetch if URI exists and not already fetching/fetched
            token_data["metadata_fetching"] = True
            asyncio.create_task(self.fetch_and_update(token_data))
            content.append("\nFetching metadata...\n", style="italic")

        content.append("\n--- All Data ---\n", style="bold")
        for k, v in token_data.items():
            if k not in priority_keys and k not in ["metadata", "metadata_fetching", "ansi_image"]:
                content.append(f"{k}: ", style="bold")
                content.append(f"{v}\n")
                
        try:
            self.query_one("#detail_content", Static).update(content)
        except Exception as e:
            with open("debug_stream.log", "a") as f:
                 f.write(f"RENDER ERROR: {e}\n")
            self.query_one("#detail_content", Static).update("Rendering error. Check logs.")


    async def fetch_and_update(self, token_data: Dict[str, Any]) -> None:
        """Async fetch metadata."""
        uri = token_data.get("uri")
        mint = token_data.get("mint", "unknown")
        with open("debug_stream.log", "a") as f:
            f.write(f"Starting fetch_and_update for {mint} (URI: {uri})\n")
            
        if uri:
            try:
                metadata = await fetch_token_metadata(uri)
                with open("debug_stream.log", "a") as f:
                    f.write(f"Metadata received for {mint}: {str(metadata)[:100]}\n")

            except Exception as e:
                with open("debug_stream.log", "a") as f:
                    f.write(f"Error fetching metadata {uri}: {e}\n")
                metadata = None
                
            if metadata:
                token_data["metadata"] = metadata
                
                # Refresh UI immediately to show metadata while image is rendering
                if self.current_token and self.current_token.get("mint") == token_data.get("mint"):
                    self.call_later(self.update_token, token_data)

                # Now trigger image rendering if image URL exists
                image_url = metadata.get("image")
                if image_url:
                    try:
                        # Use 18 wide (approx 90-120px)
                        ansi = await render_image_to_ansi(image_url, width=18)
                        token_data["ansi_image"] = ansi
                    except Exception as e:
                        with open("debug_stream.log", "a") as f:
                            f.write(f"Image Render Error for {image_url}: {e}\n")

                # Final refresh with image
                if self.current_token and self.current_token.get("mint") == token_data.get("mint"):
                    self.call_later(self.update_token, token_data)
            else:
                token_data["metadata"] = {"error": "Failed to fetch"}
                if self.current_token and self.current_token.get("mint") == token_data.get("mint"):
                    self.call_later(self.update_token, token_data)
            
            # Remove fetching flag
            if "metadata_fetching" in token_data:
                del token_data["metadata_fetching"]


