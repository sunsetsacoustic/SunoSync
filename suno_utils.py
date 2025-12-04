import os
import re
import time
import threading
import requests
import math
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TCON, COMM, TDRC, TYER, USLT, TXXX, error
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import platform
import subprocess


def open_file(path):
    """Open file or folder with default system application."""
    try:
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.call(('open', path))
        else:  # Linux
            subprocess.call(('xdg-open', path))
    except Exception as e:
        print(f"Error opening file: {e}")


def get_uuid_from_file(filepath):
    """
    Extract SUNO_UUID from audio file metadata.
    Returns None if UUID not found or file cannot be read.
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".wav":
            audio = WAVE(filepath)
        elif ext == ".mp3":
            audio = MP3(filepath, ID3=ID3)
        else:
            return None
        
        if not hasattr(audio, 'tags') or audio.tags is None:
            return None
        
        # Look for SUNO_UUID in TXXX tags
        for key in audio.tags.keys():
            if key.startswith("TXXX:"):
                tag = audio.tags[key]
                if hasattr(tag, 'desc') and tag.desc == "SUNO_UUID":
                    return str(tag.text[0]) if tag.text else None
        
        return None
    except Exception:
        return None


def build_uuid_cache(directory):
    """
    Scan directory recursively and build a set of all UUIDs found in audio files.
    Returns a set of UUID strings.
    """
    uuid_cache = set()
    if not os.path.exists(directory):
        return uuid_cache
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(('.mp3', '.wav')):
                filepath = os.path.join(root, filename)
                uuid = get_uuid_from_file(filepath)
                if uuid:
                    uuid_cache.add(uuid)
    
    return uuid_cache


def read_song_metadata(filepath):
    """
    Reads metadata from MP3/WAV file for library display.
    
    Returns: {
        'title': str,
        'artist': str,
        'duration': int (seconds),
        'date': str,
        'filepath': str,
        'filesize': int (bytes)
    }
    """
    result = {
        'title': os.path.basename(filepath),
        'artist': 'Unknown Artist',
        'duration': 0,
        'date': '',
        'filepath': filepath,
        'filesize': 0,
        'lyrics': ''
    }
    
    try:
        # Get file stats
        stat = os.stat(filepath)
        result['filesize'] = stat.st_size
        result['date'] = time.strftime('%Y-%m-%d', time.localtime(stat.st_mtime))
        
        # Read audio metadata
        ext = os.path.splitext(filepath)[1].lower()
        audio = None
        
        if ext == '.wav':
            audio = WAVE(filepath)
        elif ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
        
        if audio:
            # Duration
            if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                result['duration'] = int(audio.info.length)
            
            # Tags
            if hasattr(audio, 'tags') and audio.tags:
                # Title
                if 'TIT2' in audio.tags:
                    result['title'] = str(audio.tags['TIT2'].text[0])
                
                # Artist  
                if 'TPE1' in audio.tags:
                    result['artist'] = str(audio.tags['TPE1'].text[0])
                
                # Lyrics (USLT) - check all USLT frames and use the first non-empty one
                for key in audio.tags.keys():
                    if key.startswith('USLT'):
                        lyrics_text = str(audio.tags[key].text)
                        if lyrics_text and lyrics_text.strip():
                            result['lyrics'] = lyrics_text
                            break
                
                # Fallback to filename if no title tag
                if result['title'] == os.path.basename(filepath) and 'TIT2' not in audio.tags:
                    # Try to parse filename (remove extension and clean up)
                    name = os.path.splitext(os.path.basename(filepath))[0]
                    result['title'] = name.replace('_', ' ')
        
        # If no lyrics in metadata, check for .txt file
        if not result['lyrics'] or result['lyrics'].strip() == '':
            txt_path = os.path.splitext(filepath)[0] + ".txt"
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        result['lyrics'] = f.read()
                except Exception:
                    pass  # Silently fail if .txt file can't be read
        
        # Get UUID
        result['id'] = get_uuid_from_file(filepath)
    
    except Exception as e:
        # On any error, fallback to filename
        pass
    
    return result


def save_lyrics_to_file(filepath, lyrics):
    """Update lyrics in the audio file."""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        audio = None
        
        if ext == '.wav':
            audio = WAVE(filepath)
            if audio.tags is None:
                audio.add_tags()
        elif ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
        
        if audio:
            # Remove existing USLT frames
            to_delete = [key for key in audio.tags.keys() if key.startswith('USLT')]
            for key in to_delete:
                del audio.tags[key]
            
            # Add new USLT frame
            # encoding=3 is UTF-8, desc='' is standard for main lyrics
            audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
            
            if ext == '.mp3':
                # v2.3 is most compatible with Windows/Players
                audio.save(v2_version=3)
            else:
                audio.save()
                
            return True, "Saved successfully"
            
    except Exception as e:
        print(f"Error saving lyrics to {filepath}: {e}")
        return False, str(e)
    return False, "Unknown error or invalid file type"


FILENAME_BAD_CHARS = r'[<>:"/\\|?*\x00-\x1F]'


def hex_to_rgb(color):
    color = color.lstrip("#")
    if len(color) == 6:
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    elif len(color) == 8:
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_colors(color_a, color_b, ratio):
    a = hex_to_rgb(color_a)
    b = hex_to_rgb(color_b)
    ratio = max(0.0, min(1.0, ratio))
    return rgb_to_hex(tuple(int(max(0, min(255, a[i] + (b[i] - a[i]) * ratio))) for i in range(3)))


def lighten_color(color, amount=0.1):
    rgb = hex_to_rgb(color)
    return rgb_to_hex(tuple(max(0, min(255, int(c + (255 - c) * amount))) for c in rgb))


def sanitize_filename(name, maxlen=200):
    safe = re.sub(FILENAME_BAD_CHARS, "_", name)
    safe = safe.strip(" .")
    return safe[:maxlen] if len(safe) > maxlen else safe


def get_unique_filename(filename):
    if not os.path.exists(filename):
        return filename
    name, extn = os.path.splitext(filename)
    counter = 2
    while True:
        new_filename = f"{name} v{counter}{extn}"
        if not os.path.exists(new_filename):
            return new_filename
        counter += 1


def get_downloaded_uuids(directory):
    uuids = set()
    if not os.path.exists(directory):
        return uuids

    for root, dirs, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith(".mp3"):
                try:
                    audio = ID3(os.path.join(root, fname))
                    for frame in audio.getall("TXXX"):
                        if frame.desc == "SUNO_UUID":
                            uuids.add(frame.text[0])
                except:
                    pass
    return uuids


class RateLimiter:
    """Simple token-style rate limiter that enforces a minimum delay between calls."""

    def __init__(self, min_interval=0.0):
        self.min_interval = max(0.0, float(min_interval))
        self._lock = threading.Lock()
        self._next_allowed = time.monotonic()

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next_allowed = now + self.min_interval


def embed_metadata(
    audio_path,
    image_url=None,
    title=None,
    artist=None,
    album=None,
    genre=None,
    year=None,
    comment=None,
    lyrics=None,
    uuid=None,
    token=None,
    timeout=15,
    metadata_options=None,
):
    """
    Embed metadata into MP3 or WAV files.
    
    metadata_options: dict with keys 'title', 'artist', 'genre', 'year', 
                     'comment', 'lyrics', 'album_art', 'uuid' (all bool)
    """
    if metadata_options is None:
        # Default: include all metadata
        metadata_options = {
            'title': True, 'artist': True, 'genre': True, 'year': True,
            'comment': True, 'lyrics': True, 'album_art': True, 'uuid': True
        }
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        # Determine file type
        ext = os.path.splitext(audio_path)[1].lower()
        is_wav = ext == ".wav"
        
        # Load audio file
        if is_wav:
            audio = WAVE(audio_path)
        else:
            audio = MP3(audio_path, ID3=ID3)
        
        # Add ID3 tags if they don't exist
        if not hasattr(audio, 'tags') or audio.tags is None:
            audio.add_tags()
        
        # Get image if needed
        image_bytes = None
        mime = "image/jpeg"
        if metadata_options.get('album_art', True) and image_url:
            r = requests.get(image_url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                image_bytes = r.content
                mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]

        # Embed metadata fields based on options
        if metadata_options.get('title', True) and title:
            audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        if metadata_options.get('artist', True) and artist:
            audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        if metadata_options.get('genre', True) and genre:
            audio.tags["TCON"] = TCON(encoding=3, text=genre)
        if metadata_options.get('year', True) and year:
            audio.tags["TDRC"] = TDRC(encoding=3, text=str(year))
            audio.tags["TYER"] = TYER(encoding=3, text=str(year))
        if metadata_options.get('comment', True) and comment:
            audio.tags["COMM"] = COMM(encoding=3, lang="eng", desc="Description", text=comment)
        
        # 1. Extract Lyrics
        # Suno stores lyrics in 'prompt'. We check 'lyrics' and 'text' just in case.
        # Note: 'lyrics' variable already contains the extracted text from suno_downloader.py
        lyrics_text = lyrics
        

        if lyrics_text and metadata_options.get('lyrics', True):
            try:
                # Remove existing USLT frames first
                to_delete = [key for key in audio.tags.keys() if key.startswith('USLT')]
                for key in to_delete:
                    del audio.tags[key]
                
                # Add lyrics to both MP3 and WAV files
                # For WAV files, ensure tags exist
                if isinstance(audio, WAVE):
                    if audio.tags is None:
                        audio.add_tags()
                
                # Add USLT frame with lyrics
                audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics_text))
                print(f"Lyrics successfully embedded for {os.path.basename(audio_path)}")
                
            except Exception as e:
                print(f"Failed to embed lyrics: {e}")
                import traceback
                traceback.print_exc()

        if metadata_options.get('uuid', True) and uuid:
            audio.tags.add(TXXX(encoding=3, desc="SUNO_UUID", text=uuid))

        if image_bytes:
            for key in list(audio.tags.keys()):
                if key.startswith("APIC"):
                    del audio.tags[key]
            audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_bytes))

        # Save: MP3 uses v2_version, WAV doesn't support it
        if is_wav:
            audio.save()
        else:
            audio.save(v2_version=3)
    except Exception as e:
        print(f"Metadata error: {e}")


# --- GUI UTILS ---
def truncate_path(path, max_length=40):
    """Truncate path with middle ellipsis."""
    if len(path) <= max_length:
        return path
    folder_name = os.path.basename(path)
    parent = os.path.dirname(path)
    if len(folder_name) > max_length - 10:
        return f"...{folder_name[-max_length+3:]}"
    return f"{parent[:15]}...{os.sep}{folder_name}"


def safe_messagebox(func, *args, suppress_sound=False, **kwargs):
    """
    Wrapper for messagebox functions that can suppress Windows notification sounds.
    
    Args:
        func: messagebox function (showinfo, showwarning, showerror, askyesno, etc.)
        *args: Arguments to pass to the messagebox function
        suppress_sound: If True, suppress Windows notification sound
        **kwargs: Keyword arguments to pass to the messagebox function
    
    Returns:
        The result of the messagebox function
    """
    if suppress_sound:
        # Suppress Windows notification sound
        try:
            import tkinter as tk
            root = tk._default_root
            if root:
                # Save current bell volume
                original_volume = root.tk.call('set', 'bell_volume', root.tk.call('set', 'bell_volume'))
                # Disable bell sound by setting volume to 0
                try:
                    root.tk.call('set', 'bell_volume', '0')
                    result = func(*args, **kwargs)
                finally:
                    # Restore bell volume
                    try:
                        root.tk.call('set', 'bell_volume', original_volume)
                    except:
                        pass
                return result
        except:
            # Fallback: try disabling bell completely
            try:
                import tkinter as tk
                root = tk._default_root
                if root:
                    root.option_add('*bellOff', '1')
                    try:
                        result = func(*args, **kwargs)
                    finally:
                        root.option_clear('*bellOff')
                    return result
            except:
                pass
    
    # If suppress_sound is False or error occurred, use normal messagebox
    return func(*args, **kwargs)


def create_tooltip(widget, text):
    """Create a tooltip for a widget."""
    def on_enter(event):
        # Destroy existing tooltip if any
        if hasattr(widget, 'tooltip'):
            try:
                widget.tooltip.destroy()
            except:
                pass
            del widget.tooltip
            
        import tkinter as tk
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = tk.Label(tooltip, text=text, bg="#2d2d2d", fg="#e0e0e0",
                       font=("Segoe UI", 9), padx=8, pady=4, relief="solid", borderwidth=1)
        label.pack()
        widget.tooltip = tooltip
    
    def on_leave(event):
        if hasattr(widget, 'tooltip'):
            try:
                widget.tooltip.destroy()
            except:
                pass
            del widget.tooltip
    
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
    widget.bind("<ButtonPress>", on_leave)

