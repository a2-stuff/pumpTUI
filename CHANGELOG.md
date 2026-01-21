# Changelog

All notable changes to this project will be documented in this file.

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
