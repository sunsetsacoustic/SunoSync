import os
import time
import traceback
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import threading
import re

from suno_utils import RateLimiter, get_downloaded_uuids, embed_metadata, sanitize_filename, get_unique_filename

GEN_API_BASE = "https://studio-api.prod.suno.com"


class Signal:
    """A simple signal implementation for observer pattern."""
    def __init__(self, arg_types=None):
        self._subscribers = []
        self.arg_types = arg_types

    def connect(self, callback):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def emit(self, *args):
        for callback in self._subscribers:
            try:
                callback(*args)
            except Exception:
                traceback.print_exc()


class DownloaderSignals:
    """Container for all signals emitted by SunoDownloader."""
    def __init__(self):
        self.status_changed = Signal(str)       # msg
        self.log_message = Signal((str, str))   # msg, type (info, error, success, downloading)
        self.progress_updated = Signal(int)     # percentage (optional usage)
        self.download_complete = Signal(bool)   # success
        self.error_occurred = Signal(str)       # error message
        self.thumbnail_fetched = Signal((bytes, str)) # data, title/id context
        
        # New Signals for Queue
        self.song_started = Signal((str, str, bytes, dict)) # uuid, title, thumbnail_data, metadata
        self.song_updated = Signal((str, str, int))   # uuid, status, progress
        self.song_finished = Signal((str, bool, str)) # uuid, success, filepath
        self.song_found = Signal((dict,))             # metadata (for preload)


