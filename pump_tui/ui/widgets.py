from textual.widgets import DataTable, Button, Label, Input, Pretty, Static
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.app import ComposeResult
from textual.widget import Widget
from rich.text import Text
from rich.markup import escape
from typing import Callable, Awaitable, List, Dict, Any, Optional
import asyncio
import math
import re
import time
import httpx
from datetime import datetime
from ..config import config
from ..trading import TradingClient
from .image_utils import fetch_token_metadata
try:
    from .image_renderer import render_image_to_ansi
except ImportError:
    async def render_image_to_ansi(*args, **kwargs): return ""
from .graph_widget import CandleChart

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
        
        # Selection State
        self.selected_mint = None

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
        cols = self.table.add_columns(" ", "Token CA", "Name", "Ticker", "MC ($)", "Tx", "Hold", "Buys", "Sells", "Vol ($)", "Dev", "Age")
        # Store MC column key specifically
        if len(cols) >= 5:
            self.column_keys["MC ($)"] = cols[4]
        if len(cols) >= 6:
            self.column_keys["Tx"] = cols[5]
        if len(cols) >= 7:
            self.column_keys["Hold"] = cols[6]
        if len(cols) >= 8:
            self.column_keys["Buys"] = cols[7]
        if len(cols) >= 9:
            self.column_keys["Sells"] = cols[8]
        if len(cols) >= 10:
            self.column_keys["Vol ($)"] = cols[9]
        if len(cols) >= 11:
            self.column_keys["Dev"] = cols[10]
        if len(cols) >= 12:
            self.column_keys["Age"] = cols[11]
        
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
    
    def select_token(self, mint: str) -> bool:
        """Toggle selection of a token. Returns True if now selected."""
        if self.selected_mint == mint:
             # Deselect? Or just keep selected? Let's keep selected as it's a radio behavior effectively for trading
             # But user said "checkbox", usually implied multi-select or toggle.
             # "selected token is what's going to be used". Singular.
             # If same, maybe do nothing.
             return True
        
        self.selected_mint = mint
        # Re-render to update checkboxes
        self.render_page()
        return True

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

        # Pause on full re-render if user is browsing history (cursor > 5)
        # But atomic updates in add_new_token will still occur.
        if self.table.cursor_row > 5:
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
        
        # Capture Initial Buy (from creation event)
        # Pump.fun 'create' event usually has 'solAmount' which is the initial buy.
        if item.get("txType") == "create":
             item["initial_buy"] = float(item.get("solAmount") or 0.0)
        else:
             item["initial_buy"] = 0.0

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
                # OPTIMIZATION: Atomic addition to keep cursor stable and fast
                # This prevents the "jumping" caused by full clear/re-render
                row_data = self._format_row_data(item)
                try:
                    self.table.add_row(*row_data, key=mint, before=0)
                    
                    # Maintain page size limit (important for vertical stability)
                    if self.table.row_count > self.page_size:
                        try:
                            # Use coordinate_to_cell_key to find the last row's key
                            last_row_idx = self.table.row_count - 1
                            last_row_key = self.table.coordinate_to_cell_key((last_row_idx, 0)).row_key
                            self.table.remove_row(last_row_key)
                        except:
                            pass
                    
                    # Update label
                    self.query_one("#page_label", Label).update(f"Page {self.current_page} (Total: {len(self.filtered_history)})")
                except:
                    # Fallback to full render if atomic update fails
                    self._pending_updates = True
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
            
        if now - self._last_binding_refresh > 0.2:
            self._last_binding_refresh = now
            try:
                self.app.refresh_bindings()
            except:
                pass
            
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle double-click to open trade modal. Enter (keyboard selection) is disabled."""
        now = time.time()
        row_key = event.row_key.value
        
        if self._last_clicked_row == row_key and now - self._last_click_time < 0.4:
            # Double click detected
            self.app.action_trade_token()
            self._last_clicked_row = None # Reset
        else:
            self._last_click_time = now
            self._last_clicked_row = row_key
            
            # Since Enter key triggers this, we used to select the token here.
            # To remove the Enter keybind, we do NOT call selection logic here anymore.
            # Selection must be done via specific click or other method if desired.
            pass

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
        
        # Checkbox
        sel_str = "[green]x[/]" if item.get("mint") == self.selected_mint else "[ ]"

        return [
            sel_str,
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


# ----------------------------------------------------------------------
# Trade Panel (Persistent Side Panel)
# ----------------------------------------------------------------------



class TradeInput(Input):
    """Input that triggers trade execution on 'e' key."""
    
    def _on_key(self, event) -> None:
        if event.key in ["e", "b", "s"]:
            # Find parent panel and execute (dynamic lookup to avoid scope issues)
            # Traverse up to find the container with the action
            node = self.parent
            while node:
                if node.id in ["trade_panel_container", "trade_dialog"] or isinstance(node, Container):
                    if event.key == "e" and hasattr(node, "action_execute_trade"):
                        node.action_execute_trade()
                        event.stop() 
                        return
                    elif event.key == "b":
                        if hasattr(node, "action_toggle_buy"):
                            node.action_toggle_buy()
                            event.stop()
                            return
                        elif hasattr(node, "set_mode"):
                            node.set_mode("buy")
                            event.stop()
                            return
                    elif event.key == "s":
                        if hasattr(node, "action_toggle_sell"):
                            node.action_toggle_sell()
                            event.stop()
                            return
                        elif hasattr(node, "set_mode"):
                            node.set_mode("sell")
                            event.stop()
                            return
                node = node.parent
        super()._on_key(event)

# ----------------------------------------------------------------------
# Trade Panel (Persistent Side Panel)
# ----------------------------------------------------------------------

class TradePanel(Container):
    """Persistent widget to trade the selected token."""

    BINDINGS = [
        Binding("b", "set_mode_buy", "Buy (b)", show=True),
        Binding("s", "set_mode_sell", "Sell (s)", show=True),
        Binding("e", "execute_trade", "Execute (e)", show=True),
    ]
    
    def set_mode(self, mode: str) -> None:
        """Switch between buy and sell modes."""
        self.trade_mode = mode
        inp = self.query_one("#amount_input", Input)
        
        if mode == "buy":
            self.query_one("#buy_button").add_class("-active")
            self.query_one("#sell_button").remove_class("-active")
            self.query_one("#denom_label").update("(SOL)")
            
            # Switch to Buy: Strip % and restrict to numbers
            curr_val = inp.value.replace("%", "").strip()
            inp.value = curr_val if curr_val else "1.0"
            inp.restrict = r"^[0-9.]*$"
            
        else:
            self.query_one("#sell_button").add_class("-active")
            self.query_one("#buy_button").remove_class("-active")
            self.query_one("#denom_label").update("(%)")
            
            # Switch to Sell: Default to 100%
            inp.value = "100%"
            # Allow numbers and %
            inp.restrict = r"^[0-9.%]*$"
            
        self.update_estimation()

    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.token_data = {}
        self.trade_mode = "buy"
        self.active_wallet = None
        self.trading_client = None
        self.is_processing = False
        self.data_provider = None # Will assign later or passed via update
        self.last_chart_mc = 0.0
        self.last_buys = -1
        self.last_sells = -1

    def compose(self) -> ComposeResult:
        with Container(id="trade_panel_container"):
            # Buy/Sell Toggle (Top)
            # One line spacing above handled by spacer
            yield Label("", classes="spacer")
            with Horizontal(classes="trade_buttons"):
                yield Button("Buy (b)", id="buy_button", classes="trade_button -active")
                yield Button("Sell (s)", id="sell_button", classes="trade_button")

            # Spacer after buttons
            yield Label("", classes="spacer")

            yield Label("Trade: None Selected", id="trade_title", classes="panel-header")
            
            # Spacer after Trade title
            yield Label("", classes="spacer")
            
            # Market Stats Box (MC | Vol | Dev)
            with Container(id="market_stats_box", classes="stats-grid"):
                with Horizontal():
                     yield Label("MC: -", id="mc_label", classes="count-label")
                     yield Label("Vol: -", id="vol_label", classes="count-label")
                     yield Label("Dev: -", id="dev_label", classes="count-label")

            # Trading Stats Box (Tx | Hold | Buys | Sells)
            with Container(id="trading_stats_box", classes="stats-grid"):
                with Horizontal():
                     yield Label("Tx: -", id="tx_label", classes="count-label")
                     yield Label("Hold: -", id="holders_label", classes="count-label")
                     yield Label("Buys: -", id="buys_label", classes="count-label green")
                     yield Label("Sells: -", id="sells_label", classes="count-label red")

            # Creator Stats Box (Creator | Tokens | Migrated | Int. Buy)
            with Container(classes="stats-grid"):
                with Horizontal():
                     yield Label("Creator: -", id="creator_label", classes="count-label")
                     yield Label("Tokens: -", id="launched_count_label", classes="count-label")
                     yield Label("Migrated: -", id="migrated_count_label", classes="count-label")
                     yield Label("Buy: -", id="initial_label", classes="count-label")

            # Price Chart Box
            with Container(classes="stats-grid", id="chart_box"):
                yield Label("Price (Live):", classes="info-box-header")
                yield CandleChart(id="price_chart")

            # Contract, Description, & Socials Box
            with Container(classes="stats-grid"):
                # Name and Contract with Blue Label
                yield Label("[b][#89b4fa]Token Name:[/][/] -", id="name_label", classes="panel-info")
                yield Label("[b][#89b4fa]Contract:[/][/] -", id="ca_label", classes="panel-info")
                
                # Spacer after Token Name/Contract bar
                yield Label("", classes="spacer")
                
                yield Label("Description:", classes="info-box-header")
                yield Label("-", id="desc_label", classes="info-box-text")
                
                # Spacer above links
                yield Label("", classes="spacer")
                
                yield Label("Links:", classes="info-box-header")
                # Stack links vertically
                with Vertical(classes="social-links"):
                    yield Label("-", id="website_label", classes="link-item")
                    yield Label("-", id="twitter_label", classes="link-item")
                    yield Label("-", id="telegram_label", classes="link-item")
            
            # Wallet Info & Input Box (Amount | Input | Denom | Est)
            with Container(id="amount_stats_box", classes="stats-grid"):
                with Vertical():
                    with Horizontal(classes="input-row-inner"):
                        yield Label("[b][#89b4fa]Amount:[/][/]", classes="input_label")
                        yield TradeInput(value="1.0", id="amount_input", classes="input_field", restrict=r"^[0-9.%]*$")
                        yield Label("(SOL)", id="denom_label", classes="mini-label")
                    # Est Tokens below amount input
                    yield Label("Est. Tokens: -", id="estimated_amount", classes="mini-label")
            
            # Action Button (Centered)
            with Horizontal(classes="button-row"):
                yield Button("Execute (e)", variant="success", id="execute_button", classes="action_button")
            
            # Feedback (Overlay/Bottom)
            yield Label("", id="error_label")
            yield Label("", id="success_label")

    def on_mount(self) -> None:
        # self.update_mc_ticker = self.set_interval(1.0, self.update_market_stats)
        self.run_worker(self.load_active_wallet())
    
    async def load_active_wallet(self):
        """Load active wallet info with retry if DB is still connecting."""
        try:
            from ..database import db
            
            # 1. Wait for DB connection
            retries = 0
            while not db.connected and retries < 15:
                await asyncio.sleep(1.0)
                retries += 1
            
            if not db.connected:
                 try: self.query_one("#active_wallet_info", Label).update("Active: [red]DB Error[/]")
                 except: pass
                 return

            # 2. Try to load from local state if app already has it
            if hasattr(self.app, "active_wallet") and self.app.active_wallet:
                self.active_wallet = self.app.active_wallet
            else:
                # 3. Otherwise fetch from DB
                active_doc = await db.settings.find_one({"key": "active_wallet"})
                if active_doc and "value" in active_doc:
                    pub_key = active_doc["value"]
                    wallets = await db.get_wallets()
                    self.active_wallet = next((w for w in wallets if w["walletPublicKey"] == pub_key), None)
            
            await self.update_wallet_ui()
            
            # Start periodic internal sync (just to be safe)
            if not hasattr(self, "_wallet_sync_timer"):
                self._wallet_sync_timer = self.set_interval(30.0, self.update_wallet_ui)
            
        except Exception as e:
            try:
                try: self.query_one("#active_wallet_info", Label).update("Active: [red]Error[/]")
                except: pass
                with open("error.log", "a") as f: f.write(f"Panel Wallet Load Error: {e}\n")
            except: pass

    async def update_wallet_ui(self):
        """Update the UI labels for the active wallet."""
        try:
            if not self.is_mounted: return
            
            # Active wallet info and balance are now primarily in the System Header.
            # We keep these queries safe in case they are restored or used elsewhere.
            if self.active_wallet:
                pub = self.active_wallet.get("walletPublicKey")
                
                # Pre-initialize/Worm-up the trading client for faster execution
                if not self.trading_client or getattr(self.trading_client, "_pub_key", "") != pub:
                    try:
                        self.trading_client = TradingClient(
                            rpc_url=config.rpc_url,
                            wallet_private_key=self.active_wallet.get("privateKey"),
                            api_key=getattr(config, "api_key", None) if hasattr(config, "api_key") else ""
                        )
                        self.trading_client._pub_key = pub
                    except: pass

                display = f"{pub[:6]}...{pub[-6:]}"
                try: self.query_one("#active_wallet_info", Label).update(Text.from_markup(f"Active: [#f9e2af]{display}[/]"))
                except: pass
                # Trigger balance fetch
                await self.fetch_wallet_balance()
            else:
                try: self.query_one("#active_wallet_info", Label).update(Text.from_markup("Active: [red]None[/]"))
                except: pass
                try: self.query_one("#wallet_balance", Label).update("Balance: -")
                except: pass
        except: pass

    async def fetch_wallet_balance(self) -> None:
        """Fetch balance for the active wallet, prioritizing app cache."""
        try:
            if not self.active_wallet: return
            pub_key = self.active_wallet.get("walletPublicKey")
            
            # Optimization: Use App's already-cached balance if it matches the current wallet
            if hasattr(self.app, "active_wallet_pub") and self.app.active_wallet_pub == pub_key:
                if hasattr(self.app, "wallet_balance_str") and self.app.wallet_balance_str:
                    bal_text = self.app.wallet_balance_str
                    try: self.query_one("#wallet_balance", Label).update(f"Bal: {bal_text}")
                    except: pass
                    return

            # Fallback: Live RPC Fetch
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub_key]}
            async with httpx.AsyncClient(timeout=2.0) as http_client:
                response = await http_client.post(config.rpc_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    val = data.get("result", {}).get("value")
                    if val is not None:
                         bal_sol = val / 1_000_000_000
                         try: self.query_one("#wallet_balance", Label).update(f"Bal: {bal_sol:.4f} SOL")
                         except: pass
        except: pass

    def update_token(self, token_data: Dict[str, Any]):
        """Update the panel with new token data."""
        new_mint = token_data.get("mint")
        old_mint = self.token_data.get("mint")
        
        self.token_data = token_data
        
        name = token_data.get("name", "Unknown")
        symbol = token_data.get("symbol", "???")
        self.query_one("#trade_title", Label).update(f"Trade: ${symbol}")
        
        # Reset chart trackers if token changed
        if old_mint != new_mint:
            self.last_buys = -1
            self.last_sells = -1
            try:
                chart = self.query_one("#price_chart", CandleChart)
                chart.data = [] # Clear old data
                # Re-init with new MC if available, else flat
                mc = token_data.get("marketCapSol", 100.0)
                chart.initialize_chart(mc)
            except: pass
        
        self.update_market_stats()
        self.update_info_box()
        # Reset success/error messages on new token
        self.query_one("#error_label", Label).update("")
        self.query_one("#success_label", Label).update("")
        
        # Trigger metadata fetch if needed
        if "metadata" not in token_data and "uri" in token_data and "metadata_fetching" not in token_data:
            token_data["metadata_fetching"] = True
            asyncio.create_task(self.fetch_and_update(token_data))

    async def fetch_and_update(self, token_data: Dict[str, Any]) -> None:
        """Async fetch metadata for TradePanel."""
        uri = token_data.get("uri")
        if uri:
            try:
                metadata = await fetch_token_metadata(uri)
            except Exception:
                metadata = None
                
            if metadata:
                token_data["metadata"] = metadata
                # Refresh UI if this token is still selected
                if self.token_data and self.token_data.get("mint") == token_data.get("mint"):
                    self.update_info_box()
            else:
                token_data["metadata"] = {"error": "Failed"}
            
            if "metadata_fetching" in token_data:
                del token_data["metadata_fetching"]

    def update_info_box(self) -> None:
        """Update the info box with description and social links."""
        if not self.token_data:
            return
        
        try:
            meta = self.token_data.get("metadata", {})
            
            # Description
            desc = meta.get("description", "-")
            if desc and desc != "-":
                lines = desc.splitlines()
                if len(lines) > 3:
                    desc = "\n".join(lines[:3]).strip() + "..."
                elif len(desc) > 150: # Safeguard for very long single-line descriptions
                    desc = desc[:147] + "..."
            
            self.query_one("#desc_label", Label).update(escape(desc) if desc else "-")
            
            # Social Links
            website = meta.get("website", "")
            twitter = meta.get("twitter", "")
            telegram = meta.get("telegram", "")
            
            def truncate_link(text, limit=35):
                if len(text) > limit:
                    return text[:limit-3] + "..."
                return text

            # Display truncated links or 'None'
            self.query_one("#website_label", Label).update(f"Web: {truncate_link(website)}" if website else "Web: -")
            self.query_one("#twitter_label", Label).update(f"X: {truncate_link(twitter)}" if twitter else "X: -")
            self.query_one("#telegram_label", Label).update(f"TG: {truncate_link(telegram)}" if telegram else "TG: -")
        except:
            pass

    def update_market_stats(self) -> None:
        if not self.token_data: return
        try:
            mint = self.token_data.get("mint", "N/A")
            mc_sol = self.token_data.get("marketCapSol", 0)
            
            # Use TokenTable coloring logic
            mc_thresh = config.thresholds["mc"]
            mc_style = "green" if mc_sol > mc_thresh["yellow"] else "yellow" if mc_sol >= mc_thresh["red"] else "red"
            
            sol_price = getattr(self.app, "sol_price", 0.0)
            if sol_price > 0:
                mc_val_usd = mc_sol * sol_price
                mc_display = f"MC: [{mc_style}]${mc_val_usd:,.0f}[/]"
            else:
                mc_display = f"MC: [{mc_style}]{mc_sol:,.2f} SOL[/]"
            
            self.query_one("#mc_label", Label).update(Text.from_markup(mc_display))
            
            # Chart Update Logic based on Buys/Sells
            curr_buys = self.token_data.get("buys_count", 0)
            curr_sells = self.token_data.get("sells_count", 0)
            
            # Initialize tracking if first run for this token
            if self.last_buys == -1:
                self.last_buys = curr_buys
                self.last_sells = curr_sells
                # Initialize chart flat
                try:
                    self.query_one("#price_chart", CandleChart).initialize_chart(mc_sol if mc_sol > 0 else 100.0)
                except: pass
            else:
                d_buys = curr_buys - self.last_buys
                d_sells = curr_sells - self.last_sells
                
                # "only move if there are buy or sells"
                if d_buys > 0 or d_sells > 0:
                    trend = "neutral"
                    if d_buys > d_sells:
                        trend = "up"
                    elif d_sells > d_buys:
                        trend = "down"
                    
                    try:
                        self.query_one("#price_chart", CandleChart).add_candle(trend)
                    except: pass
                    
                    # Update trackers
                    self.last_buys = curr_buys
                    self.last_sells = curr_sells

            # Volume Display
            vol_val = self.token_data.get("volume_sol", 0.0)
            if sol_price > 0:
                vol_val_usd = vol_val * sol_price
                v_thresh = config.thresholds["vol"]
                v_style = "green" if vol_val_usd > v_thresh["yellow"] else "yellow" if vol_val_usd >= v_thresh["red"] else "red"
                vol_display = f"Vol: [{v_style}]${vol_val_usd:,.0f}[/]"
            else:
                vol_display = f"Vol: [{mc_style}]{vol_val:.2f} SOL[/]"
            
            self.query_one("#vol_label", Label).update(Text.from_markup(vol_display))

            # Dev Status
            dev_sold = self.token_data.get("dev_sold", False)
            dev_str = "Dev: [red]SOLD[/]" if dev_sold else "Dev: [green]HOLDING[/]"
            self.query_one("#dev_label", Label).update(Text.from_markup(dev_str))

            # Dev Initial Buy
            init_buy = self.token_data.get("initial_buy", 0.0)
            self.query_one("#initial_label", Label).update(f"Buy: {init_buy:.2f}")

            # Display Name and full CA
            name = self.token_data.get("name", "Unknown")
            self.query_one("#name_label", Label).update(Text.from_markup(f"[b][#89b4fa]Token Name:[/] {name}"))
            self.query_one("#ca_label", Label).update(Text.from_markup(f"[b][#89b4fa]Contract:[/] {mint}"))
            
            tx = self.token_data.get("tx_count", 0)
            tx_thresh = config.thresholds["tx"]
            tx_style = "green" if tx > tx_thresh["yellow"] else "yellow" if tx >= tx_thresh["red"] else "red"
            self.query_one("#tx_label", Label).update(Text.from_markup(f"Tx: [{tx_style}]{tx}[/]"))
            
            buys = self.token_data.get("buys_count", 0)
            sells = self.token_data.get("sells_count", 0)
            self.query_one("#buys_label", Label).update(Text.from_markup(f"Buys: [green]{buys}[/]"))
            self.query_one("#sells_label", Label).update(Text.from_markup(f"Sells: [red]{sells}[/]"))
            
            traders = self.token_data.get("traders", [])
            h_count = len(traders) if isinstance(traders, (list, set)) else 0
            h_thresh = config.thresholds["holders"]
            h_style = "green" if h_count > h_thresh["yellow"] else "yellow" if h_count >= h_thresh["red"] else "red"
            self.query_one("#holders_label", Label).update(Text.from_markup(f"Hold: [{h_style}]{h_count}[/]"))

            # Update Creator Stats
            creator = self.token_data.get("creator") or self.token_data.get("traderPublicKey", "N/A")
            if creator and creator != "N/A":
                display_creator = f"{creator[:4]}...{creator[-4:]}"
                self.query_one("#creator_label", Label).update(f"Creator: {display_creator}")
                
                # Fetch launched/migrated counts asynchronously
                asyncio.create_task(self._fetch_creator_counts(creator))
            else:
                self.query_one("#creator_label", Label).update("Creator: N/A")

            # Simple estimation update
            self.update_estimation()
            
            # Sync active wallet from App
            if hasattr(self.app, "active_wallet"):
                self.active_wallet = self.app.active_wallet # Sync ref
        except: pass

    def update_estimation(self) -> None:
        try:
            amount_str = self.query_one("#amount_input", Input).value.strip()
            label = self.query_one("#estimated_amount", Label)
            
            if not amount_str: 
                label.update("")
                return
            
            mc_sol = self.token_data.get("marketCapSol", 0)
            if mc_sol <= 0: 
                label.update("Waiting for price...")
                return

            price_sol = mc_sol / 1_000_000_000
            
            if self.trade_mode == "buy":
                try:
                    sol_in = float(amount_str)
                    if price_sol > 0:
                        tokens_out = sol_in / price_sol
                        label.update(Text.from_markup(f"[b][#89b4fa]Est:[/][/] {tokens_out:,.0f} Tokens"))
                    else:
                        label.update(Text.from_markup(f"[b][#89b4fa]Est:[/][/] Price Error"))
                except ValueError:
                     label.update(Text.from_markup(f"[b][#89b4fa]Est:[/][/] Invalid Amount"))
            else:
                # Sell Mode
                clean_val = amount_str.replace("%", "").strip()
                try:
                    percent = float(clean_val)
                    label.update(Text.from_markup(f"[b][#89b4fa]Est:[/][/] Selling {percent}%"))
                except ValueError:
                    label.update("")
        except Exception:
            try:
                self.query_one("#estimated_amount", Label).update("")
            except: pass

    # --- Actions ---
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "buy_button":
            self.set_mode("buy")
        elif bid == "sell_button":
            self.set_mode("sell")
        elif bid == "execute_button":
            self.action_execute_trade()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "amount_input":
            return

        val = event.value
        
        if self.trade_mode == "buy":
            # Allow numbers and decimals only
            sanitized = "".join([c for c in val if c.isdigit() or c == "."])
            # Ensure only one dot
            if sanitized.count(".") > 1:
                parts = sanitized.split(".")
                sanitized = parts[0] + "." + "".join(parts[1:])
            
            if val != sanitized:
                 with self.prevent(Input.Changed):
                     event.input.value = sanitized
                     val = sanitized # Update for estimation
                     
        elif self.trade_mode == "sell":
            # Allow numbers only, format with %
            digits = "".join([c for c in val if c.isdigit()])
            
            if digits:
                # Cap at 100
                if int(digits) > 100: digits = "100"
                formatted = f"{digits}%"
            else:
                formatted = ""
                
            if val != formatted:
                with self.prevent(Input.Changed):
                    event.input.value = formatted
                    val = formatted
             
        self.update_estimation()

    def action_execute_trade(self):
        # Validation
        if not self.active_wallet:
            self.query_one("#error_label", Label).update("No Wallet")
            return
        
        try:
            amount_str = self.query_one("#amount_input", Input).value.strip()
            # Use global config for defaults
            slippage = config.default_slippage
            priority_fee = config.default_priority_fee
            
            if self.trade_mode == "sell":
                # Ensure it has % if it's a percentage input
                amount = amount_str if amount_str.endswith("%") else f"{amount_str}%"
            else:
                amount = float(amount_str)
                
            denominated_in_sol = (self.trade_mode == "buy")
            
            self.is_processing = True
            self.query_one("#execute_button", Button).disabled = True
            self.query_one("#execute_button", Button).label = "Processing..."
            
            asyncio.create_task(self._execute_trade_async(
                mint=self.token_data.get("mint"),
                action=self.trade_mode,
                amount=amount,
                denominated_in_sol=denominated_in_sol,
                slippage=slippage,
                priority_fee=priority_fee
            ))
            
        except Exception as e:
             self.query_one("#error_label", Label).update("Invalid Input")

    async def _execute_trade_async(self, mint, action, amount, denominated_in_sol, slippage, priority_fee):
        try:
            # Use pre-loaded client for maximum speed
            if not self.trading_client:
                 # Last second fallback
                 priv_key = self.active_wallet.get("privateKey")
                 self.trading_client = TradingClient(
                    rpc_url=config.rpc_url,
                    wallet_private_key=priv_key,
                    api_key=getattr(config, "api_key", None) if hasattr(config, "api_key") else "" 
                 )
            
            signature = await self.trading_client.execute_trade(
                mint=mint,
                action=action,
                amount=amount,
                denominated_in_sol=denominated_in_sol,
                slippage=slippage,
                priority_fee=priority_fee
            )
            
            # Show toast notification
            self.app.notify(f"✅ Transaction sent!\nSig: {signature[:8]}...", severity="information", title="Trade Executed")
            self.query_one("#success_label", Label).update("") # Clear old label
            self.query_one("#error_label", Label).update("")
            
            # Refresh balance
            await asyncio.sleep(2)
            await self.fetch_wallet_balance()

        except Exception as e:
            # Show error toast
            self.app.notify(f"❌ Trade Failed: {str(e)[:100]}", severity="error", title="Error")
            self.query_one("#error_label", Label).update("") # Clear old label
            with open("error.log", "a") as f:
                 f.write(f"Panel Trade Error: {e}\n")
        finally:
            self.is_processing = False
            btn = self.query_one("#execute_button", Button)
            btn.disabled = False
            btn.label = "Execute (e)"

    async def _fetch_creator_counts(self, creator_pubkey: str):
        """Fetch and update creator launched/migrated counts from DB."""
        try:
            from ..database import db
            stats = await db.get_creator_stats(creator_pubkey)
            if self.is_mounted:
                self.query_one("#launched_count_label", Label).update(f"Tokens: {stats['launched']}")
                self.query_one("#migrated_count_label", Label).update(f"Migrated: {stats['migrated']}")
        except:
            pass

    def action_set_mode_buy(self) -> None:
        self.set_mode("buy")
    
    def action_set_mode_sell(self) -> None:
        self.set_mode("sell")
