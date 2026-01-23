# pumpTUI

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.1.9-orange.svg)
![Solana](https://img.shields.io/badge/Solana-Data%20Stream-black.svg?logo=solana)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Blockchain](https://img.shields.io/badge/Blockchain-Solana-black.svg)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)
![Windows](https://img.shields.io/badge/Windows-0078D6?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)

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

**Local Python installation** - MongoDB runs automatically in a Docker container.

#### Prerequisites

- Python 3.10+
- Docker (for MongoDB container)
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

4.  **Configure environment:**
    ```bash
    # Generate encryption key
    python3 manage.py --encryption-key
    
    # Edit .env with your settings
    nano .env
    ```

#### Standalone Commands

```bash
# Start (automatically starts MongoDB container)
python3 manage.py start

# Stop app and MongoDB container
python3 manage.py stop

# Or run directly (requires MongoDB already running)
python3 -m pump_tui.main
```

> **Note**: The management script automatically starts and stops a `pumpTUI-mongo` Docker container for the database. Data is persisted in a Docker volume and preserved between sessions.

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

## Data Storage

pumpTUI stores all data (tokens, wallets, settings, tracking) in MongoDB. **Both deployment modes share the same MongoDB container** so your data is available whether you run standalone or Docker mode.

### Shared MongoDB Container

| Component | Name |
|-----------|------|
| Container Name | `pumptui-mongo` |
| Docker Volume | `pumptui-mongodb` |
| External Port | `27018` |

### 🐳 Docker Deployment

| Data Type | Location |
|-----------|----------|
| MongoDB Database | Docker volume: `pumptui-mongodb` |
| App Container | `pumptui-app` |
| MongoDB Container | `pumptui-mongo` |
| Log Files | Mounted to project directory (`./error.log`, `./debug_stream.log`, etc.) |

### 💻 Standalone Mode

| Data Type | Location |
|-----------|----------|
| MongoDB Database | Docker volume: `pumptui-mongodb` (shared with Docker mode) |
| MongoDB Container | `pumptui-mongo` (shared with Docker mode) |
| Log Files | Project directory (`./error.log`, `./debug_stream.log`, etc.) |

**View containers/volumes:**
```bash
docker ps -a --filter "name=pumptui"
docker volume ls | grep pumptui
```

**Data persists** across container restarts, app exits, and switching between modes. Only `python3 manage.py clean --docker` will delete the data.

> **Backup Tip**: To backup your data, you can use `docker volume` commands or `mongodump` against the running MongoDB instance on `localhost:27018`.

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

#### Navigation
- `n`: Switch to New Tokens view
- `t`: Switch to Tracker view
- `w`: Switch to Wallets view
- `x`: Switch to Settings
- `/`: Focus Search bar
- `i`: Switch to Info
- `Ctrl+L`: Open Command Palette (Theme picker)
- `q`: Quit the application (with confirmation)

#### Trading (New Tokens View)
- `b`: Switch to Buy mode
- `s`: Switch to Sell mode
- `e`: Execute trade
- `c`: Copy Contract Address to clipboard
- `o`: Open token on pump.fun in browser
- `Enter`: Select token for Trade Panel

#### Sorting (New Tokens View)
- `m`: Sort by Market Cap
- `v`: Sort by Volume
- `l`: Reset to Live sort (newest first)

## Troubleshooting

- **Stream Error**: If you see connection errors, check your internet connection or try restarting the app.
- **Logs**: Debug logs are written to `debug_stream.log` and `error.log`.

---

## Support & Contributions

If you find pumpTUI useful, consider supporting the project:

🪙 **Token**: [$pumpTUI](https://pump.fun/coin/3rJip4AWxjhgZFNNwzWcschF52gHx1ogGBzaQ9UGpump)  
💰 **Sol Wallet**: `HDsYhpxoq3AnXbmoXhan7Dor72hwsXVuBfX2BtCDy7dJ`

