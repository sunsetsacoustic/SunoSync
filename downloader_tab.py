import os
import sys
import threading
import tkinter as tk
import queue
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

from suno_utils import blend_colors, truncate_path, create_tooltip
from suno_widgets import (
    RoundedButton,
    RoundedCardFrame,
    DownloadQueuePane,
    NeonProgressBar,
    ToggleSwitch,
    FilterPopup,
    WorkspaceBrowser
)
from suno_downloader import SunoDownloader
from suno_layout import (
    create_auth_card, 
    create_settings_card, 
    create_scraping_card, 
    create_action_area, 
    create_token_dialog
)
from config_manager import ConfigManager
from theme_manager import ThemeManager


if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

user_data_dir = os.path.join(base_path, "Suno_Browser_Profile")
CONFIG_FILE = os.path.join(base_path, "config.json")

# --- DOWNLOADER TAB (Refactored for tab view) ---
class DownloaderTab(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.theme_manager = ThemeManager()
        
        # Map theme properties to self for compatibility with layout helpers
        self._apply_theme()
        
        self.downloader = SunoDownloader()
        self.gui_queue = queue.Queue()
        self.preloaded_songs = {}  # uuid -> song_data
        self.is_preloaded = False
        self.filter_settings = {}
        
        self.create_widgets()
        self.load_config_into_ui()
        self.update_path_display()  # Initial path truncation
        
        # Start GUI processor
        self._process_gui_queue()
    
    def _apply_theme(self):
        t = self.theme_manager
        self.bg_dark = t.bg_dark
        self.card_bg = t.card_bg
        self.bg_card = t.bg_card
        self.card_border = t.card_border
        self.bg_input = t.bg_input
        self.fg_primary = t.fg_primary
        self.fg_secondary = t.fg_secondary
        self.accent_purple = t.accent_purple
        self.accent_pink = t.accent_pink
        self.accent_red = t.accent_red
        self.border_subtle = t.border_subtle
        self.section_font = t.section_font
        self.title_font = t.title_font
        
        self.configure(bg=self.bg_dark)
        self.title_image = self._create_title_image("SunoSync")

    def _create_title_image(self, text):
        font = self.theme_manager.load_title_font(46)
        try:
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width, text_height = font.getsize(text)
        padding = 12
        gradient_height = text_height + padding
        gradient = Image.new("RGBA", (text_width, gradient_height))
        draw = ImageDraw.Draw(gradient)
        for y in range(gradient_height):
            ratio = y / max(1, gradient_height - 1)
            color = blend_colors(self.accent_purple, self.accent_pink, ratio)
            draw.line([(0, y), (text_width, y)], fill=color)
        mask = Image.new("L", (text_width, gradient_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.text((0, 0), text, font=font, fill=255)
        gradient.putalpha(mask)
        return ImageTk.PhotoImage(gradient)

    def update_path_display(self):
        """Update path entry with truncated display"""
        if hasattr(self, 'path_display_var'):
            full_path = self.path_var.get()
            self.path_display_var.set(truncate_path(full_path))
    
    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        create_tooltip(widget, text)

    def create_widgets(self):
        self.log_font_size_var = tk.IntVar(value=12)

        # Main Container (2-Column Grid)
        self.columnconfigure(0, weight=0, minsize=400) # Left Column (Fixed/Min width)
        self.columnconfigure(1, weight=1)              # Right Column (Expands)
        self.rowconfigure(0, weight=1)                 # Full Height

        # --- LEFT COLUMN: Control Panel ---
        left_panel = tk.Frame(self, bg=self.bg_dark, padx=20, pady=20)
        left_panel.grid(row=0, column=0, sticky="nsew")
        
        # Header (Logo + Status)
        header_frame = tk.Frame(left_panel, bg=self.bg_dark)
        header_frame.pack(fill="x", pady=(0, 20))
        
        title_label = tk.Label(header_frame, image=self.title_image, bg=self.bg_dark)
        title_label.pack(side=tk.LEFT)
        title_label.image = self.title_image
        
        # Status Badge
        self.status_frame = tk.Frame(header_frame, bg=self.bg_dark)
        self.status_frame.pack(side=tk.RIGHT, pady=10)
        
        self.status_dot = tk.Canvas(self.status_frame, width=12, height=12, bg=self.bg_dark, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.status_indicator = self.status_dot.create_oval(2, 2, 10, 10, fill="#6b7280", outline="")
        
        self.status_label = tk.Label(self.status_frame, text="Ready", 
                                    font=("Segoe UI", 9, "bold"), bg=self.bg_dark, fg=self.fg_secondary)
        self.status_label.pack(side=tk.LEFT)
        self.status_label.bind("<Button-1>", self._on_status_click)
        self.status_label.bind("<Enter>", self._on_status_hover)
        
        self._status_pulse_job = None
        self._status_pulse_on = False
        self.last_error = None

        # Cards Container
        cards_container = tk.Frame(left_panel, bg=self.bg_dark)
        cards_container.pack(fill="both", expand=True)
        
        # 1. Authorization Card
        self.auth_card = create_auth_card(cards_container, self)
        
        # 2. Settings Card
        self.settings_card = create_settings_card(cards_container, self, base_path)
        
        # 3. Scraping Options Card
        self.scraping_card = create_scraping_card(cards_container, self)
        
        # 4. Action Buttons
        create_action_area(left_panel, self)
        
        # Initial Summary Update
        self.update_accordion_summaries()
        
        # Progress Bar (Bottom of Left Panel)
        progress_container = tk.Frame(left_panel, bg=self.bg_dark, height=6)
        progress_container.pack(fill="x", pady=(15, 0))
        progress_container.pack_propagate(False)
        
        self.progress = NeonProgressBar(progress_container, height=6,
                                        colors=(self.accent_purple, self.accent_pink),
                                        bg=self.bg_dark)
        self.progress.pack(fill="both", expand=True)
        right_panel = tk.Frame(self, bg=self.bg_dark, padx=20, pady=20)
        right_panel.grid(row=0, column=1, sticky="nsew")
        
        queue_frame = RoundedCardFrame(right_panel, bg_color=self.card_bg, corner_radius=12, padding=0)
        queue_frame.pack(fill="both", expand=True)
        
        # Header
        queue_header = tk.Frame(queue_frame.inner, bg=self.card_bg, padx=15, pady=10)
        queue_header.pack(fill="x")
        tk.Label(queue_header, text="DOWNLOAD QUEUE", font=("Segoe UI", 10, "bold"),
                 bg=self.card_bg, fg=self.fg_secondary).pack(side=tk.LEFT)
        
        theme_dict = {
            "panel_bg": self.card_bg,
            "text_secondary": self.fg_secondary,
            "text_tertiary": "#475569"
        }
        self.queue_pane = DownloadQueuePane(queue_frame.inner, bg_color=self.card_bg, theme=theme_dict)
        self.queue_pane.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        
        self.update_status_safe("Ready")

    def create_toggle_option(self, parent, text, variable):
        # Simplified toggle creation for grid layouts
        # Note: 'parent' is expected to be the grid cell frame
        toggle = ToggleSwitch(parent, variable, 
                              bg_color=self.bg_card, active_color=self.accent_purple)
        toggle.pack(side=tk.LEFT, padx=(0, 8))
        
        label = tk.Label(parent, text=text, font=("Segoe UI", 9),
                        bg=self.bg_card, fg=self.fg_primary)
        label.pack(side=tk.LEFT)
        return parent
    
    def validate_page_range(self):
        """Ensure start page doesn't exceed max page"""
        start = self.start_page_var.get()
        max_pages = self.max_pages_var.get()
        
        if max_pages > 0 and start > max_pages:
            self.start_page_var.set(max_pages)

    def on_log_font_size_change(self, *args):
        pass # Removed

    def toggle_token_visibility(self):
        if self.token_entry.cget("show") == "●":
            self.token_entry.config(show="")
        else:
            self.token_entry.config(show="●")

    def update_status_safe(self, text, color=None):
        """Thread-safe status update."""
        self.after(0, lambda: self._update_status(text, color))

    def _update_status(self, text, color=None):
        status_text = text
        status_lower = status_text.lower()
        color_map = {
            "ready": "#10b981",       # Green
            "downloading": "#8B5CF6", # Purple
            "stopped": "#EF4444",     # Red
            "complete": "#10b981",    # Green
            "error": "#EF4444"        # Red
        }
        resolved_color = color_map.get(status_lower, color or "#6b7280")
        self.status_label.config(text=status_text, fg=resolved_color)
        self.status_dot.itemconfig(self.status_indicator, fill=resolved_color)
        if "downloading" in status_lower:
            if self._status_pulse_job is None:
                self._pulse_status()
        else:
            if self._status_pulse_job:
                self.after_cancel(self._status_pulse_job)
                self._status_pulse_job = None
            self._status_pulse_on = False
            self.status_dot.itemconfig(self.status_indicator, fill=resolved_color)

    def _pulse_status(self):
        if self._status_pulse_job:
            self.after_cancel(self._status_pulse_job)
        self._status_pulse_on = not self._status_pulse_on
        base_color = "#8B5CF6"
        highlight = "#A78BFA"
        fill_color = highlight if self._status_pulse_on else base_color
        self.status_dot.itemconfig(self.status_indicator, fill=fill_color)
        self._status_pulse_job = self.after(600, self._pulse_status)

    def open_folder(self):
        folder = self.path_var.get()
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Error", "Folder does not exist yet.")

    def browse_folder(self):
        """Open a dialog to select the download folder."""
        folder = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder:
            self.path_var.set(folder)
            self.update_path_display()
            self.save_config()

    def get_token_logic(self):
        """Open the token acquisition dialog."""
        create_token_dialog(self)

    def stop_download(self):
        """Stop the current download process."""
        if self.downloader:
            self.downloader.stop()
        self.update_status_safe("Stopping...")
        self.start_btn.config_state("disabled")
        self.stop_btn.config_state("disabled")

    def toggle_action_buttons(self, downloading=False):
        """Toggle button states based on download status."""
        if downloading:
            self.start_btn.config_state("disabled")
            self.stop_btn.config_state("normal")
            if hasattr(self, 'preload_btn'):
                self.preload_btn.config_state("disabled")
        else:
            self.start_btn.config_state("normal")
            self.stop_btn.config_state("disabled")
            if hasattr(self, 'preload_btn'):
                self.preload_btn.config_state("normal")

    def on_error_safe(self, message):
        """Thread-safe error handling."""
        self.after(0, lambda: self._show_error(message))

    def _show_error(self, message):
        self.last_error = message
        self.update_status_safe("Error")
        self.toggle_action_buttons(downloading=False)
        self.progress.stop()
        self.progress.set_text("")
        messagebox.showerror("Error", message)

    def _on_status_click(self, event):
        if self.last_error and self.status_label.cget("text") == "Error":
            self._show_error_toast(event)

    def _on_status_hover(self, event):
        if self.last_error and self.status_label.cget("text") == "Error":
            # Optional: could show tooltip on hover too, but toast on click is more persistent
            pass

    def _show_error_toast(self, event):
        """Show a temporary toast message with the error details."""
        toast = tk.Toplevel(self.winfo_toplevel())
        toast.wm_overrideredirect(True)
        toast.configure(bg="#ef4444")
        
        x = event.x_root + 10
        y = event.y_root + 10
        toast.geometry(f"+{x}+{y}")
        
        label = tk.Label(toast, text=self.last_error, bg="#ef4444", fg="white", 
                         font=("Segoe UI", 9), padx=10, pady=6, justify="left")
        label.pack()
        
        # Close on click or after 3 seconds
        toast.bind("<Button-1>", lambda e: toast.destroy())
        self.after(4000, toast.destroy)

    def load_config_into_ui(self):
        c = self.config_manager
        self.token_var.set(c.get("token", ""))
        self.path_var.set(c.get("path", os.path.join(base_path, "Suno_Downloads")))
        self.embed_thumb_var.set(c.get("embed_metadata", True))
        self.organize_var.set(c.get("organize", False))
        self.save_lyrics_var.set(c.get("save_lyrics", True))
        self.download_wav_var.set(c.get("prefer_wav", False))
        self.rate_limit_var.set(c.get("download_delay", 0.5))
        self.max_pages_var.set(c.get("max_pages", 0))
        self.start_page_var.set(c.get("start_page", 0))
        self.track_folder_var.set(c.get("track_folder", False))
        
        # Load filters
        self.filter_settings = c.get("filter_settings", {
            "liked": False,
            "hide_disliked": True,
            "hide_gen_stems": True,
            "hide_studio_clips": True,
            "is_public": False,
            "trashed": False,
            "type": "all"
        })
        self._update_filter_btn_text()
        
        # Bind traces for real-time summary updates
        self.token_var.trace_add("write", self.update_accordion_summaries)
        self.download_wav_var.trace_add("write", self.update_accordion_summaries)
        self.embed_thumb_var.trace_add("write", self.update_accordion_summaries)
        self.organize_var.trace_add("write", self.update_accordion_summaries)
        self.track_folder_var.trace_add("write", self.update_accordion_summaries)

    def update_accordion_summaries(self, *args):
        """Update the summary chips on accordion headers."""
        # 1. Authorization Summary
        token = self.token_var.get().strip()
        if token:
            self.auth_card.set_summary("✓ Token Set")
        else:
            self.auth_card.set_summary("••••")
            
        # 2. Settings Summary
        settings_summary = []
        if self.download_wav_var.get():
            settings_summary.append("WAV")
        else:
            settings_summary.append("MP3")
            
        if self.embed_thumb_var.get():
            settings_summary.append("Meta: ON")
            
        if self.organize_var.get():
            settings_summary.append("Monthly")
            
        if self.track_folder_var.get():
            settings_summary.append("TrackFolder")
            
        if self.filter_settings.get("stems_only"):
            settings_summary.append("StemsOnly")
            
        self.settings_card.set_summary(f"[{' '.join(settings_summary)}]")

    def save_config(self):
        c = self.config_manager
        c.set("token", self.token_var.get())
        c.set("path", self.path_var.get())
        c.set("embed_metadata", self.embed_thumb_var.get())
        c.set("organize", self.organize_var.get())
        c.set("save_lyrics", self.save_lyrics_var.get())
        c.set("download_delay", self.rate_limit_var.get())
        c.set("prefer_wav", self.download_wav_var.get())
        c.set("max_pages", self.max_pages_var.get())
        c.set("start_page", self.start_page_var.get())
        c.set("track_folder", self.track_folder_var.get())
        c.set("filter_settings", self.filter_settings)
        c.save_config()
        
        # Update summaries when config is saved (covers most changes)
        self.update_accordion_summaries()

    def open_filters(self):
        ws_name = self.filter_settings.get("workspace_name")
        FilterPopup(self, self.filter_settings, self.on_filters_applied, active_workspace_name=ws_name,
                    bg_color=self.bg_dark, fg_color=self.fg_primary, accent_color=self.accent_purple)

    def on_filters_applied(self, new_filters):
        if new_filters.pop("clear_workspace", False):
            self.filter_settings["workspace_id"] = None
            self.filter_settings["workspace_name"] = None
            self.filter_settings["type"] = "all" # Reset to all or keep previous? Usually reset.
            if hasattr(self, 'workspace_btn'):
                self.workspace_btn.set_text("Workspaces")
            messagebox.showinfo("Workspace Cleared", "Workspace selection has been cleared.")
        
        self.filter_settings.update(new_filters)
        self._update_filter_btn_text()
        self.save_config()
        self.update_accordion_summaries()

    def _update_filter_btn_text(self):
        if hasattr(self, 'filter_btn'):
            active_count = sum(1 for k, v in self.filter_settings.items() if v is True)
            if self.filter_settings.get("type") != "all":
                active_count += 1
            self.filter_btn.set_text(f"Filters ({active_count})")

    def log_safe(self, message, tag=None, thumbnail_data=None):
        """Thread-safe logging via queue."""
        # For compatibility, we still accept logs but we might not show them all in the queue
        # unless they are relevant. For now, we rely on the specific song signals.
        pass

    def log(self, message, tag=None, thumbnail_data=None):
        """Alias for log_safe for compatibility."""
        self.log_safe(message, tag, thumbnail_data)

    # --- New Signal Handlers ---
    def on_song_started_safe(self, uuid, title, thumb_data, metadata):
        self.gui_queue.put(('add_song', uuid, title, thumb_data, metadata))
        
    def on_song_updated_safe(self, uuid, status, progress):
        self.gui_queue.put(('update_song', uuid, status, progress))
        
    def on_song_finished_safe(self, uuid, success, path):
        self.gui_queue.put(('finish_song', uuid, success, path))

    def on_song_found_safe(self, metadata):
        self.gui_queue.put(('found_song', metadata))

    def _process_gui_queue(self):
        """Process all pending GUI updates."""
        try:
            while True:
                try:
                    item = self.gui_queue.get_nowait()
                except queue.Empty:
                    break
                
                msg_type = item[0]
                
                try:
                    if msg_type == 'add_song':
                        _, uuid, title, thumb, meta = item
                        self.queue_pane.add_song(uuid, title, thumb, metadata=meta)
                    elif msg_type == 'update_song':
                        _, uuid, status, progress = item
                        self.queue_pane.update_song(uuid, status=status, progress=progress)
                    elif msg_type == 'finish_song':
                        _, uuid, success, path = item
                        status = "Complete" if success else "Error"
                        self.queue_pane.update_song(uuid, status=status, filepath=path)
                    elif msg_type == 'found_song':
                        _, meta = item
                        uuid = meta.get("id")
                        title = meta.get("title") or uuid
                        image_url = meta.get("image_url")
                        # We don't have thumbnail bytes here yet, so pass None or fetch?
                        # Passing None will show placeholder.
                        # We can store metadata for later.
                        self.preloaded_songs[uuid] = meta
                        self.queue_pane.add_song(uuid, title, None, metadata=meta)
                        # Trigger thumbnail fetch in background? 
                        # For now, just show placeholder to be fast.
                        if image_url:
                            threading.Thread(target=self._fetch_thumb_bg, args=(uuid, image_url), daemon=True).start()
                except Exception as e:
                    print(f"Error processing GUI message {msg_type}: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"Critical error in GUI queue processor: {e}")
            
        self.after(100, self._process_gui_queue)

    def _fetch_thumb_bg(self, uuid, url):
        data = self.downloader.fetch_thumbnail_bytes(url)
        if data:
            self.after(0, lambda: self.queue_pane.update_thumbnail(uuid, data))

    def open_workspaces(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a Bearer Token first.")
            return
            
        self.update_status_safe("Fetching workspaces...")
        threading.Thread(target=self._fetch_workspaces_thread, args=(token,), daemon=True).start()

    def _fetch_workspaces_thread(self, token):
        workspaces = self.downloader.fetch_workspaces(token)
        self.after(0, lambda: self._show_workspace_browser(workspaces))

    def _show_workspace_browser(self, workspaces):
        self.update_status_safe("Ready")
        if not workspaces:
            messagebox.showinfo("Info", "No workspaces found or failed to fetch.")
            return
        WorkspaceBrowser(self, workspaces, self.on_workspace_selected,
                        bg_color=self.bg_dark, fg_color=self.fg_primary)

    def on_workspace_selected(self, ws):
        # ws is a dict
        ws_id = ws.get("id")
        name = ws.get("name")
        self.filter_settings["workspace_id"] = ws_id
        self.filter_settings["workspace_name"] = name
        self.filter_settings["type"] = "workspace" # Custom type to indicate workspace mode if needed
        self.save_config()
        
        # Update UI to show selected workspace
        if hasattr(self, 'workspace_btn'):
            self.workspace_btn.set_text(f"WS: {name[:10]}...")
        
        messagebox.showinfo("Workspace Selected", f"Selected workspace: {name}\nClick 'Start Download' or 'Preload' to proceed.")

    def preload_songs(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a Bearer Token.")
            return

        self.save_config()
        self.toggle_action_buttons(downloading=True)
        self.update_status_safe("Preloading...")
        self.start_btn.set_text("Scanning...")
        self.progress.start(10)
        self.progress.set_text("Fetching List...")
        
        self.queue_pane.clear()
        self.preloaded_songs.clear()
        self.is_preloaded = True
        
        # Connect signals
        self.downloader.signals.status_changed.connect(self.update_status_safe)
        self.downloader.signals.download_complete.connect(self.on_preload_complete_safe)
        self.downloader.signals.error_occurred.connect(self.on_error_safe)
        self.downloader.signals.song_found.connect(self.on_song_found_safe)
        
        # Configure downloader for SCAN ONLY
        self.downloader.configure(
            token=token,
            directory=self.path_var.get(),
            max_pages=self.max_pages_var.get(),
            start_page=self.start_page_var.get(),
            organize_by_month=self.organize_var.get(),
            embed_metadata_enabled=self.embed_thumb_var.get(),
            save_lyrics=self.save_lyrics_var.get(),
            prefer_wav=self.download_wav_var.get(),
            download_delay=self.rate_limit_var.get(),
            filter_settings=self.filter_settings,
            scan_only=True,
            organize_by_track=self.track_folder_var.get(),
            stems_only=self.filter_settings.get("stems_only")
        )
        
        thread = threading.Thread(target=self.downloader.run, daemon=True)
        thread.start()

    def on_preload_complete_safe(self, success):
        self.after(0, lambda: self.on_preload_complete(success))

    def on_preload_complete(self, success):
        self.toggle_action_buttons(downloading=False)
        self.progress.stop()
        self.progress.set_text("")
        
        if success:
            self.update_status_safe("Preload Complete")
            self.start_btn.set_text("Download Selected")
            messagebox.showinfo("Preload Complete", f"Found {len(self.preloaded_songs)} songs.\nUncheck songs you don't want, then click 'Download Selected'.")
        else:
            self.start_btn.set_text("Start Download")
            self.is_preloaded = False # Reset if failed
            self.update_status_safe("Error")

    def start_download_thread(self):
        print("DEBUG: start_download_thread called")
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a Bearer Token.")
            return

        self.save_config()
        
        target_songs = []
        if self.is_preloaded:
            # Get selected UUIDs
            selected_uuids = self.queue_pane.get_selected_uuids()
            if not selected_uuids:
                messagebox.showwarning("No Selection", "Please select at least one song to download.")
                return
            
            # Filter preloaded_songs
            target_songs = [self.preloaded_songs[uuid] for uuid in selected_uuids if uuid in self.preloaded_songs]
            self.update_status_safe(f"Downloading {len(target_songs)} songs...")
        
        self.toggle_action_buttons(downloading=True)
        self.update_status_safe("Downloading")
        self.start_btn.set_text("Downloading...")
        self.progress.start(10)
        self.progress.set_text("Starting...")
        
        if not self.is_preloaded:
            self.queue_pane.clear()
        
        # Connect signals
        self.downloader.signals.status_changed.connect(self.update_status_safe)
        self.downloader.signals.download_complete.connect(self.on_download_complete_safe)
        self.downloader.signals.error_occurred.connect(self.on_error_safe)
        
        # New Signals
        self.downloader.signals.song_started.connect(self.on_song_started_safe)
        self.downloader.signals.song_updated.connect(self.on_song_updated_safe)
        self.downloader.signals.song_finished.connect(self.on_song_finished_safe)

        # Configure downloader
        self.downloader.configure(
            token=token,
            directory=self.path_var.get(),
            max_pages=self.max_pages_var.get(),
            start_page=self.start_page_var.get(),
            organize_by_month=self.organize_var.get(),
            embed_metadata_enabled=self.embed_thumb_var.get(),
            save_lyrics=self.save_lyrics_var.get(),
            prefer_wav=self.download_wav_var.get(),
            download_delay=self.rate_limit_var.get(),
            filter_settings=self.filter_settings,
            target_songs=target_songs,
            organize_by_track=self.track_folder_var.get(),
            stems_only=self.filter_settings.get("stems_only")
        )
        
        thread = threading.Thread(target=self.downloader.run, daemon=True)
        thread.start()

    def on_download_complete_safe(self, success):
        self.after(0, lambda: self.on_download_complete(success))

    def on_download_complete(self, success):
        self.toggle_action_buttons(downloading=False)
        self.progress.stop()
        self.progress.set_text("")
        self.start_btn.set_text("Start Download")
        self.is_preloaded = False # Reset after download
        
        if success:
            self.update_status_safe("Complete")
            messagebox.showinfo("Success", "Download cycle completed.")
        else:
            if self.downloader.is_stopped():
                self.update_status_safe("Stopped")
            else:
                self.update_status_safe("Error")


