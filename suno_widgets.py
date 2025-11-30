import math
import tkinter as tk
from tkinter import ttk, font
from io import BytesIO
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os

from suno_utils import blend_colors, hex_to_rgb, lighten_color


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg_color, fg_color, hover_color=None,
                 font=("Segoe UI", 10), width=200, height=40, border_color=None,
                 corner_radius=8, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent.cget('bg'),
                         highlightthickness=0, borderwidth=0, **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_color = hover_color or bg_color
        self.border_color = border_color
        self.text = text
        self.font = font
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.is_hovered = False
        self.is_pressed = False
        self.is_disabled = False
        
        self.draw()
        self.bind("<Configure>", self.on_configure)
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def draw(self):
        self.delete("all")
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
            
        r = self.corner_radius
        
        # Determine background color
        if self.is_disabled:
            fill_color = "#404040"
            text_color = "#808080"
        elif self.is_pressed:
            fill_color = self._darken_color(self.bg_color, 0.8)
            text_color = self.fg_color
        elif self.is_hovered:
            fill_color = self.hover_color
            text_color = self.fg_color
        else:
            fill_color = self.bg_color
            text_color = self.fg_color

        self._draw_round_rect(0, 0, w, h, r, fill=fill_color, outline=self.border_color)
        self.create_text(w / 2, h / 2, text=self.text, fill=text_color, font=self.font)

    def _draw_round_rect(self, x, y, width, height, radius, fill=None, outline=None):
        # Draw rounded rectangle using arcs and rectangles
        if fill:
            self.create_arc(x, y, x + radius*2, y + radius*2, start=90, extent=90, fill=fill, outline=fill)
            self.create_arc(x + width - radius*2, y, x + width, y + radius*2, start=0, extent=90, fill=fill, outline=fill)
            self.create_arc(x, y + height - radius*2, x + radius*2, y + height, start=180, extent=90, fill=fill, outline=fill)
            self.create_arc(x + width - radius*2, y + height - radius*2, x + width, y + height, start=270, extent=90, fill=fill, outline=fill)
            self.create_rectangle(x + radius, y, x + width - radius, y + height, fill=fill, outline=fill)
            self.create_rectangle(x, y + radius, x + width, y + height - radius, fill=fill, outline=fill)
        
        if outline:
            # Simple outline implementation if needed
            pass

    def _darken_color(self, color, factor):
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            return f"#{r:02x}{g:02x}{b:02x}"
        return color

    def on_click(self, event):
        if self.is_disabled: return
        self.is_pressed = True
        self.draw()
        if self.command:
            self.command()

    def on_release(self, event):
        if self.is_disabled: return
        self.is_pressed = False
        self.draw()

    def on_enter(self, event):
        if self.is_disabled: return
        self.is_hovered = True
        self.draw()

    def on_leave(self, event):
        if self.is_disabled: return
        self.is_hovered = False
        self.is_pressed = False
        self.draw()

    def set_text(self, text):
        self.text = text
        self.draw()

    def config_state(self, state):
        if state == "disabled":
            self.is_disabled = True
        else:
            self.is_disabled = False
        self.draw()

    def on_configure(self, event):
        self.width = event.width
        self.height = event.height
        self.draw()


class RoundedCardFrame(tk.Frame):
    def __init__(self, parent, bg_color, corner_radius=12, padding=6, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), **kwargs)
        self.bg_color = bg_color
        self.corner_radius = corner_radius
        self.padding = padding
        self.canvas = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg_color)
        self.inner_window = self.canvas.create_window((padding, padding), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._redraw)

    def _draw_round_rect(self, x, y, width, height, radius, fill=None):
        if width <= 0 or height <= 0:
            return
        self.canvas.create_arc(x, y, x + radius * 2, y + radius * 2, start=90, extent=90,
                               fill=fill, outline=fill, width=0, tags="card")
        self.canvas.create_arc(x + width - radius * 2, y, x + width, y + radius * 2, start=0, extent=90,
                               fill=fill, outline=fill, width=0, tags="card")
        self.canvas.create_arc(x, y + height - radius * 2, x + radius * 2, y + height, start=180, extent=90,
                               fill=fill, outline=fill, width=0, tags="card")
        self.canvas.create_arc(x + width - radius * 2, y + height - radius * 2, x + width, y + height, start=270,
                               extent=90, fill=fill, outline=fill, width=0, tags="card")
        self.canvas.create_rectangle(x + radius, y, x + width - radius, y + height, fill=fill, outline=fill,
                                     tags="card")
        self.canvas.create_rectangle(x, y + radius, x + width, y + height - radius, fill=fill, outline=fill,
                                     tags="card")

    def _redraw(self, event):
        self.canvas.delete("card")
        width = max(event.width, 0)
        height = max(event.height, 0)
        self._draw_round_rect(0, 0, width, height, self.corner_radius, fill=self.bg_color)
        inner_w = max(width - 2 * self.padding, 0)
        inner_h = max(height - 2 * self.padding, 0)
        self.canvas.coords(self.inner_window, self.padding, self.padding)
        self.canvas.itemconfig(self.inner_window, width=inner_w, height=inner_h)


