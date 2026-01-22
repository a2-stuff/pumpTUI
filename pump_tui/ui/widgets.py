from textual.widgets import DataTable, Button, Label, Input, Pretty, Static
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.app import ComposeResult
from textual.widget import Widget
from rich.text import Text
from rich.markup import escape
from typing import Callable, Awaitable, List, Dict, Any, Optional
import asyncio
import time
from datetime import datetime
from ..config import config

class TokenTable(Widget):
    """A widget to display a list of tokens with search."""

    def __init__(self, fetch_method: Callable[[], Awaitable[List[Dict[str, Any]]]] = None, title: str = "Tokens", id: str = None):
        super().__init__(id=id)
        from ..database import db
        self.db = db # Store ref for easy access
        self.fetch_method = fetch_method
        self.table_title = title
        self.table = DataTable(id="tokens_data_table")
        self.data_store: Dict[str, Dict[str, Any]] = {} # Store full token data
        self.column_keys = {} # Store ColumnKey objects
        self._last_age_values: Dict[str, str] = {} # Performance: Cache age strings
        self._render_throttle = 0.5 # Minimum s between full renders
        self._last_full_render = 0.0
        self._tabbed_content = None # Cache for efficiency
        
        # Pagination & Search
        self.history: List[Dict[str, Any]] = []
        self.filtered_history: List[Dict[str, Any]] = []
        self.current_filter = ""
        self.current_page = 1
        self.page_size = 35
        self.max_history = 1000
        self._last_render_time = 0.0
        self._last_click_time = 0.0
        self._last_clicked_row = None
        self._pending_updates = False

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search by Name, Ticker, or Mint...", id="search_input")
        yield self.table
        with Horizontal(classes="pagination-controls"):
            yield Button("< Newer", id="btn_newer", disabled=True)
            yield Label(f"Page {self.current_page}", id="page_label")
            yield Button("Older >", id="btn_older")

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        self.table_title = "New Tokens (Live)"
        self.table.border_title = self.table_title
        cols = self.table.add_columns("Token CA", "Name", "Ticker", "MC ($)", "Tx", "Hold", "Buys", "Sells", "Vol ($)", "Dev", "Age")
        # Store MC column key specifically
        if len(cols) >= 4:
            self.column_keys["MC ($)"] = cols[3]
        if len(cols) >= 5:
            self.column_keys["Tx"] = cols[4]
        if len(cols) >= 6:
            self.column_keys["Hold"] = cols[5]
        if len(cols) >= 7:
            self.column_keys["Buys"] = cols[6]
        if len(cols) >= 8:
            self.column_keys["Sells"] = cols[7]
        if len(cols) >= 9:
            self.column_keys["Vol ($)"] = cols[8]
        if len(cols) >= 10:
            self.column_keys["Dev"] = cols[9]
        if len(cols) >= 11:
            self.column_keys["Age"] = cols[10]
        
        # Timers
        self.set_interval(1.0, self._update_ages)
        self.set_interval(0.5, self.on_timer)
        
        # Initial Load
        asyncio.create_task(self.load_data())

    async def load_data(self) -> None:
        # Wait for DB connection if needed (Startup Race)
        for _ in range(5):
             if self.db and self.db.connected:
                 break
             await asyncio.sleep(1.0)

        # Load recent tokens from DB as history
        if self.db and self.db.connected:
             try:
                 items = await self.db.get_recent_tokens(limit=100)
                 for item in reversed(items): # Insert oldest first so newest ends up at top of list
                     self.add_new_token(item)
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
        mint = event.get("mint")
        if not mint:
            return

        tx_type = event.get("txType")
        
        # If we already know this token, update its stats
        if mint in self.data_store:
             self.update_token_trade(event)
        # For new tokens, add if it's a creation OR if it's an active trade/matured token
        elif tx_type in [None, "create", "buy", "sell"] or event.get("pool") == "bonk":
             self.add_new_token(event)
             # Important: Also process the trade data in this first event
             self.update_token_trade(event)
        else:
             # Unknown type for unknown token - skip
             pass

    def _update_ages(self) -> None:
        """Update the Age column for visible rows."""
        if not self.table.is_mounted:
            return
            
        source_list = self.filtered_history
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_items = source_list[start_idx:end_idx]
        
        age_col = self.column_keys.get("Age")
        if not age_col:
            return

        now_ts = time.time()
        
        for item in page_items:
            mint = item.get("mint")
            if not mint: continue
            
            created_ts = item.get("timestamp")
            
            age_str = "0s"
            if created_ts and isinstance(created_ts, (int, float)):
                diff = int(now_ts - created_ts)
                if diff < 60: age_str = f"{diff}s"
                elif diff < 3600: age_str = f"{diff // 60}m {diff % 60}s"
                else: age_str = f"{diff // 3600}h {(diff % 3600) // 60}m"
            
            # Optimization: Only update if the string actually changed
            if self._last_age_values.get(mint) != age_str:
                try:
                    self.table.update_cell(mint, age_col, age_str)
                    self._last_age_values[mint] = age_str
                except:
                    pass
        

    def _request_render(self) -> None:
        """Throttle full renders to preserve CPU."""
        if not self.table.is_mounted:
            return
            
        try:
            # Only render if we are on the active tab
            if not self._tabbed_content:
                self._tabbed_content = self.app.query_one("TabbedContent")
            
            if self._tabbed_content.active != "new":
                self._pending_updates = True
                return
        except:
             self._pending_updates = True
             return

        now = time.time()
        if now - self._last_full_render > self._render_throttle:
             self._last_full_render = now
             self._pending_updates = False
             
             # Auto-Sort if active
             if getattr(self, "limit_sorting", False):
                 sort_field = getattr(self, "last_sort_field", None)
                 reverse = getattr(self, "last_sort_reverse", True)
                 if sort_field:
                     def key_func(x):
                         val = x.get(sort_field, 0)
                         try:
                             return float(val) if val is not None else 0.0
                         except ValueError:
                             return 0.0
                     self.filtered_history.sort(key=key_func, reverse=reverse)
             
             self.render_page()
        else:
             self._pending_updates = True
    
    def on_timer(self) -> None:
        """Called by the background interval."""
        if self._pending_updates:
             self._request_render()

    def get_selected_token(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected/highlighted token's data."""
        try:
            if not self.table.is_mounted or self.table.cursor_row < 0:
                return None
            
            # Use DataTable's internal key tracking to ensure we get the visual row's actual token
            # bypassing any index sync issues with filtered_history
            row_key = self.table.coordinate_to_cell_key(self.table.cursor_coordinate).row_key
            mint = row_key.value
            
            if mint and mint in self.data_store:
                return self.data_store[mint]
            return None
        except Exception:
            return None

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
            
            # Coloring logic
            mc_thresh = config.thresholds["mc"]
            if new_mc > mc_thresh["yellow"]:
                mc_style = "green"
            elif new_mc >= mc_thresh["red"]:
                mc_style = "yellow"
            else:
                mc_style = "red"
            
            # Update Table if visible (mint is the row key)
            try:
                col_key = self.column_keys.get("MC ($)")
                if col_key:
                    sol_price = getattr(self.app, "sol_price", 0.0)
                    if sol_price > 0:
                        mc_val_usd = new_mc * sol_price
                        mc_str = f"[{mc_style}]${mc_val_usd:,.0f}[/]"
                    else:
                        mc_str = f"[{mc_style}]{new_mc:.2f} S[/]"
                        
                    self.table.update_cell(mint, col_key, Text.from_markup(mc_str))
                
                # Update Tx and Holders
                tx_col = self.column_keys.get("Tx")
                holders_col = self.column_keys.get("Hold")
                
                tx_count = stored_item.get("tx_count", 0)
                tx_thresh = config.thresholds["tx"]
                if tx_count > tx_thresh["yellow"]:
                    tx_style = "green"
                elif tx_count >= tx_thresh["red"]:
                    tx_style = "yellow"
                else:
                    tx_style = "red"
                
                traders_count = len(stored_item.get("traders", set()))
                h_thresh = config.thresholds["holders"]
                if traders_count > h_thresh["yellow"]:
                    h_style = "green"
                elif traders_count >= h_thresh["red"]:
                    h_style = "yellow"
                else:
                    h_style = "red"

                if tx_col:
                     self.table.update_cell(mint, tx_col, Text.from_markup(f"[{tx_style}]{tx_count}[/]"))
                if holders_col:
                     self.table.update_cell(mint, holders_col, Text.from_markup(f"[{h_style}]{traders_count}[/]"))
            except Exception:
                pass
        
        # Trigger re-sort if we are sorting and something changed
        if getattr(self, "limit_sorting", False):
            self._pending_updates = True

        # --- Aggregation Logic ---
        # Track Traders
        if "traderPublicKey" in trade:
            if "traders" not in stored_item:
                 stored_item["traders"] = set()
            stored_item["traders"].add(trade["traderPublicKey"])

        # Increment Tx Count
        stored_item["tx_count"] = stored_item.get("tx_count", 0) + 1
        
        # Track Buys/Sells
        tx_type = trade.get("txType")
        
        # Infer txType if missing
        if not tx_type:
            sol_amt_raw = float(trade.get("solAmount") or 0)
            if sol_amt_raw > 0:
                tx_type = "buy"
            elif float(trade.get("tokenAmount") or 0) > 0:
                tx_type = "sell"

        if tx_type == "buy":
             stored_item["buys_count"] = stored_item.get("buys_count", 0) + 1
        elif tx_type == "sell":
             stored_item["sells_count"] = stored_item.get("sells_count", 0) + 1

        # Update Volume
        sol_amt = float(trade.get("solAmount") or 0)
        
        # Estimation for bonk pool if solAmount is missing
        if sol_amt == 0 and trade.get("pool") == "bonk" and "marketCapSol" in trade and "tokenAmount" in trade:
             try:
                 token_amt = float(trade.get("tokenAmount") or 0)
                 mc_sol = float(trade.get("marketCapSol") or 0)
                 # Estimation: Price = MC / TotalSupply (1B)
                 price_sol = mc_sol / 1_000_000_000
                 sol_amt = token_amt * price_sol
             except:
                 pass

        new_vol = stored_item.get("volume_sol", 0.0) + sol_amt
        stored_item["volume_sol"] = new_vol
        
        # Update Volume Cell
        try:
            vol_col = self.column_keys.get("Vol ($)")
            if vol_col:
                sol_price = getattr(self.app, "sol_price", 0.0)
                if sol_price > 0:
                     new_vol_usd = new_vol * sol_price
                     v_thresh = config.thresholds["vol"]
                     if new_vol_usd > v_thresh["yellow"]:
                         v_style = "green"
                     elif new_vol_usd >= v_thresh["red"]:
                         v_style = "yellow"
                     else:
                         v_style = "red"
                     self.table.update_cell(mint, vol_col, Text.from_markup(f"[{v_style}]${new_vol_usd:,.0f}[/]"))
                else:
                     self.table.update_cell(mint, vol_col, f"{new_vol:.2f} S")
        except:
            pass
        
        # Update Buys/Sells Cell (separate try/except for independence)
        try:
            buy_col = self.column_keys.get("Buys")
            sell_col = self.column_keys.get("Sells")
            if buy_col:
                 self.table.update_cell(mint, buy_col, Text.from_markup(f"[green]{stored_item.get('buys_count', 0)}[/]"))
            if sell_col:
                 self.table.update_cell(mint, sell_col, Text.from_markup(f"[red]{stored_item.get('sells_count', 0)}[/]"))
        except:
            pass
        
        # Check Dev Sold
        creator = stored_item.get("creator")
        trader = trade.get("traderPublicKey")
        tx_type = trade.get("txType")
        
        if creator and trader and creator == trader and tx_type == "sell":
            stored_item["dev_sold"] = True
            
            # Update Table Cell for Dev Sold
            dev_col = self.column_keys.get("Dev")
            if dev_col:
                try:
                    self.table.update_cell(mint, dev_col, Text.from_markup("[green]SOLD[/]"))
                except:
                    pass
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
        if "timestamp" not in item:
             item["timestamp"] = time.time()
        
        item["tx_count"] = 0
        item["buys_count"] = 0
        item["sells_count"] = 0
        item["volume_sol"] = 0.0
        item["dev_sold"] = False
        item["creator"] = item.get("traderPublicKey", None)
        item["traders"] = set()
        if item["creator"]:
            item["traders"].add(item["creator"])
        
        self.data_store[mint] = item

        
        # Add to history
        self.history.insert(0, item)
        if len(self.history) > self.max_history:
            removed = self.history.pop()
            # Also remove from data_store to prevent memory leak and allow re-discovery
            removed_mint = removed.get("mint")
            if removed_mint and removed_mint in self.data_store:
                del self.data_store[removed_mint]
        
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
            
            should_render = False
            if self.current_page == 1 and self.table.is_mounted:
                try:
                    if not self._tabbed_content:
                        self._tabbed_content = self.app.query_one("TabbedContent")
                    if self._tabbed_content.active == "new":
                        should_render = True
                except: pass

            if should_render:
                # Flag for update instead of manual row manipulation
                # This ensures consistent ordering via render_page
                self._pending_updates = True
                
                # Maintain cursor? render_page handles state restoration if we pass logic?
                # Actually _request_render stores state.
                pass


                
                # Maintain page size limit
                if self.table.row_count > self.page_size:
                    # Remove the last row to stay within page boundary
                    # We need the key of the last row
                    last_idx = self.table.row_count - 1
                    try:
                        # row_at returns the row object/data? No, table.rows is a dict?
                        # Coordinate to row key
                        last_row_key = self.table.coordinate_to_cell_key((last_idx, 0)).row_key
                        self.table.remove_row(last_row_key)
                    except: pass
                
                # Update labels without full re-render
                self.query_one("#page_label", Label).update(f"Page {self.current_page} (Total: {len(self.filtered_history)})")
            else:
                self._pending_updates = True

    def _restore_table_state(self, row, col, scroll_x, scroll_y):
        """Helper to restore table state after re-render."""
        try:
            if row < self.table.row_count:
                self.table.cursor_coordinate = (row, col)
            self.table.scroll_to(scroll_x, scroll_y, animate=False)
        except:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update app bindings when cursor moves to show/hide contextual keys."""
        # Performance: Throttle footer updates during rapid navigation
        now = time.time()
        if not hasattr(self, "_last_binding_refresh"):
            self._last_binding_refresh = 0
            
        if now - self._last_binding_refresh > 0.1:
            self._last_binding_refresh = now
            try:
                self.app.refresh_bindings()
            except:
                pass
            
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle double-click to open trade modal."""
        now = time.time()
        row_key = event.row_key.value
        
        if self._last_clicked_row == row_key and now - self._last_click_time < 0.4:
            # Double click detected
            self.app.action_trade_token()
            self._last_clicked_row = None # Reset
        else:
            self._last_click_time = now
            self._last_clicked_row = row_key

    def render_page(self):
        """Render the current page from filtered history with cursor stability."""
        if not self.table.is_mounted: return

        # 1. Save state
        saved_key = None
        saved_row_idx = None
        try:
            if self.table.cursor_row >= 0:
                 saved_key = self.table.get_cursor_row_key()
                 saved_row_idx = self.table.cursor_row
        except: pass
        scroll_x, scroll_y = self.table.scroll_offset

        self.table.clear()
        self._last_age_values.clear() # Reset cache on full re-render
        
        source_list = self.filtered_history
        
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_items = source_list[start_idx:end_idx]
        
        for item in page_items:
            row_data = self._format_row_data(item)
            mint = item.get("mint", "N/A")
            self.table.add_row(*row_data, key=mint)
        
        # 3. Restore state (Robust)
        if saved_key:
            try:
                # Try to find the exact token again
                new_idx = self.table.get_row_index(saved_key)
                self.table.move_cursor(row=new_idx, animate=False)
            except:
                # Fallback: maintain visual row position if token moved off page
                if saved_row_idx is not None:
                     target_row = min(saved_row_idx, self.table.row_count - 1)
                     self.table.move_cursor(row=target_row, animate=False)
        elif saved_row_idx is not None and self.table.row_count > 0:
             # If no key was saved but we had a row (unlikely for DataTable but safe)
             target_row = min(saved_row_idx, self.table.row_count - 1)
             self.table.move_cursor(row=target_row, animate=False)

        self.table.scroll_to(x=scroll_x, y=scroll_y, animate=False)

        # Update controls
        self.query_one("#page_label", Label).update(f"Page {self.current_page} (Total: {len(source_list)})")
        self.query_one("#btn_newer", Button).disabled = (self.current_page <= 1)
        self.query_one("#btn_older", Button).disabled = (end_idx >= len(source_list))

    def _format_row_data(self, item: Dict[str, Any]) -> List[Any]:
        """Format token data for a DataTable row."""
        mint = item.get("mint", "N/A")
        name = item.get("name", "N/A")
        if len(name) > 22:
            name = rf"{name[:5]}...{name[-5:]}"
        
        raw_symbol = item.get("symbol", "N/A")
        symbol = f"${raw_symbol}" if raw_symbol != "N/A" else "N/A"
        
        mc_val = item.get('marketCapSol', 0)
        mc_thresh = config.thresholds["mc"]
        mc_style = "green" if mc_val > mc_thresh["yellow"] else "yellow" if mc_val >= mc_thresh["red"] else "red"
        
        sol_price = getattr(self.app, "sol_price", 0.0)
        if sol_price > 0:
            mc_val_usd = mc_val * sol_price
            market_cap = f"[{mc_style}]${mc_val_usd:,.0f}[/]"
        else:
            market_cap = f"[{mc_style}]{mc_val:.2f} S[/]"
            
        display_mint = f"{mint[:4]}...{mint[-4:]}" if len(mint) > 10 else mint
        
        tx_val = item.get("tx_count", 0)
        tx_thresh = config.thresholds["tx"]
        tx_style = "green" if tx_val > tx_thresh["yellow"] else "yellow" if tx_val >= tx_thresh["red"] else "red"
        tx_count = f"[{tx_style}]{tx_val}[/]"
        
        h_val = len(item.get("traders", set()))
        h_thresh = config.thresholds["holders"]
        h_style = "green" if h_val > h_thresh["yellow"] else "yellow" if h_val >= h_thresh["red"] else "red"
        holders = f"[{h_style}]{h_val}[/]"
        
        buys_str = f"[green]{item.get('buys_count', 0)}[/]"
        sells_str = f"[red]{item.get('sells_count', 0)}[/]"
        
        # Age
        ts = item.get("timestamp")
        age_str = "0s"
        if ts and isinstance(ts, (int, float)):
            diff = int(time.time() - ts)
            if diff < 60: age_str = f"{diff}s"
            elif diff < 3600: age_str = f"{diff // 60}m {diff % 60}s"
            else: age_str = f"{diff // 3600}h {(diff % 3600) // 60}m"
        
        # Volume
        vol_val = item.get("volume_sol", 0.0)
        if sol_price > 0:
            vol_val_usd = vol_val * sol_price
            v_thresh = config.thresholds["vol"]
            v_style = "green" if vol_val_usd > v_thresh["yellow"] else "yellow" if vol_val_usd >= v_thresh["red"] else "red"
            vol_str = f"[{v_style}]${vol_val_usd:,.0f}[/]"
        else:
            vol_str = f"{vol_val:.2f} S"
            
        dev_str = "[green]SOLD[/]" if item.get("dev_sold", False) else "[red]HOLDING[/]"
        
        return [
            display_mint, 
            name, 
            symbol, 
            Text.from_markup(market_cap), 
            Text.from_markup(tx_count), 
            Text.from_markup(holders), 
            Text.from_markup(buys_str), 
            Text.from_markup(sells_str), 
            Text.from_markup(vol_str), 
            Text.from_markup(dev_str),
            age_str
        ]

    def sort_data(self, sort_field: str, reverse: bool = True):
        """Sort the underlying data and re-render."""
        try:
             self.limit_sorting = True
             
             def key_func(x):
                 val = x.get(sort_field, 0)
                 if val is None: return 0
                 return float(val)

             self.filtered_history.sort(key=key_func, reverse=reverse)
             
             # Re-render
             self.current_page = 1
             self.render_page()
             
             title_map = {"marketCapSol": "MC", "volume_sol": "Volume", "timestamp": "Live"}
             self.table_title = f"New Tokens ({title_map.get(sort_field, sort_field)} ↓)"
             try:
                 self.table.border_title = self.table_title
             except: pass

        except Exception as e:
            with open("error.log", "a") as f:
                f.write(f"Sort Error: {e}\n")

    def sort_data(self, sort_field: str, reverse: bool = True):
        """Sort the underlying data and re-render."""
        try:
             self.limit_sorting = True
             self.last_sort_field = sort_field # Store for auto-sort
             self.last_sort_reverse = reverse
             
             def key_func(x):
                 val = x.get(sort_field, 0)
                 try:
                     return float(val) if val is not None else 0.0
                 except ValueError:
                     return 0.0

             self.filtered_history.sort(key=key_func, reverse=reverse)
             
             # Re-render
             self.current_page = 1
             self.render_page()
             
             title_map = {"marketCapSol": "MC", "volume_sol": "Volume", "timestamp": "Live"}
             self.table_title = f"New Tokens ({title_map.get(sort_field, sort_field)} ↓)"
             try:
                 self.table.border_title = self.table_title
             except: pass

        except Exception as e:
            with open("error.log", "a") as f:
                f.write(f"Sort Error: {e}\n")

    def reset_sort_live(self):
        """Reset to Live/Age sort (Newest First)."""
        self.limit_sorting = False
        # Sort by timestamp descending
        self.filtered_history.sort(key=lambda x: x.get("timestamp", 0) or 0, reverse=True)
        self.current_page = 1
        self.render_page()
        self.table_title = "New Tokens (Live)"
        try:
            self.table.border_title = self.table_title
        except: pass
        
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
         # Initial load handled in on_mount via DB check usually
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
                
                if key == "marketCapSol" and isinstance(val, (int, float)):
                    if val > 40:
                        mc_style = "green"
                    elif val >= 30:
                        mc_style = "yellow"
                    else:
                        mc_style = "red"
                    content.append(f"{val}\n", style=mc_style)
                else:
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



class VolumeTable(TokenTable):
    """
    A table that polls MongoDB for top volume tokens (Last 24h).
    Inherits from TokenTable to reuse formatting and selection logic.
    """
    
    def __init__(self, id: str = None):
        super().__init__(fetch_method=None, title="Top Volume (24h)", id=id)
        self.polling_interval = 2.0
        # Override columns: Swap 'Age' for 'Vol 24h'
        self.column_keys = {} # Reset to clear parent setup, will be rebuilt in on_mount

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        
        # Define Columns (Slightly different from TokenTable)
        cols = self.table.add_columns(
            "Token CA", "Name", "Ticker", 
            "MC ($)", "Tx", "Hold", 
            "Buys", "Sells", "Vol (24h)", # Changed label
            "Dev", "Last Upd" # Changed Age -> Last Updated
        )
        
        # Map keys for reuse of formatting logic where applicable
        if len(cols) >= 4: self.column_keys["MC ($)"] = cols[3]
        if len(cols) >= 5: self.column_keys["Tx"] = cols[4]
        if len(cols) >= 6: self.column_keys["Hold"] = cols[5]
        if len(cols) >= 7: self.column_keys["Buys"] = cols[6]
        if len(cols) >= 8: self.column_keys["Sells"] = cols[7]
        if len(cols) >= 9: self.column_keys["Vol ($)"] = cols[8] # Maps to Vol 24h column
        if len(cols) >= 10: self.column_keys["Dev"] = cols[9]
        if len(cols) >= 11: self.column_keys["Age"] = cols[10] # Maps to Last Upd
        
        self.set_interval(self.polling_interval, self.refresh_data)
        asyncio.create_task(self.refresh_data())

    async def refresh_data(self) -> None:
        """Fetch sorted data from DB and update table."""
        # Only refresh if visible
        try:
            if not self.table.is_mounted: return
            # Check active tab to save resources
            if not self._tabbed_content:
                self._tabbed_content = self.app.query_one("TabbedContent")
            
            if self._tabbed_content.active != "trending":
                return
        except:
            pass

        try:
            from ..database import db
            tokens = await db.get_top_volume_tokens(limit=50)
            
            # Save state
            saved_key = None
            if self.table.cursor_row >= 0:
                 try:
                     saved_key = self.table.get_cursor_row_key()
                 except: pass
            
            self.table.clear()
            
            for token in tokens:
                # Normalize Volume Field for format_row_data
                token["volume_sol"] = token.get("volume_24h", 0)
                
                # Format
                row_data = self._format_row_data(token)
                
                # Insert
                mint = token.get("mint", "N/A")
                self.data_store[mint] = token # Sync local store for details view
                self.table.add_row(*row_data, key=mint)
            
            # Restore state
            if saved_key:
                try:
                    dest_row = self.table.get_row_index(saved_key)
                    self.table.move_cursor(row=dest_row, animate=False)
                except: pass
                
        except Exception as e:
            with open("error.log", "a") as f:
                f.write(f"Volume Table Error: {e}\n")

    def _format_row_data(self, item: Dict[str, Any]) -> List[Any]:
        # Reuse parent formatting but override Age logic since this is Last Updated
        row = super()._format_row_data(item)
        
        # Override last column (Age) with Last Updated Time
        last_upd = item.get("last_updated")
        if isinstance(last_upd, datetime):
            time_str = last_upd.strftime("%H:%M:%S")
            row[-1] = time_str
        
        return row

class RunnersTable(TokenTable):
    """
    A table that polls MongoDB for top volume tokens (Last 12h).
    Supports sorting by Volume and Market Cap.
    """
    
    def __init__(self, id: str = None):
        super().__init__(fetch_method=None, title="Runners (12h)", id=id)
        self.polling_interval = 2.0
        self.sort_by = "volume" # or "market_cap"
        self.sort_dir = -1 # Descending
        self.column_keys = {}

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        
        # Define Columns with specific IDs for click tracking
        # We need to use Text objects or string keys if API allows
        # Since Textual 0.70 DataTable doesn't have easy header click events, 
        # we will simulate it via an Action or ignore header clicks if not supported.
        # Actually latest Textual supports on_data_table_header_selected if headers are clicked.
        
        cols = self.table.add_columns(
            "Token CA", "Name", "Ticker", 
            "MC ($) [Sort]", # Hint sorting
            "Tx", "Hold", 
            "Buys", "Sells", "Vol (12h) [Sort]", 
            "Dev", "Last Upd"
        )
        
        # Map keys
        if len(cols) >= 4: self.column_keys["MC ($)"] = cols[3]
        if len(cols) >= 9: self.column_keys["Vol ($)"] = cols[8]
        
        self.set_interval(self.polling_interval, self.refresh_data)
        asyncio.create_task(self.refresh_data())

    async def toggle_sort(self, sort_key: str):
        """Toggle sort order."""
        if self.sort_by == sort_key:
            # Toggle direction: desc (-1) -> asc (1) -> desc (-1)
            self.sort_dir *= -1
        else:
            self.sort_by = sort_key
            self.sort_dir = -1 # Default desc
            
        # Update Title
        arrow = "↓" if self.sort_dir == -1 else "↑"
        label = "Vol" if self.sort_by == "volume" else "MC"
        self.table_title = f"Runners (12h) - {label} {arrow}"
        
        # Trigger immediate refresh
        await self.refresh_data()

    async def refresh_data(self) -> None:
        """Fetch sorted data from DB."""
        try:
            if not self.table.is_mounted: return
            if not self._tabbed_content:
                self._tabbed_content = self.app.query_one("TabbedContent")
            
            if self._tabbed_content.active != "trending":
                return
        except: pass

        try:
            if self.db and self.db.connected:
                tokens = await self.db.get_runners(limit=50, sort_by=self.sort_by, sort_dir=self.sort_dir)
                
                # Save state
                saved_key = None
                if self.table.cursor_row >= 0:
                     try:
                         saved_key = self.table.get_cursor_row_key()
                     except: pass
                
                self.table.clear()
                
                for token in tokens:
                    # Normalize Volume Logic for display
                    # If we sort by MC, volume might be missing if no trades in 12h but strictly it's a runner query
                    token["volume_sol"] = token.get("volume_12h", 0)
                    
                    row_data = self._format_row_data(token)
                    mint = token.get("mint", "N/A")
                    self.data_store[mint] = token
                    self.table.add_row(*row_data, key=mint)
                
                if saved_key:
                    try:
                        dest_row = self.table.get_row_index(saved_key)
                        self.table.move_cursor(row=dest_row, animate=False)
                    except: pass
        except Exception as e:
            with open("error.log", "a") as f:
                f.write(f"Runners Error: {e}\n")

    def _format_row_data(self, item: Dict[str, Any]) -> List[Any]:
        row = super()._format_row_data(item)
        last_upd = item.get("last_updated")
        if isinstance(last_upd, datetime):
            row[-1] = last_upd.strftime("%H:%M:%S")
        return row
    
    # Simple keybindings to toggle sort since mouse header click isn't standard in older Textual
    def key_m(self): # Sort by Market Cap
        asyncio.create_task(self.toggle_sort("market_cap"))
    
    def key_v(self): # Sort by Volume
        asyncio.create_task(self.toggle_sort("volume"))
