import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import json
import sys
from library_tab import LibraryTab
from player_widget import PlayerWidget
from downloader_tab import DownloaderTab
from config_manager import ConfigManager

sys.setrecursionlimit(5000)  # Workaround for Tkinter recursion issue

if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(base_path, "config.json")
CACHE_FILE = os.path.join(base_path, "library_cache.json")
TAGS_FILE = os.path.join(base_path, "tags.json")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not PyInstaller, use the directory of the script
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


class SunoSyncApp(tk.Tk):
    """Main application with Downloader, Library, and Player."""

    def __init__(self):
        super().__init__()

        self.title("SunoSync")

        # Set Icon
        try:
            import platform

            if platform.system() == "Windows":
                # Windows: use .ico
                icon_path = resource_path("resources/icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            else:
                # Linux/macOS: use .png
                png_path = resource_path("resources/logo.png")
                if os.path.exists(png_path):
                    from PIL import Image, ImageTk

                    icon_img = Image.open(png_path)
                    # Resize to reasonable size for icon
                    icon_img = icon_img.resize((32, 32), Image.Resampling.LANCZOS)
                    icon_photo = ImageTk.PhotoImage(icon_img)
                    self.iconphoto(True, icon_photo)
        except Exception as e:
            # Silently ignore icon errors - they're cosmetic
            pass

        # Load geometry
        self.load_window_state()

        # Theme colors
        self.bg_dark = "#1a1a1a"
        self.configure(bg=self.bg_dark)

        # Ensure minimum window size
        self.minsize(1000, 750)

        # Hide window initially to show splash first
        self.withdraw()

        # Make window borderless (remove title bar)
        self.overrideredirect(True)

        # Add window drag and close functionality
        self._setup_window_drag()

        # Show window after a brief delay to allow initialization
        self.after(100, self._show_window_with_splash)

        try:
            # Main layout using grid for better control
            main_frame = tk.Frame(self, bg=self.bg_dark)
            main_frame.pack(fill="both", expand=True)
            main_frame.grid_rowconfigure(0, weight=1)  # Notebook row expands
            main_frame.grid_rowconfigure(1, weight=0)  # Player row fixed
            main_frame.grid_columnconfigure(0, weight=1)  # Single column

            # Shared Config Manager
            self.config_manager = ConfigManager(CONFIG_FILE)

            # Create tabs
            self.notebook = ttk.Notebook(main_frame)
            self.notebook.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

            # Tab 1: Downloader
            self.downloader = DownloaderTab(
                self.notebook, config_manager=self.config_manager
            )
            self.notebook.add(self.downloader, text="  Downloader  ")

            # Tab 2: Library
            self.library = LibraryTab(
                self.notebook,
                config_manager=self.config_manager,
                cache_file=CACHE_FILE,
                tags_file=TAGS_FILE,
            )
            self.notebook.add(self.library, text="  Library  ")

            # Player widget (bottom, fixed height)
            self.player = PlayerWidget(main_frame)
            self.player.set_tags_file(TAGS_FILE)
            self.player.set_library_tab(
                self.library
            )  # Give player access to library for tagging
            self.library.player_widget = (
                self.player
            )  # Give library access to player for UI updates

            # Use grid to ensure player gets fixed height
            self.player.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
            # Player widget has pack_propagate(False) and height=160 set internally
            self.player.config(height=160)

            # Connect Library to Player
            self.library.bind("<<PlaySong>>", self.on_play_song)
            self.player.bind("<<TagsUpdated>>", lambda e: self.on_tags_updated(e))
            self.player.bind("<<TrackChanged>>", self.on_track_changed)

            # Connect Downloader to Library (refresh on download complete)
            self.downloader.downloader.signals.download_complete.connect(
                self.on_download_complete
            )

            # Style notebook
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TNotebook", background=self.bg_dark, borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background="#2d2d2d",
                foreground="#e0e0e0",
                padding=[20, 10],
                font=("Segoe UI", 10, "bold"),
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#8b5cf6")],
                foreground=[("selected", "white")],
            )

            # Handle close
            self.protocol("WM_DELETE_WINDOW", self.on_close)

        except Exception as e:
            # Show error dialog if initialization fails
            import traceback

            error_msg = (
                f"Failed to initialize application:\n{e}\n\n{traceback.format_exc()}"
            )
            print(error_msg)
            try:
                messagebox.showerror("Initialization Error", error_msg)
            except:
                pass
            raise

    def _show_window_with_splash(self):
        """Show window and then display splash screen."""
        # Show the window
        self.deiconify()
        self.update_idletasks()
        self.lift()
        self.focus_force()

        # Show splash screen after window is visible
        self.after(50, self.show_splash)

    def show_splash(self):
        """Show splash screen as an overlay frame."""
        splash_path = resource_path("resources/splash.png")
        if not os.path.exists(splash_path):
            # If splash doesn't exist, just show the window
            self.update_idletasks()
            self.lift()
            self.focus_force()
            return

        # Create overlay frame that covers the entire window
        splash_frame = tk.Frame(self, bg="black")
        splash_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        splash_frame.lift()  # Ensure it's on top

        try:
            # Load and display the splash image
            pil_img = Image.open(splash_path)
            # Get window size for proper scaling
            self.update_idletasks()
            win_width = self.winfo_width()
            win_height = self.winfo_height()

            # Scale image to fit window while maintaining aspect ratio
            img_width, img_height = pil_img.size
            scale = (
                min(win_width / img_width, win_height / img_height)
                if win_width > 0 and win_height > 0
                else 1.0
            )

            # If window is too small, use a minimum size
            if scale > 1.0 or win_width < 600:
                new_width = max(600, int(img_width * scale))
                new_height = max(400, int(img_height * scale))
                pil_img = pil_img.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )

            img = ImageTk.PhotoImage(pil_img)

            # Center the image
            lbl = tk.Label(splash_frame, image=img, bg="black")
            lbl.image = img  # Keep a reference
            lbl.place(relx=0.5, rely=0.5, anchor="center")

            # Version text in bottom right
            version_label = tk.Label(
                splash_frame,
                text="v2.0",
                bg="black",
                fg="white",
                font=("Segoe UI", 12, "bold"),
            )
            version_label.place(relx=0.95, rely=0.95, anchor="se")

            # Make sure window is visible
            self.update_idletasks()
            self.lift()
            self.focus_force()

        except Exception as e:
            print(f"Splash error: {e}")
            import traceback

            traceback.print_exc()
            splash_frame.destroy()
            # Still show the window even if splash fails
            self.update_idletasks()
            self.lift()
            self.focus_force()
            return

        def end_splash():
            try:
                splash_frame.destroy()
            except:
                pass
            # Ensure main window is visible after splash
            self.update_idletasks()
            self.lift()
            self.focus_force()
            self.check_changelog()

        # Show splash for 2 seconds
        self.after(2000, end_splash)

    def check_changelog(self):
        """Show changelog on first launch of new version."""
        current_version = "2.0"
        last_version = None
        state_file = "window_state.json"
        data = {}

        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                    last_version = data.get("version")
            except:
                pass

        if last_version != current_version:
            # Show Changelog
            messagebox.showinfo(
                "What's New in v2.0",
                "🎉 Welcome to SunoSync v2.0! 🎉\n\n"
                "✨ New Features:\n"
                "• Sleek Borderless Design: Modern, professional windowless interface\n"
                "• Enhanced Debug Log: Built-in debug viewer with save-to-file support\n"
                "• Improved Stop Button: Now properly stops preload and download operations\n"
                "• Better Error Handling: More detailed error messages and logging\n"
                "• Fixed Player Sizing: Audio player now displays at proper height\n\n"
                "🔧 Improvements:\n"
                "• Preload functionality now works reliably\n"
                "• Stop button allows restarting operations\n"
                "• Better splash screen timing\n"
                "• Improved UI layout and spacing\n\n"
                "Enjoy your music!",
            )

            # Save new version
            data["version"] = current_version
            try:
                with open(state_file, "w") as f:
                    json.dump(data, f)
            except:
                pass

    def load_window_state(self):
        try:
            if os.path.exists("window_state.json"):
                with open("window_state.json", "r") as f:
                    data = json.load(f)
                    geometry = data.get("geometry", "1100x750")
                    self.geometry(geometry)
            else:
                self.geometry("1100x750")
                self.center_window()

            # Ensure window is on screen
            self.update_idletasks()
            # Check if window is off-screen and reset if needed
            try:
                x = self.winfo_x()
                y = self.winfo_y()
                width = self.winfo_width()
                height = self.winfo_height()
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                # If window is completely off-screen, center it
                if (
                    x + width < 0
                    or x > screen_width
                    or y + height < 0
                    or y > screen_height
                ):
                    self.geometry("1100x750")
                    self.center_window()
            except:
                # If we can't check position, just center it
                self.geometry("1100x750")
                self.center_window()
        except:
            self.geometry("1100x750")
            self.center_window()

    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_window_drag(self):
        """Setup window dragging and close button for borderless window."""
        # Variables for dragging
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Create a small close button in top-right corner
        close_frame = tk.Frame(self, bg=self.bg_dark, height=30)
        close_frame.pack(fill="x", side="top")

        close_btn = tk.Button(
            close_frame,
            text="✕",
            font=("Segoe UI", 14, "bold"),
            bg=self.bg_dark,
            fg="#ffffff",
            activebackground="#ff4444",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            width=3,
            height=1,
            command=self.on_close,
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=10, pady=5)

        # Bind drag to the close_frame (title bar area)
        close_frame.bind("<Button-1>", self._start_drag)
        close_frame.bind("<B1-Motion>", self._on_drag)

        # Add title text in the title bar
        title_label = tk.Label(
            close_frame,
            text="SunoSync",
            bg=self.bg_dark,
            fg="#ffffff",
            font=("Segoe UI", 10),
        )
        title_label.pack(side="left", padx=15, pady=5)
        title_label.bind("<Button-1>", self._start_drag)
        title_label.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        """Start dragging the window."""
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _on_drag(self, event):
        """Handle window dragging."""
        x = self.winfo_x() + event.x_root - self._drag_start_x
        y = self.winfo_y() + event.y_root - self._drag_start_y
        self.geometry(f"+{x}+{y}")
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def on_close(self):
        try:
            with open("window_state.json", "w") as f:
                json.dump({"geometry": self.geometry()}, f)
        except:
            pass
        self.destroy()

    def on_download_complete(self, success):
        """Refresh library when downloads complete."""
        if success:
            self.library.refresh_library()

    def on_play_song(self, event):
        """Handle play song event from library."""
        # Get playlist and index from library
        if hasattr(self.library, "current_playlist") and hasattr(
            self.library, "current_index"
        ):
            self.player.set_playlist(
                self.library.current_playlist, self.library.current_index
            )

    def on_tags_updated(self, event):
        """Handle tags updated event from player."""
        try:
            # Use after() to ensure we're in the main thread
            if hasattr(self, "library") and self.library:
                # Use a longer delay to ensure any ongoing operations complete
                self.after(200, self._safe_reload_tags)
        except Exception as e:
            print(f"Error in on_tags_updated: {e}")
            import traceback

            traceback.print_exc()

    def _safe_reload_tags(self):
        """Safely reload tags in library."""
        try:
            if (
                hasattr(self, "library")
                and self.library
                and hasattr(self.library, "reload_tags")
            ):
                self.library.reload_tags()
        except Exception as e:
            print(f"Error in _safe_reload_tags: {e}")
            import traceback

            traceback.print_exc()

    def on_track_changed(self, event):
        """Handle track change from player."""
        try:
            if hasattr(self.player, "current_file") and self.player.current_file:
                # Use after() to ensure we're in the main thread and UI is ready
                self.after(50, lambda: self._update_library_selection())
        except Exception as e:
            print(f"Error in on_track_changed: {e}")
            import traceback

            traceback.print_exc()

    def _update_library_selection(self):
        """Update library selection to match currently playing song."""
        try:
            if hasattr(self.player, "current_file") and self.player.current_file:
                # Normalize the filepath before selecting
                filepath = os.path.normpath(self.player.current_file)
                self.library.select_song(filepath)
        except Exception as e:
            print(f"Error in _update_library_selection: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    app = SunoSyncApp()
    app.mainloop()
