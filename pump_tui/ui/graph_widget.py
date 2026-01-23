from textual.widget import Widget
from rich.text import Text
import random
import math

class CandleChart(Widget):
    """A simple ASCII candlestick chart widget."""
    
    def __init__(self, id: str = None):
        super().__init__(id=id)
        self.data = [] # List of (open, high, low, close)
        self.chart_height = 11
        self.current_price = 100.0
        self.last_trend = None

    def initialize_chart(self, start_price: float, count: int = 40):
        """Initialize chart with flat data at start_price."""
        self.current_price = start_price
        # Fill with neutral small candles to start
        for _ in range(count):
            self.data.append((start_price, start_price, start_price, start_price))

    def add_candle(self, trend: str):
        """Add a new candle based on trend ('up' or 'down')."""
        self.last_trend = trend
        prev_close = self.data[-1][3] if self.data else self.current_price
        
        # Volatility
        change_pct = random.uniform(0.005, 0.02) # 0.5% to 2% move
        
        if trend == "up":
            # Green candle
            close_p = prev_close * (1 + change_pct)
            open_p = prev_close
            high_p = close_p * (1 + random.uniform(0, 0.005))
            low_p = open_p * (1 - random.uniform(0, 0.005))
        elif trend == "down":
            # Red candle
            close_p = prev_close * (1 - change_pct)
            open_p = prev_close
            high_p = open_p * (1 + random.uniform(0, 0.005))
            low_p = close_p * (1 - random.uniform(0, 0.005))
        else:
            # Neutral/Doji
            close_p = prev_close
            open_p = prev_close
            high_p = prev_close * 1.001
            low_p = prev_close * 0.999

        self.current_price = close_p
        self.data.append((open_p, high_p, low_p, close_p))
        
        # Keep buffer limit (e.g. 100 candles)
        if len(self.data) > 100:
            self.data.pop(0)
            
        self.refresh()

    def render(self) -> Text:
        if not self.data:
            return Text("Waiting for price data...", style="dim")

        width = self.size.width
        if width < 4: return Text("")
        
        # Position latest candle 3 quarters of the way (75% history, 25% gap)
        target_idx = (width * 3) // 4
        
        # Available slots to the left (including target): target_idx + 1
        visible_count = min(len(self.data), target_idx + 1)
        visible_data = self.data[-visible_count:]
        
        # Determine range based ONLY on visible data
        all_vals = [x for candle in visible_data for x in candle]
        if not all_vals:
             return Text("")
             
        min_val = min(all_vals)
        max_val = max(all_vals)
        
        # Add padding
        padding = (max_val - min_val) * 0.1
        if padding == 0: padding = max_val * 0.01
        
        min_val -= padding
        max_val += padding
        
        if max_val == min_val:
            max_val += 1.0 

        scale = self.chart_height / (max_val - min_val)
        
        lines = ["" for _ in range(self.chart_height)]
        
        # Render Loop
        # Start column for data: target_idx - visible_count + 1
        start_col = target_idx - visible_count + 1
        
        # Pre-fill left empty space
        for _ in range(start_col):
            for y in range(self.chart_height):
                lines[y] += " "

        # Render Data
        for o, h, l, c in visible_data:
            y_high = int((max_val - h) * scale)
            y_low = int((max_val - l) * scale)
            y_open = int((max_val - o) * scale)
            y_close = int((max_val - c) * scale)
            
            y_high = max(0, min(self.chart_height - 1, y_high))
            y_low = max(0, min(self.chart_height - 1, y_low))
            y_open = max(0, min(self.chart_height - 1, y_open))
            y_close = max(0, min(self.chart_height - 1, y_close))
            
            is_green = c >= o
            color = "green" if is_green else "red"
            
            start_body = min(y_open, y_close)
            end_body = max(y_open, y_close)
            
            for y in range(self.chart_height):
                char = " "
                if y_high <= y <= y_low:
                    if start_body <= y <= end_body:
                        char = "█"
                    else:
                        char = "│"
                
                lines[y] += f"[{color}]{char}[/]"
        
        # Fill right empty space (25% gap)
        remaining = width - (start_col + visible_count)
        for i in range(remaining):
            for y in range(self.chart_height):
                char = " "
                # Draw arrow in top right (y=5, last column)
                if self.last_trend and y == 5 and i == remaining - 1:
                    if self.last_trend == "up":
                        char = "[green]▲[/]"
                    elif self.last_trend == "down":
                        char = "[red]▼[/]"
                lines[y] += char

        return Text.from_markup("\n".join(lines))