class CollapsibleCard(RoundedCardFrame):
    def __init__(self, parent, title, bg_color, corner_radius=12, padding=6, collapsed=True, **kwargs):
        super().__init__(parent, bg_color=bg_color, corner_radius=corner_radius, padding=padding, **kwargs)
        self.title = title
        self.collapsed = collapsed
        header = tk.Frame(self.inner, bg=bg_color)
        header.pack(fill="x", pady=(0, 4))
        accent = tk.Frame(header, width=4, bg="#ff00ff")
        accent.pack(side="left", fill="y", padx=(0, 0))
        content = tk.Frame(header, bg=bg_color)
        content.pack(side="left", fill="x", expand=True)
        self.arrow_label = tk.Label(content, text="▶", font=("Segoe UI", 12, "bold"), bg=bg_color, fg="#f8fafc")
        self.arrow_label.pack(side="left")
        self.title_label = tk.Label(content, text=title, font=("Segoe UI", 11, "bold"),
                                    bg=bg_color, fg="#f8fafc")
        self.title_label.pack(side="left", padx=(8, 0))
        
        # Summary chip (right side)
        self.summary_label = tk.Label(content, text="", font=("Segoe UI", 9),
                                      bg=bg_color, fg="#94a3b8")
        self.summary_label.pack(side="right", padx=(8, 0))
        
        # Recursively bind click events to header and all its children
        self._bind_click_events(header)
        
        self._header_bg = bg_color
        self._hover_bg = lighten_color(bg_color, 0.05)
        self.body = tk.Frame(self.inner, bg=bg_color)
        self.body.pack(fill="both", expand=True)
        if collapsed:
            self.body.pack_forget()
        self._update_arrow()
        self.header = header
        self.accent_strip = accent
        self._adjust_size()
    
    def set_summary(self, text):
        """Update the summary chip text displayed on the right side of the header."""
        self.summary_label.config(text=text)

    def _bind_click_events(self, widget):
        widget.bind("<Button-1>", self.toggle)
        widget.bind("<Enter>", self._on_header_enter)
        widget.bind("<Leave>", self._on_header_leave)
        for child in widget.winfo_children():
            self._bind_click_events(child)

    def _on_header_enter(self, event=None):
        self.header.configure(bg=self._hover_bg)
        for child in self.header.winfo_children():
            if child is self.accent_strip:
                continue
            child.configure(bg=self._hover_bg)

    def _on_header_leave(self, event=None):
        self.header.configure(bg=self._header_bg)
        for child in self.header.winfo_children():
            if child is self.accent_strip:
                continue
            child.configure(bg=self._header_bg)

    def set_collapsed(self, collapsed):
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
        if self.collapsed:
            self.body.pack_forget()
        else:
            self.body.pack(fill="both", expand=True)
        self._update_arrow()
        self._adjust_size()

    def toggle(self, event=None):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
        else:
            self.body.pack(fill="both", expand=True)
        self._update_arrow()
        self._adjust_size()

    def _update_arrow(self):
        self.arrow_label.config(text="▼" if not self.collapsed else "▶")

    def _adjust_size(self):
        self.inner.update_idletasks()
        header_height = self.header.winfo_reqheight()
        body_height = self.body.winfo_reqheight() if not self.collapsed else 0
        total_height = header_height + body_height + self.padding * 2
        event = type("E", (), {"width": self.canvas.winfo_width(), "height": max(total_height, 1)})
        self.canvas.config(height=event.height)
        self._redraw(event)


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, bg_color="#0a0a0a", active_color="#8b5cf6", **kwargs):
        super().__init__(parent, width=50, height=24, bg=bg_color, highlightthickness=0, **kwargs)
        self.variable = variable
        self.is_on = variable.get()
        self.off_color = "#2a2a2a"
        self.on_color = active_color
        self.bg_color = bg_color
        self.draw()
        self.bind("<Button-1>", self.toggle)
        self.variable.trace_add("write", lambda *args: self.update_from_var())

    def draw(self):
        self.delete("all")
        bg_color = self.on_color if self.is_on else self.off_color
        # Draw track
        self.create_oval(2, 2, 22, 22, fill=bg_color, outline="")
        self.create_rectangle(12, 2, 38, 22, fill=bg_color, outline="")
        self.create_oval(28, 2, 48, 22, fill=bg_color, outline="")
        # Draw thumb
        x = 28 if self.is_on else 6
        self.create_oval(x, 4, x+16, 20, fill="#ffffff", outline="")

    def toggle(self, event=None):
        self.is_on = not self.is_on
        self.variable.set(self.is_on)
        self.draw()

    def update_from_var(self):
        new_val = self.variable.get()
        if new_val != self.is_on:
            self.is_on = new_val
            self.draw()


