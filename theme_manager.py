from PIL import ImageFont
import platform
import os


class ThemeManager:
    def __init__(self):
        # Modern Dark Mode Palette
        self.bg_dark = "#121212"  # Main background
        self.card_bg = "#1E1E1E"  # Card/Panel background
        self.bg_card = self.card_bg  # Alias
        self.bg_input = "#2C2C2C"  # Input fields
        self.fg_primary = "#E0E0E0"  # Main text
        self.fg_secondary = "#A0A0A0"  # Secondary text

        self.accent_purple = "#8B5CF6"  # Primary Action (Matte Purple)
        self.accent_pink = "#EC4899"  # Secondary Accent
        self.accent_red = "#EF4444"  # Destructive Action

        self.border_subtle = "#333333"  # Subtle borders
        self.card_border = "#333333"  # Card borders

        # Platform-specific font defaults
        system = platform.system()
        if system == "Windows":
            self.section_font = ("Segoe UI", 11, "bold")
            self.title_font = ("Segoe UI", 24, "bold")
            self.mono_font = ("Consolas", 10)
        elif system == "Darwin":  # macOS
            self.section_font = ("SF Pro Display", 11, "bold")
            self.title_font = ("SF Pro Display", 24, "bold")
            self.mono_font = ("Monaco", 10)
        else:  # Linux
            self.section_font = ("DejaVu Sans", 11, "bold")
            self.title_font = ("DejaVu Sans", 24, "bold")
            self.mono_font = ("DejaVu Sans Mono", 10)

    def load_title_font(self, size):
        """Load font with cross-platform fallbacks for Linux compatibility."""
        system = platform.system()

        if system == "Windows":
            # Try Windows fonts
            try:
                return ImageFont.truetype("arial.ttf", size)
            except OSError:
                try:
                    return ImageFont.truetype("seguiemj.ttf", size)
                except OSError:
                    pass

        elif system == "Darwin":  # macOS
            try:
                return ImageFont.truetype("Arial.ttf", size)
            except OSError:
                pass

        else:  # Linux - Try multiple common font paths
            # Common Linux font locations
            font_paths = [
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/local/share/fonts/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
                "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except:
                        continue

            # Last resort: try to use default font (Pillow will use its built-in default)
            try:
                return ImageFont.load_default(size)
            except:
                # Final fallback - this should work on any system
                return ImageFont.load_default()

        # Ultimate fallback
        return ImageFont.load_default()
