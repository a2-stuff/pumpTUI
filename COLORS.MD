# Color Guide for pumpTUI

This document explains the meaning of colors used in the pumpTUI interface for various metrics and statuses. Colors are often dynamic and depend on configurable thresholds.

## Global Thresholds

Most metrics use a three-color system based on thresholds defined in the application settings:

- **[Green]**: Above the "Yellow" threshold (High/Healthy)
- **[Yellow]**: Between "Red" and "Yellow" thresholds (Moderate)
- **[Red]**: Below the "Red" threshold (Low/Warning)

---

## Metric Breakdown

### Market Cap (MC)

Determined by the token's market capitalization in SOL.

- **Green**: High Market Cap (Default: > 160 SOL)
- **Yellow**: Medium Market Cap (Default: 80 - 160 SOL)
- **Red**: Low Market Cap (Default: < 80 SOL)
*Displayed as USD ($) if the SOL price is available, otherwise shows in SOL (S).*

### Volume (Vol)

Calculated as the total trading volume in USD (if SOL price is available).

- **Green**: High Volume (Default: > $60,000)
- **Yellow**: Medium Volume (Default: $30,000 - $60,000)
- **Red**: Low Volume (Default: < $30,000)

### Transaction Count (Tx)

The total number of trades recorded for the token.

- **Green**: High Activity (Default: > 110 Tx)
- **Yellow**: Moderate Activity (Default: 50 - 110 Tx)
- **Red**: Minimal Activity (Default: < 50 Tx)

### Holder Count (Hold)

The number of unique wallets that have interacted with the token.

- **Green**: Many Holders (Default: > 120)
- **Yellow**: Moderate Holders (Default: 50 - 120)
- **Red**: Few Holders (Default: < 50)

### Transaction Types

- **Green (Buys)**: All buy transactions.
- **Red (Sells)**: All sell transactions.

### Developer Status (Dev)

Indicates whether the token creator has sold their initial position.

- **Green (SOLD)**: The developer has sold. In the table, this is green to indicate the dev dump threat has passed.
- **Red (HOLDING)**: The developer is still holding. In the table, this is red to indicate a potential "rug" or dump risk.
*Note: In the Token Detail view, "YES (SOLD)" may appear in red to highlight the event of selling, while "NO (HOLDING)" appears in green.*

### Initial Buy (Buy)

The amount of SOL the creator spent to buy their own token at launch.

- **Green**: High Confidence (Default: > 2.0 SOL)
- **Yellow**: Moderate Confidence (Default: 1.0 - 2.0 SOL)
- **Red**: Low Confidence (Default: < 1.0 SOL)

---

## Action Colors

- **Green Buttons**: Execute Trade, Buy.
- **Red Buttons**: Sell.
- **Blue/Cyan Tokens**: Selected or highlighted items.

---

*Note: Thresholds can be customized in the **Settings** tab within pumpTUI.*