class CustomCheckbox(tk.Canvas):
    def __init__(self, parent, variable, text="", bg_color="#1a1a1a", fg_color="#ffffff", 
                 active_color="#8b5cf6", check_color="#ffffff", size=20, font_spec=("Segoe UI", 10), **kwargs):
        super().__init__(parent, bg=bg_color, highlightthickness=0, **kwargs)
        self.variable = variable
        self.text = text
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.active_color = active_color
        self.check_color = check_color
        self.size = size
        self.font = font_spec
        
        self.is_checked = variable.get()
        
        # Calculate dimensions
        try:
            self.font_obj = font.Font(font=font_spec)
            text_width = self.font_obj.measure(text)
            text_height = self.font_obj.metrics("linespace")
        except Exception as e:
            print(f"Font error in CustomCheckbox: {e}")
            text_width = 100
            text_height = 20
        
        total_width = size + 8 + text_width + 4
        total_height = max(size, text_height) + 4
        
        self.configure(width=total_width, height=total_height)
        
        self.bind("<Button-1>", self.toggle)
        self.variable.trace_add("write", lambda *args: self.update_from_var())
        self.draw()

    # ... (rest of CustomCheckbox)

# ...



    def draw(self):
        self.delete("all")
        
        # Draw Box
        box_x, box_y = 2, 2
        box_size = self.size
        
        fill = self.active_color if self.is_checked else self.bg_color
        outline = self.active_color if self.is_checked else "#606060"
        
        self.create_rectangle(box_x, box_y, box_x+box_size, box_y+box_size, 
                              fill=fill, outline=outline, width=1)
        
        # Draw Checkmark
        if self.is_checked:
            # Simple checkmark coordinates relative to box
            cx, cy = box_x + box_size/2, box_y + box_size/2
            self.create_line(cx-4, cy, cx-1, cy+4, cx+5, cy-5, 
                             fill=self.check_color, width=2, capstyle="round")
            
        # Draw Text
        if self.text:
            text_x = box_x + box_size + 8
            text_y = box_y + box_size/2
            self.create_text(text_x, text_y, text=self.text, fill=self.fg_color, 
                             font=self.font, anchor="w")

    def toggle(self, event=None):
        self.is_checked = not self.is_checked
        self.variable.set(self.is_checked)
        self.draw()

    def update_from_var(self):
        new_val = self.variable.get()
        if new_val != self.is_checked:
            self.is_checked = new_val
            self.draw()


