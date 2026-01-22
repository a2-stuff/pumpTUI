# Changelog

All notable changes to this project will be documented in this file.

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
