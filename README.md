# pumpTUI

pumpTUI is a Terminal User Interface (TUI) application for viewing and tracking tokens on Pump.fun directly from your terminal. It provides real-time updates, detailed token information, and wallet tracking capabilities.

## Features

- **Real-time Token Streaming**: View new tokens as they are created on Pump.fun.
- **Detailed Token Info**: Select any token to view detailed statistics, including market cap, volume, and holder data.
- **Wallet Tracking**: Monitor specific wallets and their activities.
- **Interactive TUI**: Fully keyboard-navigable interface built with Textual.
- **System Stats**: View CPU, Memory usage, Network Latency, and Token Velocity (tpm).
- **Data Persistence**: Automatically logs new token data to daily CSV files.
- **Visual Feedback**: Smooth startup and shutdown animations.

## Installation

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

Environment variables are handled via a `.env` file or system environment variables.

1.  Create a `.env` file in the root directory (if not already present).
2.  Add your API Key if you have a custom one (optional, a default key is included):
    ```env
    API_KEY=your_api_key_here
    ```

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