class SongCard(tk.Frame):
    def __init__(self, parent, uuid, title, thumbnail_data=None, metadata=None, bg_color="#1a1a1a", **kwargs):
        print(f"DEBUG: SongCard init for {uuid}")
        super().__init__(parent, bg=bg_color, **kwargs)
        self.uuid = uuid
        self.title = title
        self.metadata = metadata or {}
        self.status = "Waiting"
        self.progress = 0
        self.filepath = None
        
        try:
            # Container for content
            self.inner = tk.Frame(self, bg=bg_color)
            self.inner.pack(fill="both", expand=True, padx=8, pady=6)
            
            # Grid Layout Configuration
            self.inner.columnconfigure(2, weight=1) # Title column expands
            
            # Checkbox (Row 0-1, Col 0)
            self.selected_var = tk.BooleanVar(value=True)
            self.checkbox = CustomCheckbox(self.inner, variable=self.selected_var, 
                                           bg_color=bg_color, active_color="#8b5cf6", check_color="#ffffff", size=18)
            self.checkbox.grid(row=0, column=0, rowspan=2, padx=(0, 12))
            
            # Thumbnail (Row 0-1, Col 1)
            # Fixed size container for thumbnail
            self.thumb_frame = tk.Frame(self.inner, bg="#2d2d2d", width=48, height=48)
            self.thumb_frame.pack_propagate(False) # Force size
            self.thumb_frame.grid(row=0, column=1, rowspan=2, padx=(0, 12))
            
            self.thumb_label = tk.Label(self.thumb_frame, bg="#2d2d2d")
            self.thumb_label.pack(fill="both", expand=True)
            
            if thumbnail_data:
                self.set_thumbnail(thumbnail_data)
            else:
                # Placeholder
                self.thumb_label.config(text="♫", fg="#505050", font=("Segoe UI", 16))
        except Exception as e:
            print(f"Error in SongCard init: {e}")
            # Don't raise, just log, to prevent crash
            pass
            
        # Title (Row 0, Col 2)
        # Truncate title if too long
        display_title = title if len(title) < 40 else title[:37] + "..."
        self.title_label = tk.Label(self.inner, text=display_title, font=("Segoe UI", 10, "bold"),
                                    bg=bg_color, fg="#f1f5f9", anchor="w")
        self.title_label.grid(row=0, column=2, sticky="ew", pady=(0, 2))
        
        # Tags/Genre (Row 1, Col 2)
        tags = self.metadata.get("tags", "")
        if not tags:
            tags = "Unknown Genre"
        # Truncate tags
        display_tags = tags if len(tags) < 50 else tags[:47] + "..."
        
        self.sub_label = tk.Label(self.inner, text=display_tags, font=("Segoe UI", 9),
                                  bg=bg_color, fg="#94a3b8", anchor="w")
        self.sub_label.grid(row=1, column=2, sticky="ew", pady=(0, 0))
        
        # Status (Row 0, Col 3)
        self.status_label = tk.Label(self.inner, text="Waiting", font=("Segoe UI", 9),
                                     bg=bg_color, fg="#64748b", anchor="e")
        self.status_label.grid(row=0, column=3, padx=8, sticky="e")
        
        # Progress Bar (Row 1, Col 3)
        self.progress_bar = ttk.Progressbar(self.inner, length=80, mode="determinate")
        # self.progress_bar.grid(row=1, column=3, padx=8, sticky="e") # Only show when downloading
        
        # Action Button (Row 0-1, Col 4)
        # Play icon for "Open in Default Player"
        self.action_btn = tk.Label(self.inner, text="▶", font=("Segoe UI", 14),
                                   bg=bg_color, fg="#10b981", cursor="hand2")
        self.action_btn.bind("<Button-1>", self.on_action)
        self.action_btn.grid_forget() # Hidden initially
        
    def set_thumbnail(self, data):
        try:
            image = Image.open(BytesIO(data))
            # Resize to 48x48
            image = image.resize((48, 48), Image.Resampling.LANCZOS)
            self.thumb_img = ImageTk.PhotoImage(image)
            self.thumb_label.config(image=self.thumb_img, text="")
        except Exception as e:
            print(f"Error setting thumbnail: {e}")

    def set_status(self, status, progress=None):
        self.status = status
        self.status_label.config(text=status)
        
        if status == "Downloading" and progress is not None:
            self.progress_bar.grid(row=1, column=3, padx=8, sticky="e")
            self.progress_bar['value'] = progress
        elif status == "Complete":
            self.progress_bar.grid_forget()
            self.status_label.config(fg="#10b981") # Green
            self.action_btn.grid(row=0, column=4, rowspan=2, padx=8)
        elif status == "Error":
            self.progress_bar.grid_forget()
            self.status_label.config(fg="#ef4444") # Red
        else:
            self.progress_bar.grid_forget()
            self.action_btn.grid_forget()

    def set_filepath(self, path):
        self.filepath = path

    def on_action(self, event=None):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(self.filepath)
            except Exception as e:
                print(f"Error opening file: {e}")

    def is_selected(self):
        return self.selected_var.get()