class SunoDownloader:
    STEM_INDICATORS = [
        "(bass)", "(drums)", "(backing vocal)", "(backing vocals)", "(vocals)", "(instrumental)",
        "(woodwinds)", "(brass)", "(fx)", "(synth)", "(strings)", 
        "(percussion)", "(keyboard)", "(guitar)"
    ]

    def __init__(self):
        self.signals = DownloaderSignals()
        self.stop_event = threading.Event()
        self.config = {}
        self.rate_limiter = RateLimiter(0.0)

    def configure(self, token, directory, max_pages, start_page, 
                  organize_by_month, embed_metadata_enabled, prefer_wav, download_delay, 
                  filter_settings=None, scan_only=False, target_songs=None, save_lyrics=True,
                  organize_by_track=False, stems_only=False, smart_resume=False):
        self.config = {
            "token": token,
            "directory": directory,
            "max_pages": max_pages,
            "start_page": start_page,
            "organize_by_month": organize_by_month,
            "embed_metadata": embed_metadata_enabled,
            "save_lyrics": save_lyrics,
            "prefer_wav": prefer_wav,
            "download_delay": max(0.0, float(download_delay)),
            "filter_settings": filter_settings or {},
            "scan_only": scan_only,
            "target_songs": target_songs or [], # List of dicts or UUIDs
            "organize_by_track": organize_by_track,
            "stems_only": stems_only,
            "smart_resume": smart_resume
        }
        self.rate_limiter = RateLimiter(self.config["download_delay"])

    def stop(self):
        self.stop_event.set()

    def is_stopped(self):
        return self.stop_event.is_set()

    def _log(self, message, msg_type="info", thumbnail_data=None):
        """Internal helper to emit log signals."""
        # Also print for debug window capture
        print(f"[{msg_type.upper()}] {message}")
        self.signals.log_message.emit(message, msg_type, thumbnail_data)
        if thumbnail_data:
            self.signals.thumbnail_fetched.emit(thumbnail_data, message)

    def run(self):
        self.stop_event.clear()
        print(f"DEBUG: Starting download/preload run()")
        print(f"DEBUG: Config keys: {list(self.config.keys())}")
        
        token = self.config.get("token", "").strip()
        print(f"DEBUG: Token present: {bool(token)}, length: {len(token) if token else 0}")
        
        # Sanitize token: Remove any non-ASCII characters (e.g. ellipsis from copy-paste)
        if token:
            token = re.sub(r'[^\x00-\x7F]+', '', token)
            
        if not token:
            error_msg = "Token missing; download halted."
            self._log(error_msg, "error")
            print(f"ERROR: {error_msg}")
            self.signals.download_complete.emit(False)
            return

        directory = self.config.get("directory")
        print(f"DEBUG: Download directory: {directory}")
        if not directory:
            error_msg = "Download directory not set."
            self._log(error_msg, "error")
            print(f"ERROR: {error_msg}")
            self.signals.download_complete.emit(False)
            return

        if not os.path.exists(directory):
            os.makedirs(directory)
        
        delay = self.config.get("download_delay", 0)
        if delay > 0:
            self._log(f"Rate limiter enabled: waiting {delay:.2f}s between downloads.", "info")

        scan_only = self.config.get("scan_only", False)
        # Removed: if self.config.get("scan_only"): self._run_scan_only(); return
        # The logic below handles scan_only mode correctly.

        target_songs = self.config.get("target_songs", [])
        filters = self.config.get("filter_settings", {})
        
        headers = {"Authorization": f"Bearer {token}"}
        existing_uuids = get_downloaded_uuids(directory)

        # Mode 1: Download Specific Songs (from Preload)
        if target_songs:
            self.signals.status_changed.emit(f"Downloading {len(target_songs)} selected songs...")
            self._log(f"Starting download of {len(target_songs)} selected songs...", "info")
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for song_data in target_songs:
                    if self.is_stopped(): break
                    futures.append(
                        executor.submit(
                            self.download_single_song,
                            song_data,
                            directory,
                            headers,
                            token,
                            existing_uuids,
                            self.rate_limiter,
                        )
                    )
                
                # Wait for futures but check stop event
                for future in futures:
                    if self.is_stopped():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        future.result()
                    except Exception as e:
                        import traceback
                        error_msg = f"Download error: {str(e)}\n{traceback.format_exc()}"
                        self._log(error_msg, "error")
                        print(error_msg)  # Also print for debug log
            
            if self.is_stopped():
                self.signals.status_changed.emit("Stopped")
            else:
                self.signals.status_changed.emit("Complete")
            self.signals.download_complete.emit(True)
            return

        # Mode 2: Scan/Download from Feed/Workspace
        self.signals.status_changed.emit("Scanning...")
        self._log("Scanning existing files...", "info")
        self._log(f"Found {len(existing_uuids)} existing songs.", "info")

        # --- URL Selection Logic ---
        workspace_id = filters.get("workspace_id")
        is_public = filters.get("is_public", False)
        
        params = []
        # Common params
        if filters.get("liked"): params.append("liked=true")
        if filters.get("trashed"): params.append("trashed=true")
        
        if workspace_id:
            # Workspace/Project Endpoint
            # User correction: Use /api/project/{id} (no /clips, no trailing slash before ?)
            if workspace_id == "default":
                # Assuming default project ID is "default"
                base_url = "https://studio-api.prod.suno.com/api/project/default"
            else:
                # Check if it is a playlist or project
                if filters.get("type") == "playlist":
                     # Playlists might not support pagination, so we'll try without page parameter first
                     base_url = f"https://studio-api.prod.suno.com/api/playlist/{workspace_id}/"
                else:
                     base_url = f"https://studio-api.prod.suno.com/api/project/{workspace_id}"
            
            self._log(f"Fetching from {filters.get('type', 'Project')}: {filters.get('workspace_name', workspace_id)}", "info")
        elif is_public:
            # Public Feed (v2)
            base_url = "https://studio-api.prod.suno.com/api/feed/v2"
            params.append("is_public=true")
            self._log("Fetching from Public Feed", "info")
        else:
            # My Library (v1) - Default
            base_url = "https://studio-api.prod.suno.com/api/feed/"
            self._log("Fetching from My Library", "info")
            
        # Append params to base_url
        if params:
            separator = "&" if "?" in base_url else "?"
            base_url += separator + "&".join(params)
        
        # Check if this is a playlist (playlists might not support pagination)
        is_playlist = filters and filters.get("type") == "playlist"
        
        # Ensure URL ends with page= for the loop (unless it's a playlist)
        if not is_playlist:
            separator = "&" if "?" in base_url else "?"
            base_url += f"{separator}page="

        self._log(f"API URL: {base_url}...", "info")

        max_pages = self.config.get("max_pages", 0)
        page_num = self.config.get("start_page", 1)

        success = True
        try:
            self.signals.status_changed.emit("Fetching List...")
            self._log("Fetching song list...", "info")
            
            # Build UUID cache from existing files for duplicate detection
            self._log("Building UUID cache from existing files...", "info")
            from suno_utils import build_uuid_cache
            uuid_cache = build_uuid_cache(directory)
            self._log(f"Found {len(uuid_cache)} existing songs in cache.", "info")
            
            consecutive_skipped_pages = 0
            # Adaptive threshold: scale with library size
            # For small libraries (< 100 songs): 2 pages
            # For medium libraries (100-1000 songs): 5 pages  
            # For large libraries (1000-5000 songs): 10 pages
            # For very large libraries (> 5000 songs): 20 pages
            library_size = len(uuid_cache)
            if library_size < 100:
                smart_resume_threshold = 2
            elif library_size < 1000:
                smart_resume_threshold = 5
            elif library_size < 5000:
                smart_resume_threshold = 10
            else:
                smart_resume_threshold = 20
            
            # Track if we've found ANY new songs yet (to avoid stopping on initial already-downloaded pages)
            found_new_songs = False
            
            if self.config.get("smart_resume"):
                self._log(f"Smart Resume: Will stop after {smart_resume_threshold} consecutive pages with no new songs (library size: {library_size} songs).", "info")
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                while not self.is_stopped():
                    if max_pages > 0 and page_num > max_pages:
                        self._log(f"Reached max pages limit ({max_pages}). Stopping.", "info")
                        break

                    self._log(f"Page {page_num}...", "info")
                    # Retry logic for fetching page
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # For playlists, don't append page number
                            if is_playlist:
                                url = base_url
                            else:
                                url = f"{base_url}{page_num}"
                            # Increased timeout to 30s and added retry loop
                            r = requests.get(url, headers=headers, timeout=30)
                            
                            # 404 Fallback Logic: Project -> Playlist
                            if r.status_code == 404:
                                if "/api/project/" in base_url:
                                    self._log("Project endpoint 404. Switching to Playlist endpoint...", "warning")
                                    # Regex replace /api/project/ID -> /api/playlist/ID/
                                    base_url = re.sub(r"/api/project/([^?&]+)", r"/api/playlist/\1/", base_url)
                                    continue # Retry immediately with new URL
                                else:
                                    self._log("Error: Resource not found (404).", "error")
                                    success = False
                                    break

                            if r.status_code == 401:
                                self._log("Error: Token expired.", "error")
                                self.signals.error_occurred.emit("Token expired. Please get a new token.")
                                success = False
                                break # Break retry loop, outer loop will also break due to success=False
                            r.raise_for_status()
                            data = r.json()
                            
                            # Debug: Log response structure for playlists
                            if is_playlist:
                                print(f"\n=== PLAYLIST API DEBUG ===")
                                print(f"URL: {url}")
                                print(f"Response Status: {r.status_code}")
                                print(f"Response Type: {type(data)}")
                                if isinstance(data, dict):
                                    print(f"Response Keys: {list(data.keys())}")
                                    # Check for various possible keys
                                    for key in ["playlist_clips", "clips", "items", "songs", "tracks", "playlist"]:
                                        if key in data:
                                            items = data[key]
                                            if isinstance(items, list):
                                                print(f"Found '{key}' with {len(items)} items")
                                                if len(items) > 0:
                                                    print(f"First item keys: {list(items[0].keys()) if isinstance(items[0], dict) else 'Not a dict'}")
                                            elif isinstance(items, dict):
                                                print(f"Found '{key}' as dict with keys: {list(items.keys())}")
                                elif isinstance(data, list):
                                    print(f"Response is a list with {len(data)} items")
                                    if len(data) > 0:
                                        print(f"First item type: {type(data[0])}")
                                        if isinstance(data[0], dict):
                                            print(f"First item keys: {list(data[0].keys())}")
                                print(f"Full Response (first 1000 chars): {str(data)[:1000]}")
                                print(f"=== END PLAYLIST DEBUG ===\n")
                                
                                self._log(f"Playlist API Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}", "info")
                            
                            # If successful, break the retry loop
                            break 
                        except Exception as exc:
                            if attempt < max_retries - 1:
                                self._log(f"Connection error on page {page_num} (Attempt {attempt+1}/{max_retries}): {exc}. Retrying...", "warning")
                                time.sleep(2)
                                continue
                            else:
                                self._log(f"Request failed after {max_retries} attempts: {exc}", "error")
                                self.signals.error_occurred.emit(f"Network error on page {page_num}: {exc}")
                                success = False
                                break # Break retry loop
                    
                    if not success:
                        break # Break page loop

                    # Handle different API response structures and robustly unwrap clips
                    # 1. Project/Workspace: {"project_clips": [{"clip": {...}}, ...]}
                    # 2. Main Library: [{"id": ...}, ...] or {"clips": [...]}
                    
                    # --- WORKSPACE PARSING LOGIC ---
                    
                    # 1. Identify the list source
                    raw_data = data
                    raw_items = []
                    
                    if isinstance(raw_data, dict):
                        # Try various possible keys for playlist/workspace data
                        if "project_clips" in raw_data:
                            raw_items = raw_data["project_clips"]
                        elif "playlist_clips" in raw_data:
                            raw_items = raw_data["playlist_clips"]
                        elif "clips" in raw_data:
                            raw_items = raw_data["clips"]
                        elif "items" in raw_data:
                            raw_items = raw_data["items"]
                        elif "songs" in raw_data:
                            raw_items = raw_data["songs"]
                        elif "tracks" in raw_data:
                            raw_items = raw_data["tracks"]
                        elif "playlist" in raw_data and isinstance(raw_data["playlist"], dict):
                            # Nested playlist structure
                            playlist_data = raw_data["playlist"]
                            if "playlist_clips" in playlist_data:
                                raw_items = playlist_data["playlist_clips"]
                            elif "clips" in playlist_data:
                                raw_items = playlist_data["clips"]
                            elif "items" in playlist_data:
                                raw_items = playlist_data["items"]
                    elif isinstance(raw_data, list):
                        # Direct list of items
                        raw_items = raw_data
                    
                    if is_playlist:
                        print(f"Parsed {len(raw_items)} items from playlist response")
                        self._log(f"Parsed {len(raw_items)} items from playlist response", "info")
                        if len(raw_items) == 0:
                            print(f"\n!!! WARNING: No items found in playlist response !!!")
                            print(f"Response type: {type(data)}")
                            if isinstance(data, dict):
                                print(f"Response keys: {list(data.keys())}")
                                # Print full response structure
                                import json as json_module
                                try:
                                    response_str = json_module.dumps(data, indent=2)
                                    print(f"Full Response:\n{response_str}")
                                except Exception as e:
                                    print(f"Could not serialize response: {e}")
                                    print(f"Response repr: {repr(data)[:1000]}")
                            print(f"!!! END WARNING !!!\n")
                            
                            self._log(f"WARNING: No items found in playlist response. Response type: {type(data)}, Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}", "warning")

                    filtered_clips = []

                    # 2. Setup Filter Flags from UI
                    filter_liked_only = filters.get("liked", False)
                    filter_hide_stems = filters.get("hide_gen_stems", False)
                    filter_exclude_trash = not filters.get("trashed", False)
                    filter_hide_disliked = filters.get("hide_disliked", False)
                    filter_public_only = filters.get("is_public", False)
                    filter_hide_studio = filters.get("hide_studio_clips", False)
                    filter_type = filters.get("type", "all")
                    search_text = filters.get("search_text", "").strip().lower()

                    # Override: If Stems Only is active, disable Hide Stems
                    if self.config.get("stems_only"):
                        filter_hide_stems = False

                    for index, item in enumerate(raw_items):
                        # A. UNWRAP STRATEGY
                        if isinstance(item, dict) and "clip" in item:
                            song_data = item["clip"]
                        else:
                            song_data = item

                        if not song_data:
                            continue

                        # B. EXTRACT VARIABLES
                        title = song_data.get("title", "") or "Unknown Title"
                        
                        # Robust Liked Check
                        is_liked_bool = song_data.get("is_liked", False)
                        reaction = song_data.get("reaction", {}) 
                        if reaction is None: reaction = {} 
                        reaction_type = reaction.get("reaction_type", "")
                        vote = song_data.get("vote", "") or song_data.get("metadata", {}).get("vote", "")
                        
                        # It is liked if Boolean is True OR Reaction is 'L' OR Vote is 'up'
                        is_liked = is_liked_bool or (reaction_type == "L") or (vote == "up")

                        # Extract metadata for filters
                        metadata = song_data.get("metadata", {}) or {}
                        if metadata is None: metadata = {}
                        clip_type = metadata.get("type", "")

                        is_stem = self._is_stem(song_data)

                        # Trash Check
                        is_trashed = song_data.get("is_trashed", False)
                        
                        # Public Check
                        is_public = song_data.get("is_public", False)
                        
                        # Audio URL
                        audio_url = song_data.get("audio_url")

                        # D. APPLY FILTERS
                        
                        # 0. Audio URL (Critical)
                        if not audio_url and not scan_only:
                            continue

                        # 1. Trash Filter
                        if filter_exclude_trash and is_trashed:
                            continue

                        # 2. Stem Filter
                        if filter_hide_stems and is_stem:
                            continue

                        # 2b. Stems Only Filter
                        if self.config.get("stems_only") and not is_stem:
                            continue

                        # 3. Liked Filter
                        if filter_liked_only:
                            if not is_liked:
                                continue
                        
                        # 4. Hide Disliked
                        if filter_hide_disliked and (vote == "down" or reaction_type == "D"):
                            continue

                        # 5. Public Only
                        if filter_public_only and not is_public:
                            continue
                            
                        # 6. Hide Studio
                        if filter_hide_studio and clip_type == "studio_clip":
                            continue
                            
                        # 7. Type Filter
                        if filter_type == "uploads" and clip_type != "upload":
                            continue
                            
                        # 8. Search Text
                        if search_text:
                            tags = metadata.get("tags", "") or ""
                            prompt = metadata.get("prompt", "") or ""
                            searchable_content = f"{title_lower} {tags.lower()} {prompt.lower()}"
                            if search_text not in searchable_content:
                                continue

                        # Extract UUID
                        uuid = song_data.get("id")

                        # 9. Duplicate Check (Metadata-Based)
                        if uuid and uuid in uuid_cache:
                            self._log(f"Skipping {title} (UUID found in cache)", "info")
                            continue

                        # E. SUCCESS
                        filtered_clips.append(song_data)


                    if not filtered_clips:
                        self._log(f"Page {page_num}: All songs filtered out or skipped.", "info")
                    
                    # Track if we found new songs on this page
                    if filtered_clips:
                        found_new_songs = True
                        consecutive_skipped_pages = 0  # Reset counter when we find new songs
                    else:
                        # Only count skipped pages if we've already found some new songs
                        # This prevents stopping on initial pages of already-downloaded content
                        if found_new_songs:
                            consecutive_skipped_pages += 1
                        # If we haven't found any new songs yet, don't count skipped pages
                        # This allows scanning through already-downloaded pages at the start
                         
                    # Smart Resume: Only stop if we've found new songs before, then hit threshold
                    # This ensures we scan past initial already-downloaded pages
                    if self.config.get("smart_resume") and found_new_songs and consecutive_skipped_pages >= smart_resume_threshold:
                        self._log(f"Smart Resume: Found new songs earlier, but no new songs in last {smart_resume_threshold} consecutive pages. Stopping scan.", "success")
                        success = True
                        break
                    
                    if scan_only:
                        for clip in filtered_clips:
                            if self.is_stopped(): break
                            self.signals.song_found.emit(clip)
                    else:
                        futures = []
                        for clip in filtered_clips:
                            if self.is_stopped(): break
                            futures.append(
                                executor.submit(
                                    self.download_single_song,
                                    clip,
                                    directory,
                                    headers,
                                    token,
                                    existing_uuids,
                                    self.rate_limiter,
                                )
                            )

                        for future in futures:
                            if self.is_stopped():
                                executor.shutdown(wait=False, cancel_futures=True)
                                break
                            try:
                                future.result()
                            except Exception:
                                pass

                    # For playlists, only fetch once (no pagination)
                    if is_playlist:
                        break
                    
                    # Check if stopped before continuing to next page
                    if self.is_stopped():
                        break
                    
                    page_num += 1
                    time.sleep(1)
        except Exception as exc:
            tb = traceback.format_exc()
            self._log(f"Critical Error: {exc}\n{tb}", "error")
            self.signals.error_occurred.emit(f"Critical Error: {exc}")
            success = False

        if self.is_stopped():
            self.signals.status_changed.emit("Stopped")
        elif success:
            self.signals.status_changed.emit("Complete")
        else:
            self.signals.status_changed.emit("Error")
            
        self.signals.download_complete.emit(success)

    def fetch_workspaces(self, token):
        """Fetch list of workspaces (projects) using the correct endpoint."""
        headers = {"Authorization": f"Bearer {token}"}
        
        # Endpoint provided by user: 
        # https://studio-api.prod.suno.com/api/project/me?page=1&sort=created_at&show_trashed=false
        
        url = f"{GEN_API_BASE}/api/project/me?page=1&sort=created_at&show_trashed=false"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # User confirmed structure: {"projects": [...]}
                projects = data.get("projects", [])
                return projects
            else:
                self._log(f"Failed to fetch projects: {r.status_code} {r.text}", "error")
        except Exception as e:
            self._log(f"Error fetching projects: {e}", "error")
            
        return []

    def fetch_playlists(self, token):
        """Fetch list of playlists."""
        headers = {"Authorization": f"Bearer {token}"}
        # Endpoint: /api/playlist/me?page=1&show_trashed=false&show_sharelist=false
        url = f"{GEN_API_BASE}/api/playlist/me?page=1&show_trashed=false&show_sharelist=false"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Structure: {"playlists": [...]}
                return data.get("playlists", [])
            else:
                self._log(f"Failed to fetch playlists: {r.status_code} {r.text}", "error")
        except Exception as e:
            self._log(f"Error fetching playlists: {e}", "error")
            
        return []

    def download_single_song(self, clip, directory, headers, token, existing_uuids, rate_limiter):
        if self.is_stopped():
            return

        uuid = clip.get("id")
        if uuid in existing_uuids:
            self._log(f"Skipping: {clip.get('title') or uuid} (already downloaded)", "info")
            return

        title = clip.get("title") or uuid
        image_url = clip.get("image_url")
        display_name = clip.get("display_name")
        metadata = clip.get("metadata", {})
        prompt = metadata.get("prompt", "")
        
        # --- REFETCH STRATEGY ---
        # If prompt is missing (common in V5/Covers list view), fetch full details
        if not prompt:
            clip_id = clip.get("id")
            if clip_id:
                try:
                    detail_url = f"https://studio-api.prod.suno.com/api/clip/{clip_id}"
                    # Use the same headers (auth) as the main request
                    r_refetch = requests.get(detail_url, headers=headers, timeout=10)
                    if r_refetch.status_code == 200:
                        full_details = r_refetch.json()
                        metadata = full_details.get("metadata", {})
                        prompt = metadata.get("prompt", "")
                        # Update clip metadata so subsequent logic uses it
                        clip["metadata"] = metadata
                except Exception as e:
                    self._log(f"Failed to refetch prompt for {clip_id}: {e}", "warning")
        # ------------------------
        tags = metadata.get("tags", "")
        created_at = clip.get("created_at", "")
        year = created_at[:4] if created_at else None
        lyrics = metadata.get("lyrics") or metadata.get("text") or prompt
        if lyrics:
            self._log(f"Lyrics found ({len(lyrics)} chars). Start: {lyrics[:30]}...", "info")
        else:
            self._log(f"No lyrics found for {title} in metadata", "warning")
        
        thumb_data = self.fetch_thumbnail_bytes(image_url) if image_url else None
        
        # Notify start
        self.signals.song_started.emit(uuid, title, thumb_data, metadata)

        audio_url, file_ext, used_wav = self._resolve_audio_stream(clip, title, headers)
        if not audio_url:
            self._log(f"No usable audio stream for {title}; skipping.", "error")
            self.signals.song_updated.emit(uuid, "Error", 0)
            return

        target_dir = directory
        if self.config.get("organize_by_month") and created_at:
            try:
                month_folder = created_at[:7]
                target_dir = os.path.join(directory, month_folder)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
            except:
                pass

        if self.config.get("organize_by_track") and self._is_stem(clip):
            try:
                # Create a subfolder with the song title (stripped of stem indicators)
                base_title = self._get_base_title(title)
                safe_title = sanitize_filename(base_title)
                target_dir = os.path.join(target_dir, safe_title)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
            except:
                pass

        ext = file_ext or ".mp3"
        fname = sanitize_filename(title) + ext
        out_path = os.path.join(target_dir, fname)
        if os.path.exists(out_path):
            out_path = get_unique_filename(out_path)

        self._log(f"Downloading: {title}", "downloading", thumbnail_data=thumb_data)
        self.signals.song_updated.emit(uuid, "Downloading", 0)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if rate_limiter:
                    rate_limiter.wait()
                with requests.get(audio_url, stream=True, headers=headers, timeout=60) as r_dl:
                    r_dl.raise_for_status()
                    total_size = int(r_dl.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(out_path, "wb") as f:
                        for chunk in r_dl.iter_content(chunk_size=8192):
                            if self.is_stopped():
                                f.close()
                                os.remove(out_path)
                                return
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int(downloaded * 100 / total_size)
                                self.signals.song_updated.emit(uuid, "Downloading", percent)
                break
            except Exception as exc:
                if attempt < max_retries - 1:
                    self._log(f"  Retry {attempt+1}/{max_retries}...", "info")
                    time.sleep(2)
                else:
                    self._log(f"Failed: {title} - {exc}", "error")
                    self.signals.song_updated.emit(uuid, "Error", 0)
                    return

        try:
            if lyrics and self.config.get("save_lyrics", True):
                txt_path = os.path.splitext(out_path)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(lyrics)
            
            # Always embed metadata if enabled, or at least embed lyrics
            if self.config.get("embed_metadata"):
                # Full metadata embedding
                embed_metadata(
                    audio_path=out_path,
                    image_url=image_url,
                    title=title,
                    artist=display_name,
                    genre=tags,
                    year=year,
                    comment=prompt,
                    lyrics=lyrics,
                    uuid=uuid,
                    token=token,
                )
            elif lyrics:
                # Only embed lyrics even if full metadata is disabled
                embed_metadata(
                    audio_path=out_path,
                    lyrics=lyrics,
                    metadata_options={
                        'title': False, 'artist': False, 'genre': False, 'year': False,
                        'comment': False, 'lyrics': True, 'album_art': False, 'uuid': False
                    }
                )
            
            existing_uuids.add(uuid)
            self._log(f"✓ {title}", "success", thumbnail_data=thumb_data)
            self.signals.song_finished.emit(uuid, True, out_path)
        except Exception as exc:
            self._log(f"  Metadata error: {exc}", "error")
            self.signals.song_finished.emit(uuid, True, out_path) # Still success even if metadata fails

    def _is_stem(self, song_data):
        """Check if song is a stem."""
        metadata = song_data.get("metadata", {}) or {}
        if metadata is None: metadata = {}
        clip_type = metadata.get("type", "")
        top_type = song_data.get("type", "")
        title = song_data.get("title", "") or ""
        
        title_lower = title.lower()
        is_stem_title = any(ind in title_lower for ind in self.STEM_INDICATORS)
        
        return (clip_type in ["gen_stem", "stem"] or 
                "stem" in top_type or 
                is_stem_title)

    def _get_base_title(self, title):
        """Strip stem indicators from title to get base song name."""
        clean_title = title
        for ind in self.STEM_INDICATORS:
            pattern = re.escape(ind)
            clean_title = re.sub(pattern, "", clean_title, flags=re.IGNORECASE)
        return clean_title.strip()

    def _resolve_audio_stream(self, clip, title, headers):
        prefer_wav = self.config.get("prefer_wav")
        audio_url = clip.get("audio_url")
        extension = ".mp3"
        used_wav = False
        wav_url = self._find_wav_url(clip)
        if prefer_wav and wav_url:
            audio_url = wav_url
            extension = self._extract_extension_from_url(wav_url, default=".wav")
            used_wav = True
        elif prefer_wav:
            # self._log(f"WAV stream unavailable for '{title}'. Requesting conversion...", "info")
            converted = self._fetch_converted_wav(clip, headers)
            if converted:
                audio_url = converted
                extension = self._extract_extension_from_url(converted, default=".wav")
                used_wav = True
            else:
                self._log(f"Conversion failed or timed out for '{title}'. Falling back to MP3.", "error")

        if not audio_url:
            return None, None, False

        if not used_wav:
            extension = self._extract_extension_from_url(audio_url, default=".mp3")

        return audio_url, extension, used_wav

    def _find_wav_url(self, data):
        if isinstance(data, str):
            val = data.strip()
            lowered = val.lower()
            if lowered.startswith("http") and ".wav" in lowered:
                return val
            return None

        if isinstance(data, dict):
            prioritized = (
                "audio_url_wav",
                "wav_url",
                "wav_audio_url",
                "master_wav_url",
                "preview_wav_url",
            )
            for key in prioritized:
                val = data.get(key)
                if isinstance(val, str) and val.lower().startswith("http") and ".wav" in val.lower():
                    return val
            for value in data.values():
                candidate = self._find_wav_url(value)
                if candidate:
                    return candidate

        if isinstance(data, list):
            for entry in data:
                candidate = self._find_wav_url(entry)
                if candidate:
                    return candidate
        return None

    def _fetch_converted_wav(self, clip, headers):
        clip_id = clip.get("id")
        if not clip_id:
            return None
        convert_url = f"{GEN_API_BASE}/api/gen/{clip_id}/convert_wav/"
        # self._log(f"Requesting WAV conversion for '{clip_id}'...", "info")
        try:
            resp = requests.post(convert_url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            self._log(f"Failed to request WAV conversion: {exc}", "error")
            return None
        return self._wait_for_wav_url(clip_id, headers)

    def _wait_for_wav_url(self, clip_id, headers, timeout=120, interval=2):
        deadline = time.monotonic() + timeout
        detail_url = f"https://studio-api.prod.suno.com/api/gen/{clip_id}/wav_file/"
        while time.monotonic() < deadline and not self.is_stopped():
            try:
                resp = requests.get(detail_url, headers=headers, timeout=15)
                if resp.status_code == 404:
                    time.sleep(interval)
                    continue
                resp.raise_for_status()
                data = resp.json()
                wav_url = self._find_wav_url(data)
                if wav_url:
                    return wav_url
            except requests.HTTPError as http_err:
                status = http_err.response.status_code if http_err.response else "?"
                if status != 404:
                    self._log(f"WAV status check failed ({status}): {http_err}", "info")
            except Exception as exc:
                self._log(f"WAV status check failed: {exc}", "info")
            time.sleep(interval)
        if self.is_stopped():
            self._log("WAV polling aborted.", "info")
        else:
            self._log("WAV conversion timed out.", "error")
        return None

    def _extract_extension_from_url(self, url, default=".mp3"):
        try:
            path = urlparse(url).path
            ext = os.path.splitext(path)[1]
            return ext.lower() if ext else default
        except:
            return default

    def fetch_thumbnail_bytes(self, url, size=40):
        try:
            from io import BytesIO
            from PIL import Image
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        except:
            return None

