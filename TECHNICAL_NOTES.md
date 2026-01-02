# Technical Notes & Fixes

This document tracks technical issues and their resolutions for SunoSync V2.

## Recent Fixes (Latest Session)

### 1. Linux Compatibility - Font & Icon Loading ✅
**Problem**: App crashed on Arch Linux with `OSError: cannot open resource` and `TclError: bitmap not defined`  
**Root Cause**: 
- Hardcoded Windows font paths (`arial.ttf`) don't exist on Linux
- `.ico` files not supported on Linux
- Image references being garbage collected

**Fixes Applied**:
- **theme_manager.py**: Added cross-platform font detection
  - Windows: `arial.ttf`, `seguiemj.ttf`
  - macOS: `Arial.ttf`
  - Linux: Multiple fallback paths for DejaVu and Liberation fonts
  - Ultimate fallback: `ImageFont.load_default()`

- **main.py**: Platform-specific icon handling
  - Windows: Uses `.ico` with `iconbitmap()`
  - Linux/macOS: Uses `.png` with `iconphoto()` (resized to 32x32)
  - Silently ignores icon errors (cosmetic)

- **downloader_tab.py**: Fixed PhotoImage garbage collection
  - Store PIL image before creating PhotoImage
  - Added `_create_title_image_pil()` helper
  - Keep reference to prevent garbage collection

**Location**: `theme_manager.py`, `main.py`, `downloader_tab.py`  
**Status**: ✅ Fixed - App now runs on Arch Linux with system Python

### 2. Startup Crash (Infinite Recursion) ✅
**Problem**: App crashed silently on startup  
**Root Cause**: `LibraryTab.update_tree()` had a recursive call to itself with no exit condition  
**Location**: `library_tab.py` line 367  
**Fix**: Removed the recursive call (now commented out)  
**Status**: ✅ Fixed

### 2. Playlist Search Functionality ✅
**Problem**: Playlist API was returning 404 errors  
**Fixes Applied**:
- Added trailing slash to playlist API URL: `/api/playlist/{id}/`
- Updated `fetch_playlists()` to use correct endpoint: `/api/playlist/me?page=1&show_trashed=false&show_sharelist=false`
- Implemented 404 fallback logic: if `/api/project/{id}` returns 404, automatically switches to `/api/playlist/{id}/` (legacy mode)
- Ensured `playlist_clips` array is correctly parsed from API responses

**Location**: `suno_downloader.py`
- Lines 196, 259-260: 404 fallback logic
- Lines 539-556: `fetch_playlists()` method

**Status**: ✅ Fixed

### 3. UI Layout Issues ✅
**Problem**: Three buttons (Filters, Workspaces, Playlists) didn't fit in the row  
**Fix**: Reduced button widths from 110px to 95px and adjusted padding  
**Location**: `suno_layout.py` lines 151, 158, 165  
**Status**: ✅ Fixed

### 4. Playlist Dialog Crash ✅
**Problem**: `WorkspaceBrowser` class didn't accept `title` parameter  
**Fix**: Added `title` parameter to `WorkspaceBrowser.__init__()`  
**Location**: `suno_widgets.py` line 686  
**Status**: ✅ Fixed

### 5. Playlist Download Crash (NameError) ✅
**Problem**: `current_uuid` variable was undefined, causing crash during playlist download  
**Fix**: Changed to properly extract `uuid` from `song_data.get("id")`  
**Location**: `suno_downloader.py` line 436  
**Status**: ✅ Fixed

### 6. Audio Player ✅
**Status**: Verified working in isolation  
**Notes**: Issues were likely related to playlist failures, not the player itself

### 7. Workspace/Playlist Pagination Bug ✅
**Problem**: When searching workspaces or playlists, only the first page was being fetched, so users only saw some of their workspaces/playlists  
**Root Cause**: `fetch_workspaces()` and `fetch_playlists()` only fetched page 1 without pagination  
**Location**: `suno_downloader.py` lines 607-647  
**Fix**: Implemented pagination loops in both functions that:
- Start at page 1 and increment
- Accumulate all items from all pages
- Stop when a page returns empty results or 404
**Status**: ✅ Fixed

### 8. Focus/Grab Issue After Popup Dialogs ✅
**Problem**: After closing popup dialogs (Get Token, Filters, Workspace Browser), users couldn't click anything in the main window. Had to click another window and back to regain control.  
**Root Cause**: Dialogs using `grab_set()` weren't properly releasing the grab or returning focus to the parent window when closed  
**Location**: 
- `suno_widgets.py` - `FilterPopup` and `WorkspaceBrowser` classes
- `suno_layout.py` - `create_token_dialog()` function  
**Fix**: Added proper cleanup methods that:
- Call `grab_release()` before destroying dialogs
- Call `parent.focus_set()` to return focus to main window
- Handle both programmatic close (buttons) and window close (X button) via `WM_DELETE_WINDOW` protocol
**Status**: ✅ Fixed