class DownloadQueuePane(tk.Frame):
    def __init__(self, parent, bg_color, theme=None, **kwargs):
        super().__init__(parent, bg=bg_color, **kwargs)
        self.bg_color = bg_color
        self.theme = theme or {}
        self.cards = {} # uuid -> SongCard
        
        # Empty State Widget
        self.empty_state = EmptyStateWidget(self, self.theme)
        self.empty_state.pack(fill="both", expand=True)
        
        # Scrollable Canvas (initially hidden)
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=bg_color)
        
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Don't pack canvas initially - empty state is shown
        
        self.scroll_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
    
    def _update_empty_state(self):
        """Show empty state if no cards, otherwise show queue."""
        if len(self.cards) == 0:
            self.canvas.pack_forget()
            self.scrollbar.pack_forget()
            self.empty_state.pack(fill="both", expand=True)
        else:
            self.empty_state.pack_forget()
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas.find_withtag("all")[0], width=event.width)

    def add_song(self, uuid, title, thumbnail_data=None, metadata=None):
        print(f"DEBUG: DownloadQueuePane.add_song called for {uuid}")
        if uuid in self.cards:
            print(f"DEBUG: Song {uuid} already in cards")
            return
            
        try:
            # Use alternating colors or same color
            bg = self.bg_color
            card = SongCard(self.scroll_frame, uuid, title, thumbnail_data, metadata=metadata, bg_color=bg)
            card.pack(fill="x", pady=0, padx=0)
            self.cards[uuid] = card
            self._update_empty_state()
            self.canvas.yview_moveto(1.0) # Auto-scroll to bottom
            print(f"DEBUG: SongCard added successfully for {uuid}")
        except Exception as e:
            print(f"DEBUG: Error creating SongCard: {e}")
            import traceback
            traceback.print_exc()

    def update_song(self, uuid, status=None, progress=None, filepath=None):
        if uuid in self.cards:
            card = self.cards[uuid]
            if status:
                card.set_status(status, progress)
            if filepath:
                card.set_filepath(filepath)
    
    def update_thumbnail(self, uuid, thumbnail_data):
        if uuid in self.cards:
            self.cards[uuid].set_thumbnail(thumbnail_data)

    def clear(self):
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self.cards.clear()
        self._update_empty_state()
    
    def get_selected_uuids(self):
        return [uuid for uuid, card in self.cards.items() if card.is_selected()]


