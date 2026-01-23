# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.9] - 2026-01-22

### Added
- **Docker Performance Overhaul**: 
  - Switched from Alpine to Debian Slim (`glibc`) for native-tier Python execution speed and UI responsiveness.
- **Global Connection Pooling**: Unified all network requests (Trades, RPC, Metadata) under a single shared HTTP pool to eliminate SSL handshake overhead.
- **Encryption Key Generator**: Added `--encryption-key` flag to `manage.py` to generate a secure `SETTINGS_ENCRYPTION_KEY` for database encryption.
- **Project Stack Name**: Added `-p pumpTUI` to all Docker Compose commands for consistent container naming and isolation.
- **Persistent API Token**: Settings screen now saves the API Token securely to MongoDB (encrypted if key is present).
- **Docker TrueColor Support**: Added `COLORTERM=truecolor` support in Docker for accurate theme rendering.
- **Theme Persistence**: Selected themes are now automatically saved to the database and persist across restarts.

### Changed
- **Trading UX**: Hotkeys `b` (Buy) and `s` (Sell) now work flawlessly even when focused on the amount input field.
- **UI Refinement**: Added 1-line padding between the token table scrollbar and the vertical divider for better visual clarity.
- **Hotkey Conflict Fix**: Changed Command Palette hotkey from `Ctrl+P` to `Ctrl+L` to avoid conflicts with Docker's detach sequence.
- **Trading Defaults**: Set the default Sell amount to 100% for faster execution.

### Fixed
- **Docker Trading Crash**: Fixed "TradingClient is not defined" error and ensured the Execute button label resets correctly on failure.
- **Trade Execution Speed**: Optimized transaction creation by loading `TradingClient` at app-level and warmed-up imports.
- **PumpPortal API**: Fixed "Bad Request" (400) error by ensuring `denominatedInSol` is sent as a boolean.
- **Dependency Issues**: Added `solana` and `solders` to Dockerfile to resolve transaction errors in containers.
- **Notification API**: Corrected `notify()` calls to use `severity` instead of `variant`.

### Removed
- **CSV Logging**: Completely removed file-based CSV token logging in favor of centralized MongoDB storage.
- **File Wallets**: Removed `wallets.json` support. All wallets are now stored securely and exclusively in the database.

## [v1.1.8] - 2026-01-22

### Added
- **Docker Deployment Improvements**:
  - **Smart Container Management**: The `manage.py start --docker` command now intelligently detects container state:
    - If containers are running → Attaches to the session
    - If containers are stopped → Restarts them without rebuilding
    - If containers don't exist → Creates and builds them
  - **New `rebuild` Command**: Added `python3 manage.py rebuild --docker` for explicit image rebuilding after code changes
  - **Data Safety**: Eliminates prompts to recreate containers, protecting wallet and settings data
  - **Dynamic Container Naming**: Handles Docker-generated container name prefixes automatically
- **Documentation Enhancements**:
  - Enhanced README.md with comprehensive deployment instructions for both Docker and Standalone modes
  - Added clear workflow examples and command references
  - Created DOCKER_IMPROVEMENTS.md explaining the new container management system
  - Updated DOCKER.md with new rebuild command documentation

### Changed
- **Container Startup Logic**: 
  - Removed automatic `--build` flag from `start --docker` command
  - Only builds when image is missing, preventing unnecessary container recreation
  - Faster startup times when restarting existing containers
- **Documentation Structure**: Reorganized README for better clarity between Docker and Standalone deployment

### Fixed
- **Container Recreation Issue**: Fixed prompt asking to "Continue with the new image?" which could cause data loss concerns
- **Startup Reliability**: Resolved Docker startup failures when containers had stale image references
- **Container Attach**: Fixed error when attaching to containers with Docker-generated name prefixes

## [v1.1.7] - 2026-01-22

