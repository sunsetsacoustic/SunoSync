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
                  organize_by_track=False, stems_only=False):
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
            "stems_only": stems_only
        }
        self.rate_limiter = RateLimiter(self.config["download_delay"])

    def stop(self):
        self.stop_event.set()

    def is_stopped(self):
        return self.stop_event.is_set()

    def _log(self, message, msg_type="info", thumbnail_data=None):
        """Internal helper to emit log signals."""
        self.signals.log_message.emit(message, msg_type, thumbnail_data)
        if thumbnail_data:
            self.signals.thumbnail_fetched.emit(thumbnail_data, message)

    def run(self):
        print("DEBUG: SunoDownloader.run started")
        self.stop_event.clear()
        token = self.config.get("token", "").strip()
        if not token:
            self._log("Token missing; download halted.", "error")
            self.signals.download_complete.emit(False)
            return

        directory = self.config.get("directory")
        if not directory:
            self._log("Download directory not set.", "error")
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
                    except Exception:
                        pass
            
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
                base_url = f"https://studio-api.prod.suno.com/api/project/{workspace_id}"
            
            self._log(f"Fetching from Project: {filters.get('workspace_name', workspace_id)}", "info")
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
        
        # Ensure URL ends with page= for the loop
        separator = "&" if "?" in base_url else "?"
        base_url += f"{separator}page="

        self._log(f"API URL: {base_url}...", "info") # Log truncated URL for debug

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
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                while not self.is_stopped():
                    if max_pages > 0 and page_num > max_pages:
                        self._log(f"Reached max pages limit ({max_pages}). Stopping.", "info")
                        break

                    self._log(f"Page {page_num}...", "info")
                    try:
                        url = f"{base_url}{page_num}"
                        r = requests.get(url, headers=headers, timeout=15)
                        if r.status_code == 401:
                            self._log("Error: Token expired.", "error")
                            self.signals.error_occurred.emit("Token expired. Please get a new token.")
                            success = False
                            break
                        r.raise_for_status()
                        data = r.json()
                        
                        # DEBUG: Inspect raw API response for prompt
                        try:
                            if isinstance(data, dict):
                                clips = data.get("clips") or data.get("project_clips")
                                if clips and len(clips) > 0:
                                    first_clip = clips[0]
                                    if "clip" in first_clip: first_clip = first_clip["clip"]
                                    meta = first_clip.get("metadata", {})
                                    print(f"DEBUG: Raw API Metadata Keys (First Item): {list(meta.keys())}")
                                    print(f"DEBUG: Raw API Prompt (First Item): {bool(meta.get('prompt'))}")
                        except Exception as e:
                            print(f"DEBUG: Failed to inspect raw API: {e}")
                    except Exception as exc:
                        self._log(f"Request failed: {exc}", "error")
                        self.signals.error_occurred.emit(f"Network error on page {page_num}: {exc}")
                        success = False
                        break

                    # Handle different API response structures and robustly unwrap clips
                    # 1. Project/Workspace: {"project_clips": [{"clip": {...}}, ...]}
                    # 2. Main Library: [{"id": ...}, ...] or {"clips": [...]}
                    
                    # --- ULTIMATE WORKSPACE PARSING & DEBUGGING LOGIC ---
                    
                    # 1. Identify the list source
                    raw_data = data
                    if isinstance(raw_data, dict) and "project_clips" in raw_data:
                        raw_items = raw_data["project_clips"]
                    elif isinstance(raw_data, list):
                        raw_items = raw_data
                    elif isinstance(raw_data, dict) and "clips" in raw_data:
                        raw_items = raw_data["clips"]
                    else:
                        raw_items = []

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

                    print(f"--- STARTING FILTER DEBUG ---")
                    print(f"Filters Active: Liked={filter_liked_only}, NoStems={filter_hide_stems}, NoTrash={filter_exclude_trash}")

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

                        is_stem = self._is_stem(song_data)

                        # Trash Check
                        is_trashed = song_data.get("is_trashed", False)
                        
                        # Public Check
                        is_public = song_data.get("is_public", False)
                        
                        # Audio URL
                        audio_url = song_data.get("audio_url")

                        # C. DEBUG PRINT
                        # print(f"Song: {title[:15]}... | Liked: {is_liked} | Stem: {is_stem} | Trash: {is_trashed}")

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

                        # 9. Duplicate Check (Metadata-Based)
                        current_uuid = song_data.get("id")
                        if current_uuid and current_uuid in uuid_cache:
                            self._log(f"Skipping {title} (UUID found in cache)", "info")
                            continue

                        # E. SUCCESS
                        filtered_clips.append(song_data)

                    print(f"--- FILTERING DONE. Found {len(filtered_clips)} songs. ---")

                    if not filtered_clips:
                        self._log(f"Page {page_num}: All songs filtered out.", "info")
                    
                    if scan_only:
                        for clip in filtered_clips:
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
                print(f"DEBUG: Prompt missing for {clip_id}. Refetching full details...")
                try:
                    detail_url = f"https://studio-api.prod.suno.com/api/clip/{clip_id}"
                    # Use the same headers (auth) as the main request
                    r_refetch = requests.get(detail_url, headers=headers, timeout=10)
                    if r_refetch.status_code == 200:
                        full_details = r_refetch.json()
                        metadata = full_details.get("metadata", {})
                        prompt = metadata.get("prompt", "")
                        print(f"DEBUG: Refetch successful. Prompt found: {bool(prompt)} (Len: {len(prompt)})")
                        # Update clip metadata so subsequent logic uses it
                        clip["metadata"] = metadata
                except Exception as e:
                    print(f"DEBUG: Refetch failed: {e}")
        else:
             print(f"DEBUG: Prompt found in initial data: {bool(prompt)} (Len: {len(prompt)})")
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
            if self.config.get("embed_metadata"):
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

