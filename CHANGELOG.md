# Changelog

All notable changes to SunoSync will be documented in this file.

## [2.1] - 2025-01

### Added
- **Borderless Window Design**: Modern, frameless window with custom drag functionality and close button
- **Enhanced Splash Screen**: Improved splash screen timing and visibility - no more brief window flash before splash appears
- **Linux Support**: Full compatibility with Linux systems (Ubuntu, Debian, Arch, etc.)

### Fixed
- **Linux Font Loading**: Cross-platform font detection with fallbacks for DejaVu and Liberation fonts on Linux
- **Linux Icon Loading**: Platform-specific icon handling (.ico for Windows, .png for Linux/macOS)
- **PhotoImage Garbage Collection**: Fixed image reference issues that caused TclError on Linux
- **Cross-Platform Compatibility**: Works with system Python in virtual environments on all platforms

### Changed
- **Player Widget Sizing**: Fixed audio player being squished - now maintains proper height (160px) using grid layout
- **Splash Screen Visibility**: Fixed main window showing briefly before splash screen appears
- **Stop Button**: Enhanced stop functionality to properly halt downloads/preloads and reset UI state
- **Preload Functionality**: Fixed preload mode not working - now properly scans without downloading
- **Debug Log**: Fixed debug log not showing output in compiled EXE
- **Download/Preload Operations**: Improved error handling and logging for download and preload operations

### Changed
- **Window Management**: Converted from pack to grid layout for better widget height control
- **UI Polish**: Further refined borderless window design for a more professional appearance

## [Unreleased]

### Added
- **Debug Log Window**: Built-in debug log viewer for troubleshooting (manual open, doesn't auto-open on startup)
- **Save Debug Logs**: Export debug logs as text files for bug reports
- **Disable Notification Sounds**: Option in settings to turn off Windows alert notification sounds
- **Improved Lyrics Support**: Lyrics editor now reads from both embedded metadata and `.txt` files, prioritizes `.txt` files when available
- **Auto-embed Lyrics**: Lyrics are now automatically embedded for all new downloads, even when full metadata embedding is disabled

### Fixed
- **Startup Crash (Infinite Recursion)**: Fixed silent crash on startup caused by recursive call in `LibraryTab.update_tree()` with no exit condition
- **Playlist API 404 Errors**: 
  - Added trailing slash to playlist API URL: `/api/playlist/{id}/`
  - Updated `fetch_playlists()` to use correct endpoint: `/api/playlist/me?page=1&show_trashed=false&show_sharelist=false`
  - Implemented 404 fallback logic: if `/api/project/{id}` returns 404, automatically switches to `/api/playlist/{id}/` (legacy mode)
  - Improved playlist response parsing to handle various API response structures
- **UI Layout Issues**: 
  - Reduced button widths from 110px to 95px for Filters, Workspaces, and Playlists buttons to fit properly in the row
  - Fixed song counter text truncation (now shows full "songs" text)
  - Fixed toggle label truncation in settings (added minimum column widths)
  - Fixed progress bar squishing (increased from 6px to 20px height)
- **Playlist Dialog Crash**: Added `title` parameter to `WorkspaceBrowser.__init__()` in `suno_widgets.py`
- **Playlist Download Crash (NameError)**: Fixed undefined `current_uuid` variable by properly extracting `uuid` from `song_data.get("id")` in `suno_downloader.py`
- **Tag System Issues**:
  - Fixed tag buttons (Like/Trash/Star) not working - now properly toggles tags and updates UI
  - Fixed tag icons not showing in library column - improved filepath normalization for consistent tag lookups
  - Fixed selection being lost when toggling tags - now preserves and restores selection after tag updates
  - Fixed sorting by trashed/starred songs - normalized filepaths for proper tag filtering
- **Lyrics Editor Issues**:
  - Fixed lyrics not showing for songs with `.txt` files - now reads from both sources
  - Fixed lyrics editor not opening - improved error handling and filepath normalization
  - Fixed lyrics not being embedded in WAV files - corrected save logic and lyrics embedding for WAV format
  - Lyrics now always embedded automatically for new tracks regardless of metadata setting
- **Audio Playback Issues**:
  - Fixed audio playback failing silently - added clear error messages for VLC initialization failures
  - Fixed library selection not updating when using next/previous buttons - improved track change synchronization
  - Fixed player widget visibility and sizing issues - removed fixed height constraints
- **Filter Popup**: Made filter dialog scrollable and ensured Save button is always visible
- **Smart Resume**: Fixed smart resume to work with large libraries - now adaptively scales threshold (2-20 pages) and only stops after finding new songs first

### Changed
- **Code Cleanup**: Removed all debug print statements throughout the codebase (redirected to debug log window instead)
- **Error Handling**: Improved error handling consistency, better error messages, and thread-safe UI updates
- **File Cleanup**: Removed debug/test files and unnecessary utility scripts
- **Smart Resume Algorithm**: Improved to handle libraries where first pages are already downloaded - won't stop prematurely
- **Lyrics Embedding**: Lyrics are now embedded by default for all new downloads, even if other metadata embedding is disabled
- **Tag System**: Improved filepath normalization across all tag operations for consistent behavior
- **UI Polish**: Fixed various visual bugs including text truncation, button borders, and element sizing

## [2.0.0] - 2024

### Added
- Library tab with metadata browsing and playback
- Audio player with VLC integration
- Playlist and workspace browsing
- Advanced filtering options
- Download queue management
- Metadata embedding (ID3 tags, album art, lyrics)
- WAV file download support
- Rate limiting for API requests
- Monthly folder organization
- Smart resume (never downloads same song twice)

### Changed
- Refactored codebase into modular structure:
  - `main.py` - Main application entry point
  - `suno_downloader.py` - Download logic and API interaction
  - `suno_utils.py` - Utility functions
  - `suno_widgets.py` - Custom Tkinter widgets
  - `suno_layout.py` - Layout builders and dialogs
  - `library_tab.py` - Library browsing interface
  - `player_widget.py` - Audio player component
  - `downloader_tab.py` - Download management interface
  - `config_manager.py` - Configuration management
  - `theme_manager.py` - Theme and styling management

### Fixed
- WAV generation timeout increased to 120 seconds
- Improved error handling for network requests
- Better handling of API rate limits

## [1.0.0] - 2024

### Added
- Initial release
- Basic download functionality
- Metadata embedding
- GUI interface