### Added
- **Live Candle Graph**: Added a real-time ASCII candlestick chart to the Trade Panel.
  - Features dynamic auto-scaling and centering based on visible history.
  - Updates only on price movement (Market Cap change) or active Buy/Sell pressure.
  - Color-coded candles (Green for UP, Red for DOWN) based on trade trend.
- **Trade Panel UI Overhaul**:
  - Restructured layout with boxed containers for cleaner organization.
  - **Market Stats**: Added "Initial Buy" (In. Buy) and "Dev Status" (SOLD/HOLDING) indicators.
  - **Contract Info**: Moved Contract Address to a dedicated box, including full social links and description.
  - **Input Box**: Improved layout with stacked input and estimate fields for better visibility.
- **Global Keybindings**:
  - Added global `e` hotkey to execute trades from anywhere in the app.
  - Restored `Enter` hotkey to select tokens from the list.

### Changed
- **Visuals**:
  - Centered Buy/Sell buttons at the top of the panel.
  - Adjusted button colors (Sell is now Red).
  - Ticker symbol now includes `$` prefix.
  - Optimized vertical spacing and box heights for a compact view.
  - Truncated social links to prevent overflow.
- **Performance**:
  - Replaced 1-second polling in Trade Panel with purely event-driven real-time updates.

## [v1.1.6] - 2026-01-21

### Added
- **Robust Connection Management**: 
  - Implemented automatic WebSocket reconnection with exponential backoff for the token stream.
  - Added "Stream Connected" and "Reconnecting..." notifications for better visibility of connection status.
- **Enhanced Data Flow**:
  - Isolated individual event handling to prevent single malformed messages from interrupting the data stream.
  - Standardized JSON payloads for trade execution to ensure full compatibility with the PumpPortal API.
- **Comprehensive Logging**:
  - Detailed diagnostic logging in `error.log` for failed transaction creations, capturing full payload and response data.
  - Redacted heavy debug logging to improve terminal disk I/O performance.

### Fixed
- **System Stability**: 
  - Resolved UI freezes and the 100% CPU lock when opening the trade modal by optimizing list processing and render cycles.
  - Fixed a common crash related to unmounted widgets during asynchronous balance updates.
- **Trade Execution**: Fixed "Bad Request" errors when buying/selling tokens by ensuring correct data types (booleans/numbers) are sent to the PumpPortal API.

### Removed
- **Unstable Navigation**: Reverted the experimental token navigation (Prev/Next) in the Trade Modal to maintain application stability under high load.


## [v1.1.5] - 2026-01-21

### Added
- **Wallet Manager Enhancements**:
  - New **Created** column showing when a wallet was added.
  - New **Txs** column showing live transaction counts for all wallets.
  - **Copy Address** button to quickly get your own wallet CA.
  - **Delete Selected** button with safety checks.
- **Contextual Hotkeys**:
  - Trade `(b)` and Copy CA `(c)` hotkeys now only appear in the footer when on the **New Tokens** tab.
  - Unified notification style for better visual feedback.

### Fixed
- **Wallet Balance**: Resolved an issue where balances would stay stuck on "Checking..." due to RPC timeouts.
- **Hotkey Stability**: Fixed an async/sync mismatch that caused `b` and `c` keys to be unresponsive.

## [v1.1.4] - 2026-01-21

### Added
- **Smart Trade Inputs**:
  - Automatic numeric/decimal validation in the trade modal.
  - Auto-suffixing `%` for slippage and sell percentages.
  - Active Wallet Address display in the trade modal for better transparency.
- **Improved Error Handling**:
  - Human-friendly identification of common RPC errors (e.g., "Insufficient SOL").
  - Automated public key derivation from private keys in the configuration.

### Fixed
- **Keybinding Stability**: Fixed focus-trapping in Settings and Tracker tabs that disabled navigation shortcuts.
- **Trade Counters**: Resolved a syncing issue where Buys/Sells counts in the modal didn't match the live table.
- **Focus Refinement**: Improved `safe_focus` logic to prevent random jumps to the search bar.

## [v1.1.3] - 2026-01-21