class FilterPopup(tk.Toplevel):
    def __init__(self, parent, current_filters, on_apply, active_workspace_name=None, bg_color="#1a1a1a", fg_color="#ffffff", accent_color="#8b5cf6"):
        super().__init__(parent)
        self.title("Filters")
        self.geometry("300x550")
        self.configure(bg=bg_color)
        self.transient(parent)
        self.grab_set()
        
        self.on_apply = on_apply
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.accent_color = accent_color
        self.active_workspace_name = active_workspace_name
        self.clear_workspace_flag = False
        
        # Header
        header = tk.Frame(self, bg=bg_color)
        header.pack(fill="x", padx=16, pady=16)
        tk.Label(header, text="Filters", font=("Segoe UI", 14, "bold"), bg=bg_color, fg=fg_color).pack(side="left")
        
        # Content
        content = tk.Frame(self, bg=bg_color)
        content.pack(fill="both", expand=True, padx=16)
        
        self.vars = {}
        
        # Section 0: Workspace (if active)
        if self.active_workspace_name:
            self._add_section_header(content, "Active Workspace")
            ws_frame = tk.Frame(content, bg=bg_color)
            ws_frame.pack(fill="x", pady=4)
            
            tk.Label(ws_frame, text=f"📂 {self.active_workspace_name}", font=("Segoe UI", 10),
                     bg=bg_color, fg=accent_color).pack(side="left")
            
            clear_btn = tk.Label(ws_frame, text="✖ Clear", font=("Segoe UI", 9, "bold"),
                                 bg=bg_color, fg="#ef4444", cursor="hand2")
            clear_btn.pack(side="right")
            clear_btn.bind("<Button-1>", self._clear_workspace)
            self.ws_label = clear_btn # Keep ref to update if clicked

        
        # Section 1: Toggles
        self._add_section_header(content, "Status")
        self._add_checkbox(content, "Liked", "liked", current_filters.get("liked", False))
        self._add_checkbox(content, "Hide Disliked", "hide_disliked", current_filters.get("hide_disliked", True))
        self._add_checkbox(content, "Hide Stems", "hide_gen_stems", current_filters.get("hide_gen_stems", True))
        self._add_checkbox(content, "Stems Only", "stems_only", current_filters.get("stems_only", False))
        self._add_checkbox(content, "Hide Clips", "hide_studio_clips", current_filters.get("hide_studio_clips", True))
        self._add_checkbox(content, "Public", "is_public", current_filters.get("is_public", False))
        self._add_checkbox(content, "Trash", "trashed", current_filters.get("trashed", False))
        
        # Section 2: Types (Radio)
        self._add_section_header(content, "Type")
        self.type_var = tk.StringVar(value=current_filters.get("type", "all"))
        self._add_radio(content, "All", "all", self.type_var)
        self._add_radio(content, "Uploads", "uploads", self.type_var)
        self._add_radio(content, "Full Songs", "full_songs", self.type_var)
        
        # Footer
        footer = tk.Frame(self, bg=bg_color)
        footer.pack(fill="x", padx=16, pady=16, side="bottom")
        
        apply_btn = RoundedButton(footer, "Save Filters", self._apply,
                                 bg_color=accent_color, fg_color="white",
                                 hover_color=lighten_color(accent_color, 0.1),
                                 width=268, height=40, corner_radius=8)
        apply_btn.pack()

    def _add_section_header(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), 
                 bg=self.bg_color, fg="#808080").pack(anchor="w", pady=(12, 8))

    def _add_checkbox(self, parent, text, key, initial_value):
        var = tk.BooleanVar(value=initial_value)
        self.vars[key] = var
        
        frame = tk.Frame(parent, bg=self.bg_color)
        frame.pack(fill="x", pady=4)
        
        cb = CustomCheckbox(frame, variable=var, text=text,
                            bg_color=self.bg_color, fg_color=self.fg_color,
                            active_color=self.accent_color, check_color="#ffffff", size=18)
        cb.pack(side="left", fill="x", expand=True)

    def _add_radio(self, parent, text, value, variable):
        frame = tk.Frame(parent, bg=self.bg_color)
        frame.pack(fill="x", pady=4)
        
        rb = tk.Radiobutton(frame, text=text, value=value, variable=variable,
                            bg=self.bg_color, fg=self.fg_color, selectcolor=self.bg_color,
                            activebackground=self.bg_color, activeforeground=self.fg_color,
                            font=("Segoe UI", 10), anchor="w", padx=0, pady=0)
        rb.pack(side="left", fill="x", expand=True)

    def _clear_workspace(self, event):
        self.clear_workspace_flag = True
        self.ws_label.config(text="✓ Cleared", fg="#10b981")

    def _apply(self):
        result = {key: var.get() for key, var in self.vars.items()}
        result["type"] = self.type_var.get()
        if self.clear_workspace_flag:
            result["clear_workspace"] = True
        self.on_apply(result)
        self.destroy()