## Current State

- ✅ App launches successfully
- ✅ Playlist browsing dialog opens and shows playlists
- ✅ 404 fallback logic implemented for legacy playlist support
- ✅ All UI elements fit properly
- ⏳ Ready for testing playlist downloads

## Architecture Overview

### File Structure
```
SunoSync/
├── main.py              # Main application entry point
├── suno_downloader.py    # Download logic and API interaction
├── suno_utils.py         # Utility functions (metadata, file handling)
├── suno_widgets.py       # Custom Tkinter widgets
├── suno_layout.py        # Layout builders and dialogs
├── library_tab.py        # Library browsing interface
├── player_widget.py      # Audio player component (VLC)
├── downloader_tab.py     # Download management interface
├── theme_manager.py      # Theme management
└── config_manager.py     # Configuration management
```

### Key Components

#### Download System
- **Rate Limiting**: Configurable delay between downloads
- **Retry Logic**: Automatic retries on network errors
- **WAV Support**: Handles asynchronous WAV conversion (up to 120s timeout)
- **Metadata Embedding**: ID3 tags, album art, lyrics
- **Smart Resume**: UUID-based duplicate detection

#### API Endpoints
- **Songs**: `/api/gen/me?page={page}`
- **Playlists**: `/api/playlist/me?page=1&show_trashed=false&show_sharelist=false`
- **Playlist Details**: `/api/playlist/{id}/` (with 404 fallback to `/api/project/{id}`)
- **WAV Conversion**: `/api/gen/{id}/convert_wav/`
- **WAV Status**: `https://studio-api.prod.suno.com/api/gen/{clip_id}/wav_file/`

#### Library System
- **Metadata Cache**: Caches file metadata to speed up scanning
- **Tag System**: Supports keep/star/trash tags
- **Search & Filter**: Real-time search with tag filtering
- **Sorting**: Multiple column sorting support

#### Audio Player
- **VLC Integration**: Uses python-vlc for playback
- **Playlist Support**: Can play from library or download queue
- **Seek & Volume**: Full playback controls

## Testing Checklist

### Playlist Functionality
- [ ] Test playlist browsing dialog
- [ ] Test playlist selection
- [ ] Test playlist download (full playlist)
- [ ] Test 404 fallback for legacy playlists
- [ ] Verify playlist_clips parsing

### Download System
- [ ] Test regular song downloads
- [ ] Test WAV downloads
- [ ] Test rate limiting
- [ ] Test duplicate detection
- [ ] Test metadata embedding

### Library System
- [ ] Test library refresh
- [ ] Test search functionality
- [ ] Test tag filtering
- [ ] Test sorting
- [ ] Test context menu actions

### Audio Player
- [ ] Test playback from library
- [ ] Test playback from queue
- [ ] Test seek functionality
- [ ] Test volume control
- [ ] Test play/pause/stop

## Known Issues

None currently documented.

## Code Cleanup (Latest Session)

### Debug Code Removal ✅
- Removed all `print("DEBUG: ...")` statements from:
  - `suno_downloader.py` (9 instances)
  - `suno_widgets.py` (4 instances)
  - `downloader_tab.py` (4 instances)
  - `main.py` (1 instance)
  - `player_widget.py` (2 instances)
  - `suno_utils.py` (2 instances)

### Test/Debug Files Removed ✅
- `debug_startup.py` - Debug startup script
- `debug_lyrics.py` - Lyrics debugging script
- `reproduce_issue.py` - Issue reproduction script
- `test_vlc_import.py` - VLC import test
- `test_sanitization.py` - Filename sanitization test

### Code Quality Improvements ✅
- Cleaned up debug comments (e.g., "ULTIMATE WORKSPACE PARSING & DEBUGGING LOGIC" → "WORKSPACE PARSING LOGIC")
- Improved error handling consistency
- Removed unnecessary print statements
- Verified no linter errors

## Next Steps

1. **End-to-End Testing**: Test playlist download functionality completely
2. **Error Handling**: Consider implementing additional error handling for edge cases
3. **Performance**: Optimize library scanning for large collections
4. **Documentation**: Update user documentation with playlist features

## API Notes

### Playlist API Structure
```json
{
  "playlists": [
    {
      "id": "playlist_id",
      "name": "Playlist Name",
      "playlist_clips": [
        {
          "id": "clip_id",
          "title": "Song Title",
          ...
        }
      ]
    }
  ]
}
```

### 404 Fallback Logic
When `/api/project/{id}` returns 404:
1. Log warning message
2. Replace `/api/project/` with `/api/playlist/` in URL
3. Add trailing slash
4. Retry request immediately

This handles legacy playlists that may still use the project endpoint format.

