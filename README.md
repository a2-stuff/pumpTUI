# pumpTUI

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.1.6-orange.svg)
![Solana](https://img.shields.io/badge/Solana-Data%20Stream-black.svg?logo=solana)

pumpTUI is a Terminal User Interface (TUI) application for viewing and tracking tokens on Pump.fun directly from your terminal. It provides real-time updates, detailed token information, and wallet tracking capabilities.

## Features

- **Self-Healing Token Stream**: Real-time websocket feed with automatic reconnection and error isolation.
- **Real-time Token Discovery**: View new tokens as they are created on Pump.fun instantly.
- **Detailed Token Info**: Select any token to view detailed statistics, including market cap, volume, and holder data.
- **Crypto Ticker**: Live SOL and BTC prices in the footer ticker (Every 10s).
- **USD Metrics**: Automatic conversion of Market Cap and Volume to **$USD** using live SOL prices.
- **Trade Statistics**: Track Buys and Sells for every token in real-time.
- **Wallet Tracking**: Monitor specific wallets and their activities.
- **Interactive TUI**: Fully keyboard-navigable interface built with Textual.
- **System Stats**: View CPU, Memory usage, Network Latency, and Token Velocity (tpm).
- **Data Persistence**: Automatically logs new token data to daily CSV files.
- **Visual Feedback**: Smooth startup and shutdown animations.

## Installation

### Option 1: Docker (Recommended for Easy Setup)

**Zero localhost dependencies** - Everything runs in containers!

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd pumpTUI
    ```

2.  **Configure environment:**
    ```bash
    cp .env.example .env
    # Edit .env with your API key and settings
    ```

3.  **Start with Docker:**
    ```bash
    python3 manage.py start --docker
    ```
    
    That's it! Docker will automatically:
    - Download and set up MongoDB
    - Build the application image
    - Start both containers
    - Connect you to the TUI

📚 **See [DOCKER.md](DOCKER.md) for the complete Docker deployment guide**

### Option 2: Local Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd pumpTUI
    ```

2.  **Set up a virtual environment (optional but recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    This project uses Poetry for dependency management.
    ```bash
    pip install poetry
    poetry install
    ```
    Alternatively, if you use `pip`:
    ```bash
    pip install -r requirements.txt
    ```


## Setup
Environment variables are handled via a `.env` file in the root directory. To configure or update your settings:

1.  **Create/Edit `.env`**: If not present, create a file named `.env` based on `.env.example`.
2.  **Update API Key**: Add your PumpPortal API Key. You can generate one at [pumpportal.fun/trading-api/setup](https://pumpportal.fun/trading-api/setup).
    ```env
    API_KEY=your_actual_api_key_here
    ```
3.  **Update RPC URL**: Use a premium RPC (Alchemy, QuickNode) for faster trade execution.
    ```env
    RPC_URL=https://solana-mainnet.g.alchemy.com/v2/your_key
    ```
4.  **Trading Defaults**: You can also set default slippage and priority fees:
    ```env
    DEFAULT_SLIPPAGE=10
    DEFAULT_PRIORITY_FEE=0.005
    ```

> **Note**: After updating the `.env` file, you must restart the application for changes to take effect.

## Trading Requirements

To use the **Buy** and **Sell** functions, you must set up a wallet within the application:

1.  **Generate a Wallet**: Go to the **Wallets** tab (`w`) and click **Generate New**. This will create a fresh Solana account for you.
2.  **Fund your Wallet**: Send a small amount of SOL to the generated address. This is required for transaction fees and purchasing tokens.
3.  **Set as Default**: In the **Wallets** tab, select your wallet to mark it as the **Active** wallet. You will see an `[X]` next to the active wallet. If you only have one wallet, it will be selected automatically.
4.  **Trade**: Once funded and active, you can press `b` on any token to open the trade modal.

## Usage

To start the application, use the provide management script:

```bash
python3 manage.py start
```

Or run the module directly:

```bash
python3 -m pump_tui.ui.app
```

### Key Bindings

- `n`: Switch to New Tokens view
- `v`: Switch to 24h Volume view
- `t`: Switch to Tracker view
- `w`: Switch to Wallets view
- `x`: Switch to Settings
- `s`: Focus Search bar
- `i`: Switch to Info
- `r`: Refresh Data (Note: Streaming updates automatically)
- `q`: Quit the application (with confirmation)

## Troubleshooting

- **Stream Error**: If you see connection errors, check your internet connection or try restarting the app.
- **Logs**: Debug logs are written to `debug_stream.log` and `error.log`.