class WorkspaceBrowser(tk.Toplevel):
    def __init__(self, parent, workspaces, on_select, bg_color="#1a1a1a", fg_color="#ffffff", accent_color="#8b5cf6"):
        super().__init__(parent)
        self.title("Select Workspace")
        self.geometry("400x500")
        self.configure(bg=bg_color)
        self.transient(parent)
        self.grab_set()
        
        self.on_select = on_select
        self.bg_color = bg_color
        self.fg_color = fg_color
        
        # Header
        header = tk.Frame(self, bg=bg_color)
        header.pack(fill="x", padx=16, pady=16)
        tk.Label(header, text="Workspaces", font=("Segoe UI", 14, "bold"), bg=bg_color, fg=fg_color).pack(side="left")
        
        # Scrollable List
        canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=bg_color)
        
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0))
        scrollbar.pack(side="right", fill="y")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas.find_withtag("all")[0], width=e.width))
        
        for ws in workspaces:
            self._create_item(scroll_frame, ws)

    def _create_item(self, parent, ws):
        # ws = {id, name, created_at, updated_at, num_tracks}
        frame = tk.Frame(parent, bg=self.bg_color)
        frame.pack(fill="x", pady=4)
        
        # Hover effect
        def on_enter(e): frame.config(bg="#2a2a2a")
        def on_leave(e): frame.config(bg=self.bg_color)
        def on_click(e):
            self.on_select(ws)
            self.destroy()
            
        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)
        frame.bind("<Button-1>", on_click)
        
        # Icon/Image Placeholder
        icon = tk.Label(frame, text="📁", font=("Segoe UI", 16), bg=self.bg_color, fg=self.fg_color)
        icon.pack(side="left", padx=(8, 12), pady=8)
        icon.bind("<Button-1>", on_click)
        
        # Text Info
        info = tk.Frame(frame, bg=self.bg_color)
        info.pack(side="left", fill="x", expand=True)
        info.bind("<Button-1>", on_click)
        
        title = tk.Label(info, text=ws.get("name", "Untitled"), font=("Segoe UI", 10, "bold"), 
                         bg=self.bg_color, fg=self.fg_color, anchor="w")
        title.pack(fill="x")
        title.bind("<Button-1>", on_click)
        
        meta = tk.Label(info, text=f"{ws.get('clip_count', ws.get('num_tracks', 0))} Songs • {ws.get('updated_at', '')[:10]}", 
                        font=("Segoe UI", 9), bg=self.bg_color, fg="#808080", anchor="w")
        meta.pack(fill="x")
        meta.bind("<Button-1>", on_click)


class NeonProgressBar(tk.Canvas):
    def __init__(self, parent, height=16, colors=("#8A2BE2", "#EC4899"), bg="#101010", **kwargs):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.height = height
        self.colors = colors
        self.offset = 0
        self.running = False
        self._job = None
        self.text = ""
        self.bind("<Configure>", lambda e: self._draw())

    def set_text(self, text):
        self.text = text
        self._draw()

    def start(self, interval=20):
        if self.running:
            return
        self.running = True
        self._animate(interval)

    def stop(self):
        self.running = False
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.offset = 0
        self._draw()

    def _animate(self, interval):
        if not self.running:
            return
        width = max(1, self.winfo_width())
        self.offset = (self.offset + 4) % width
        self._draw()
        self._job = self.after(interval, lambda: self._animate(interval))

    def _draw(self):
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        
        # Draw background
        self.create_rectangle(0, 0, width, height, fill=self["bg"], outline="")
        
        if self.running:
            # Draw gradient bar
            # Simplified gradient simulation for performance
            bar_width = width // 3
            x1 = self.offset
            x2 = x1 + bar_width
            
            # Wrap around
            if x2 > width:
                # Part 1
                self.create_rectangle(x1, 0, width, height, fill=self.colors[0], outline="")
                # Part 2
                self.create_rectangle(0, 0, x2 - width, height, fill=self.colors[0], outline="")
            else:
                self.create_rectangle(x1, 0, x2, height, fill=self.colors[0], outline="")
                
        # Draw Text Overlay
        if self.text:
            self.create_text(width/2, height/2, text=self.text, fill="#ffffff", font=("Segoe UI", 9, "bold"))


class EmptyStateWidget(tk.Frame):
    """Empty state placeholder for the download queue."""
    def __init__(self, parent, theme, **kwargs):
        super().__init__(parent, bg=theme.get("panel_bg", "#1e293b"), **kwargs)
        self.theme = theme
        
        # Container for centered content
        container = tk.Frame(self, bg=self.cget("bg"))
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icon (music note using Unicode)
        icon_label = tk.Label(
            container,
            text="♪",
            font=("Segoe UI", 64),
            fg=theme.get("text_secondary", "#64748b"),
            bg=self.cget("bg")
        )
        icon_label.pack(pady=(0, 16))
        
        # Message
        message_label = tk.Label(
            container,
            text="Ready to Sync",
            font=("Segoe UI", 14, "bold"),
            fg=theme.get("text_secondary", "#64748b"),
            bg=self.cget("bg")
        )
        message_label.pack()
        
        # Subtitle
        subtitle_label = tk.Label(
            container,
            text="Click 'Preload List' or 'Start Download' to begin",
            font=("Segoe UI", 10),
            fg=theme.get("text_tertiary", "#475569"),
            bg=self.cget("bg")
        )
        subtitle_label.pack(pady=(8, 0))
