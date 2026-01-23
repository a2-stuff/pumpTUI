# pumpTUI

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.1.9-orange.svg)
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
- **Data Persistence**: Centralized MongoDB storage for all tokens, wallets, and configuration.
- **Visual Feedback**: Smooth startup and shutdown animations.

## Installation

pumpTUI can be deployed in two ways: **Docker** (recommended, zero dependencies) or **Standalone** (local Python installation).

### Option 1: 🐳 Docker Deployment (Recommended)

**Zero localhost dependencies** - Everything runs in isolated containers!

#### Quick Start

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd pumpTUI
    ```

2.  **Configure environment:**
    ```bash
    # Generate a secure encryption key for your wallets
    python3 manage.py --encryption-key
    
    # Configure your API key and settings
    nano .env
    ```

3.  **Start the application:**
    ```bash
    python3 manage.py start --docker
    # Or with sudo if needed:
    sudo python3 manage.py start --docker
    ```

**What happens automatically:**
- Downloads MongoDB container (if needed)
- Builds pumpTUI application image
- Creates persistent data volumes
- Starts both containers
- Attaches you to the TUI interface

#### Docker Commands

```bash
# Start (smart: attaches if running, starts if stopped, builds if missing)
python3 manage.py start --docker

# Stop (preserves all data)
python3 manage.py stop --docker

# Rebuild after code changes (data preserved)
python3 manage.py rebuild --docker

# Complete cleanup (⚠️ DELETES ALL DATA)
python3 manage.py clean --docker
```

#### Benefits of Docker Deployment

✅ No Python packages installed on your system  
✅ No MongoDB installation required  
✅ Consistent environment across all machines  
✅ Automatic wallet/settings persistence in Docker volumes  
✅ Easy distribution: `git clone` + `start --docker`  
✅ One-command cleanup

📚 **For detailed Docker documentation, see [DOCKER.md](DOCKER.md)**

---

### Option 2: 💻 Standalone Installation

**Local Python installation** - Full control over dependencies.

#### Prerequisites

- Python 3.10+
- MongoDB (running locally or remote)
- pip or Poetry

#### Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd pumpTUI
    ```

2.  **Set up a virtual environment (recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    
    **Using Poetry (recommended):**
    ```bash
    pip install poetry
    poetry install
    ```
    
    **Using pip:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install and configure MongoDB:**
    ```bash
    # Ubuntu/Debian
    sudo apt-get install mongodb
    sudo systemctl start mongodb
    
    # macOS
    brew install mongodb-community
    brew services start mongodb-community
    ```

5.  **Configure environment:**
    ```bash
    # Generate encryption key
    python3 manage.py --encryption-key
    
    # Edit .env with your settings
    nano .env
    ```

#### Standalone Commands

```bash
# Start with management script
python3 manage.py start

# Or run directly
python3 -m pump_tui.main

# Stop (Ctrl+C or press 'q' in app)
```

---

## Configuration

Environment variables are managed via `.env` in the root directory:

1.  **Create/Edit `.env`**: 
    ```bash
    cp .env.example .env
    nano .env  # or your preferred editor
    ```

2.  **Required Settings:**
    ```env
    # PumpPortal API Key (get from: https://pumpportal.fun/trading-api/setup)
    API_KEY=your_actual_api_key_here
    
    # Solana RPC (use premium for better performance)
    RPC_URL=https://solana-mainnet.g.alchemy.com/v2/your_key
    
    # MongoDB Connection (Docker auto-configures this)
    MONGO_URI=mongodb://localhost:27017
    
    # Encryption key for secure wallet storage (Generate with: python3 manage.py --encryption-key)
    SETTINGS_ENCRYPTION_KEY=your_generated_key_here
    ```

3.  **Optional Trading Defaults:**
    ```env
    DEFAULT_SLIPPAGE=10
    DEFAULT_PRIORITY_FEE=0.005
    ```

> **Note**: Restart the application after changing `.env` for changes to take effect.

---

## Trading Setup

To use **Buy** and **Sell** functions:

1.  **Navigate to Wallets**: Press `w` to open the Wallets tab
2.  **Generate Wallet**: Click **Generate New** to create a Solana wallet
3.  **Fund Wallet**: Send SOL to the generated address (for fees and trading)
4.  **Set Active**: Check the box next to your wallet to mark it active `[X]`
5.  **Trade**: Press `b` on any token to open the trade modal

> **Security**: Wallets are stored encrypted in MongoDB using the `SETTINGS_ENCRYPTION_KEY`.

---

## Usage

### Running the Application

**Docker:**
```bash
python3 manage.py start --docker
# Detach without stopping: Ctrl+P, then Ctrl+Q
```

**Standalone:**
```bash
python3 manage.py start
# Exit: Press 'q' or Ctrl+C
```

### Key Bindings

- `n`: Switch to New Tokens view
- `v`: Switch to 24h Volume view
- `t`: Switch to Tracker view
- `w`: Switch to Wallets view
- `x`: Switch to Settings
- `s`: Focus Search bar
- `i`: Switch to Info
- `Ctrl+L`: Open Command Palette (Theme picker)
- `q`: Quit the application (with confirmation)

## Troubleshooting

- **Stream Error**: If you see connection errors, check your internet connection or try restarting the app.
- **Logs**: Debug logs are written to `debug_stream.log` and `error.log`.