### Added
- **Trading Modal Enhancements**: 
  - Real-time `(1s)` Market Cap updates with color coding.
  - Wallet Balance display.
  - Button hints `(e)`/`(c)` and improved styling.
  - Active Wallet Selection in Wallet Manager `(w)` - simply check the box to use a wallet for trading.
- **Configurable Settings**: 
  - **RPC URL**: customizable Solana RPC endpoint.
  - **Defaults**: Customizable default slippage and priority fees.

### Fixed
- **Keybinding Focus**: Resolved issues where pressing keys `s`, `n`, etc. during trading or navigation would reset the view or steal focus.
- **Raydium/Migration Tracking**: Resolved a logic error where the very first event for a newly discovered token (migrated or missed creation) was not being counted towards "Buys". 
- **Count Accuracy**: All discovered tokens now correctly capture their initial trade data upon discovery.
- **Robust Inference**: Enhanced trade type inference for missing metadata in the stream.

### Changed
- **Wallet Architecture**: Private keys are now loaded from secure local `wallets.json` via the Active Wallet selector, removing manual entry from Settings.
- **UI Tweaks**: Renamed "Holders" -> "Hold" (continued) and increased table width to 66% (details 34%) for better readability.
- **Image Sizing**: Reduced token detail image size by ~5% for better fit.
- **Version Increment**: Bumped to v1.1.3.

## [v1.1.2] - 2026-01-21

### Changed
- **UI Renaming**: Renamed "Holders" column to "Hold" for better table fit.
- **Version Increment**: Bumped to v1.1.2.

### Fixed
- **Raydium (Bonk) Buys**: Corrected a potential crash in trade aggregation that prevented "Buys" from updating on migrated tokens.

## [v1.1.1] - 2026-01-21

### Added
- **Crypto Ticker**: Real-time SOL and BTC price ticker in the footer (fetching from DexScreener).
- **USD Conversion**: Token "Market Cap" and "Volume" now automatically calculate USD values based on live SOL price.
- **Trade Stats**: New "Buys" and "Sells" columns in the token table for detailed session activity tracking.

### Fixed
- **Raydium (Bonk) Tracking**: 
  - Fixed volume staying at $0 for migrated tokens by implementing SOL price estimation.
  - Fixed "Buys" not showing for `bonk` pool events by improving `txType` inference and processing.
- **Footer Layout**: Stabilized the bottom bar layout to prevent UI elements from overlapping.

### Changed
- **Refresh Cycle**: Reduced BTC/SOL price refresh interval to 10 seconds for better performance/limit balance.
- **Version Increment**: Bumped to v1.1.1.

## [v1.1.0] - 2026-01-21

### Added
- **Metric Tracking**: Added "Velocity" (tokens per minute) and real-time "Latency" to the header.
- **Data Persistence**: New tokens are now logged to `tokensdb/tokens_YYYY-MM-DD.csv`.
- **Animations**: Added `StartupScreen` with loading steps and `ShutdownScreen` validation.
- **Quit Confirmation**: Pressing 'q' now presents a Yes/No modal.
- **Image Resilience**: Added multiple IPFS gateways and fallback logic for token images.

### Changed
- **UI & Layout**:
  - Renamed tabs: "Tracker" (was Wallet Tracker), "Wallets" (was Wallet Manager), "Volume" (was Trending).
  - Reduced button sizes and centered pagination controls.
  - Improved spacing in the header and details panel.
  - Token names in the table are now truncated (First5...Last5).
  - Removed border around token images for a cleaner look.
- **Performance**:
  - Reduced WebSocket ping interval to 2 seconds for real-time latency updates.
  - Fixed a focus-stealing bug where background updates forced navigation back to the "New Tokens" tab.
- **Key Bindings**:
  - Remapped `x` to Settings.
  - Remapped `s` to Focus Search.

## [v1.0.1] - 2026-01-21

### Added
- Added `README.md` documentation.
- Added `CHANGELOG.md`.

### Changed
- Bumped application version to v1.0.1 in the UI header.
