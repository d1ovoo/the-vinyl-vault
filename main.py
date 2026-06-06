"""
Spotify Dashboard Widget — Retro Pixel Edition
Pixelated checkered background, CRT-style themes, Courier New font throughout.

Vignette: Gaussian-kernel method (GeeksforGeeks / OpenCV style) applied directly
          to pixel data — no overlay canvas.  Uses numpy; cv2 not required.
          Background sigma_factor=0.38 (tight, heavy dark border).
          Album-art sigma_factor=0.50 (moderate edge darkening).
Bloom:    Soft glow halo composited behind album-art images via PIL.
          bloom_radius=10, bloom_strength=0.80 for a pronounced CRT glow.
Scanlines: Every 2nd row dimmed 22 % (factor 0.78) to simulate phosphor gaps.
"""

import tkinter as tk
import threading
import json
import os
import webbrowser
from io import BytesIO

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageTk
from spotify_auth import SpotifyAuthenticator
from spotify_api import SpotifyAPI


FONT = "Courier New"


class SpotifyWidget:
    """Retro Pixel Spotify Dashboard Widget"""

    PALETTES = {
        "terminal": {
            "name": "Terminal",
            "bg":             "#000000",
            "secondary_bg":   "#111111",
            "tertiary_bg":    "#001400",
            "fg":             "#00FF41",
            "accent":         "#00AA00",
            "text_secondary": "#007A1F",
            "check1":         "#001400",
            "check2":         "#001C00",
        },
        "amber": {
            "name": "Amber CRT",
            "bg":             "#0D0800",
            "secondary_bg":   "#1F1200",
            "tertiary_bg":    "#130A00",
            "fg":             "#FFB000",
            "accent":         "#FF8000",
            "text_secondary": "#AA7000",
            "check1":         "#130A00",
            "check2":         "#1C1000",
        },
        "gameboy": {
            "name": "Game Boy",
            "bg":             "#0F380F",
            "secondary_bg":   "#2D5A1C",
            "tertiary_bg":    "#8BAC0F",
            "fg":             "#0F380F",
            "accent":         "#306230",
            "text_secondary": "#1A3A1A",
            "check1":         "#8BAC0F",
            "check2":         "#9BBC0F",
        },
        "synthwave": {
            "name": "Synthwave",
            "bg":             "#0D0020",
            "secondary_bg":   "#1A003A",
            "tertiary_bg":    "#08000F",
            "fg":             "#FF00FF",
            "accent":         "#00FFFF",
            "text_secondary": "#BB00BB",
            "check1":         "#08000F",
            "check2":         "#0F0018",
        },
    }

    DEMO_ARTISTS = [
        {"name": "The Weeknd",       "genres": "synth-pop, pop",         "popularity": 92, "url": "https://open.spotify.com/artist/1Xyo4u8uIGMw73CxIaXvj"},
        {"name": "Drake",             "genres": "hip-hop, rap",           "popularity": 88, "url": "https://open.spotify.com/artist/7dGJo4pcD2V6oG8kP0tJt"},
        {"name": "Taylor Swift",      "genres": "pop, country",           "popularity": 95, "url": "https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf94"},
        {"name": "Ariana Grande",     "genres": "pop, r&b",               "popularity": 90, "url": "https://open.spotify.com/artist/66CXWjxzNUsdJxJ2JdwvnR"},
        {"name": "Post Malone",       "genres": "trap, hip-hop",          "popularity": 85, "url": "https://open.spotify.com/artist/PostMalone"},
        {"name": "Billie Eilish",     "genres": "alternative, indie",     "popularity": 88, "url": "https://open.spotify.com/artist/6qqNVTkY8uBU9cUvJSo"},
        {"name": "Bad Bunny",         "genres": "reggaeton, trap latino",  "popularity": 92, "url": "https://open.spotify.com/artist/BadBunny"},
        {"name": "Harry Styles",      "genres": "pop, rock",              "popularity": 86, "url": "https://open.spotify.com/artist/6deJKheGRHoExMgJeffo01"},
        {"name": "Dua Lipa",          "genres": "pop, dance",             "popularity": 87, "url": "https://open.spotify.com/artist/6HvZYsbFfjnjFrWF950C9m"},
        {"name": "The Chainsmokers",  "genres": "electronic, pop",        "popularity": 80, "url": "https://open.spotify.com/artist/69GGBxA162lQ3FqAJtBjBC"},
        {"name": "Shawn Mendes",      "genres": "pop, pop-rock",          "popularity": 82, "url": "https://open.spotify.com/artist/7n2wHs1TKAczGzO7Dd0qKw"},
        {"name": "Khalid",            "genres": "r&b, pop",               "popularity": 79, "url": "https://open.spotify.com/artist/6LuymHvsWaNTap0EYna"},
        {"name": "Camila Cabello",    "genres": "pop, latin",             "popularity": 81, "url": "https://open.spotify.com/artist/4nDoRrQiYLoBzwC5BhVG0k"},
        {"name": "Alan Walker",       "genres": "electronic, edm",        "popularity": 75, "url": "https://open.spotify.com/artist/7vk4XtFDUKqiaeIWHRSkHt"},
        {"name": "Logic",             "genres": "hip-hop, rap",           "popularity": 77, "url": "https://open.spotify.com/artist/5nCnpMS0Uixt4PSoCMTga7"},
    ]

    DEMO_TRACKS = [
        {"name": "Blinding Lights",      "artist": "The Weeknd",                     "album": "After Hours",             "popularity": 94, "url": "https://open.spotify.com/track/0VjIjW4GlUZAMYd2v"},
        {"name": "One Dance",            "artist": "Drake ft. Wizkid & Kyla",        "album": "Views",                   "popularity": 91, "url": "https://open.spotify.com/track/1301WleyT98MSxVHP"},
        {"name": "Levitating",           "artist": "Dua Lipa ft. DaBaby",            "album": "Future Nostalgia",        "popularity": 93, "url": "https://open.spotify.com/track/0dGsSpZcaIiOUieK"},
        {"name": "Shape of You",         "artist": "Ed Sheeran",                     "album": "÷",                       "popularity": 95, "url": "https://open.spotify.com/track/7qiZfU4dY1lsylv"},
        {"name": "Peaches",              "artist": "Justin Bieber ft. Daniel Caesar","album": "Justice",                 "popularity": 89, "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3P"},
        {"name": "Anti-Hero",            "artist": "Taylor Swift",                   "album": "Midnights",               "popularity": 96, "url": "https://open.spotify.com/track/0V3dsPmy4NqIUZSp"},
        {"name": "As It Was",            "artist": "Harry Styles",                   "album": "Harry's House",           "popularity": 92, "url": "https://open.spotify.com/track/7qiZfU4dY1lsylvN"},
        {"name": "Heat Waves",           "artist": "Glass Animals",                  "album": "Dreamland",               "popularity": 88, "url": "https://open.spotify.com/track/2takcwFXGpVSXi3R"},
        {"name": "Sunroof",              "artist": "Nicky Youre",                    "album": "Sunroof",                 "popularity": 87, "url": "https://open.spotify.com/track/4rVrcmK72nG8eQ5B"},
        {"name": "Running Up That Hill", "artist": "Kate Bush",                      "album": "Stranger Things Vol. 1",  "popularity": 90, "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3P"},
        {"name": "Flowers",             "artist": "Miley Cyrus",                    "album": "Endless Summer Vacation", "popularity": 91, "url": "https://open.spotify.com/track/4rVrcmK72nG8eQ5Bo"},
        {"name": "Industry Baby",        "artist": "Lil Nas X & Jack Harlow",        "album": "Montero",                 "popularity": 85, "url": "https://open.spotify.com/track/2takcwFXGpVSXi3R"},
        {"name": "Vampire",              "artist": "Olivia Rodrigo",                 "album": "GUTS",                    "popularity": 84, "url": "https://open.spotify.com/track/2takcwFXGpVSXi3R"},
        {"name": "Dance the Night",      "artist": "Dua Lipa",                       "album": "Barbie The Album",        "popularity": 89, "url": "https://open.spotify.com/track/2takcwFXGpVSXi3R"},
        {"name": "Cruel Summer",         "artist": "Taylor Swift",                   "album": "Lover",                   "popularity": 92, "url": "https://open.spotify.com/track/7qiZfU4dY1lsylvN"},
    ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _contrast_fg(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return "#FFFFFF"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 else "#FFFFFF"

    @staticmethod
    def _hex_to_rgb(hex_color: str):
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # ── Vignette mask (GFG / OpenCV Gaussian kernel method) ──────────────────

    @staticmethod
    def _make_vignette_mask(w: int, h: int, sigma_factor: float = 0.55) -> np.ndarray:
        """
        Build a 2-D Gaussian vignette mask normalised to [0, 1].

        Mirrors the GeeksforGeeks / OpenCV approach exactly:
          X_kernel = getGaussianKernel(cols, sigma)
          Y_kernel = getGaussianKernel(rows, sigma)
          mask     = Y_kernel * X_kernel.T          (outer product)
          mask     = mask / norm(mask)              (normalise)

        sigma_factor controls the brightness falloff:
          lower  → tighter bright centre, heavier dark border
          higher → gentler, wider bright area
        """
        sigma_x = w * sigma_factor
        sigma_y = h * sigma_factor

        x = np.arange(w, dtype=np.float64)
        y = np.arange(h, dtype=np.float64)

        kx = np.exp(-((x - w / 2) ** 2) / (2 * sigma_x ** 2))
        ky = np.exp(-((y - h / 2) ** 2) / (2 * sigma_y ** 2))

        mask = np.outer(ky, kx)            # h × w
        mask /= np.linalg.norm(mask)       # normalise
        mask /= mask.max()                 # rescale peak to 1.0
        return mask.astype(np.float32)

    # ── Init ──────────────────────────────────────────────────────────────────

    def __init__(self, root):
        self.root = root
        self.root.title("Spotify Widget")

        self.widget_width   = 390
        self.widget_height  = 390
        self.row_height     = 58
        self.control_height = 58
        self.content_height = self.widget_height - self.control_height

        self.sp_client          = None
        self.sp_api             = None
        self.current_time_range = "medium_term"
        self.current_tab        = "artists"
        self.drag_data          = {"x": 0, "y": 0}
        self.dragging_enabled   = True
        self.loading            = False
        self.artists_data       = []
        self.tracks_data        = []
        self.settings_open      = False
        self.demo_mode          = False
        self.image_cache        = {}
        self.item_images        = []
        # hold references to background PhotoImages so GC doesn't collect them
        self._bg_photos         = {}

        self.config_file = "widget_config.json"
        self.settings    = self.load_settings()
        self.current_palette = self.settings.get("palette", "terminal")
        if self.current_palette not in self.PALETTES:
            self.current_palette = "terminal"

        self.setup_styles()

        self.root.geometry(f"{self.widget_width}x{self.widget_height}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.configure(bg=self.panel_bg)

        self.create_ui()
        self.setup_drag()
        self.load_window_position()
        self.root.after(50, self.load_window_position)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after_idle(self.root.attributes, "-topmost", False)

        self.apply_theme_colors()
        self._show_loading("CONNECTING TO SPOTIFY...")
        self.authenticate()

    # ── Settings persistence ──────────────────────────────────────────────────

    def load_settings(self):
        defaults = {"palette": "terminal", "x": None, "y": None}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file) as f:
                    defaults.update(json.load(f))
            except Exception:
                pass
        return defaults

    def save_settings(self):
        self.settings["palette"] = self.current_palette
        self.settings["x"] = self.root.winfo_x()
        self.settings["y"] = self.root.winfo_y()
        with open(self.config_file, "w") as f:
            json.dump(self.settings, f, indent=2)

    def load_window_position(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = sw - self.widget_width  - 24
        y  = sh - self.widget_height - 64
        self.root.geometry(f"{self.widget_width}x{self.widget_height}+{x}+{y}")

    # ── Theme ─────────────────────────────────────────────────────────────────

    def setup_styles(self):
        p = self.PALETTES[self.current_palette]
        self.palette        = p
        self.bg_color       = p["bg"]
        self.secondary_bg   = p["secondary_bg"]
        self.tertiary_bg    = p["tertiary_bg"]
        self.fg_color       = p["fg"]
        self.accent_color   = p["accent"]
        self.text_secondary = p["text_secondary"]
        self.panel_bg       = p["bg"]

    def apply_theme_colors(self):
        self.setup_styles()
        self.update_background_colors()

    def update_background_colors(self):
        for attr in ("main_frame", "content_settings_frame"):
            if hasattr(self, attr):
                getattr(self, attr).configure(bg=self.panel_bg)
        for attr in ("content_frame", "artists_canvas", "artists_content",
                     "songs_canvas", "songs_content"):
            if hasattr(self, attr):
                getattr(self, attr).configure(bg=self.tertiary_bg)

    def change_palette(self, palette_name):
        reopen = self.settings_open
        self.current_palette = palette_name
        self.setup_styles()
        self.image_cache.clear()
        self._bg_photos.clear()
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=self.panel_bg)
        self.create_ui()
        if self.artists_data:
            self.display_artists()
        if self.tracks_data:
            self.display_songs()
        if reopen:
            self.open_settings()

    # ── UI construction ───────────────────────────────────────────────────────

    def create_ui(self):
        main_frame = tk.Frame(self.root, bg=self.panel_bg)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame = main_frame

        self.content_settings_frame = tk.Frame(main_frame, bg=self.panel_bg)
        self.content_settings_frame.pack(fill=tk.BOTH, expand=True)

        self.content_frame = tk.Frame(
            self.content_settings_frame, bg=self.tertiary_bg,
            height=self.content_height,
        )
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        self.content_frame.pack_propagate(False)

        # Bottom bar
        tk.Frame(main_frame, bg=self.accent_color, height=2).pack(
            fill=tk.X, side=tk.BOTTOM
        )
        self.control_frame = tk.Frame(main_frame, bg=self.secondary_bg)
        self.control_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_row = tk.Frame(self.control_frame, bg=self.secondary_bg)
        btn_row.pack(fill=tk.X, padx=4, pady=6)

        self.tab_buttons = {}
        for label, tab_name in [("ARTISTS", "artists"), ("SONGS", "songs")]:
            btn = self._make_btn(btn_row, label, lambda n=tab_name: self.change_tab(n))
            btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            self.tab_buttons[tab_name] = btn

        self.time_buttons = {}
        for label, code in [("1W", "short_term"), ("1M", "medium_term"), ("6M", "long_term")]:
            btn = self._make_btn(btn_row, label, lambda c=code: self.change_time_range(c))
            btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            self.time_buttons[code] = btn

        settings_btn = self._make_btn(btn_row, "SET", self.toggle_settings)
        settings_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        self.settings_btn = settings_btn

        self.update_control_states()

        # Artists canvas
        self.artists_canvas = tk.Canvas(
            self.content_frame, bg=self.tertiary_bg,
            highlightthickness=0, borderwidth=0, relief="flat",
        )
        self.artists_canvas.pack(fill=tk.BOTH, expand=True)
        self.artists_content = tk.Frame(self.artists_canvas, bg=self.tertiary_bg)
        self.artists_canvas.create_window(
            (0, 0), window=self.artists_content, anchor=tk.NW, width=self.widget_width,
        )

        # Songs canvas
        self.songs_canvas = tk.Canvas(
            self.content_frame, bg=self.tertiary_bg,
            highlightthickness=0, borderwidth=0, relief="flat",
        )
        self.songs_content = tk.Frame(self.songs_canvas, bg=self.tertiary_bg)
        self.songs_canvas.create_window(
            (0, 0), window=self.songs_content, anchor=tk.NW, width=self.widget_width,
        )

        self.canvases = {
            "artists": (self.artists_canvas, self.artists_content),
            "songs":   (self.songs_canvas,   self.songs_content),
        }

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.artists_canvas.pack(fill=tk.BOTH, expand=True)
        self.settings_frame = tk.Frame(self.content_settings_frame, bg=self.secondary_bg)

    def _make_btn(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            font=(FONT, 7, "bold"),
            bg=self.tertiary_bg,
            fg=self.fg_color,
            activebackground=self.accent_color,
            activeforeground=self._contrast_fg(self.accent_color),
            border=1,
            relief=tk.RAISED,
            padx=4,
            pady=5,
            command=command,
        )

    def update_control_states(self):
        if not hasattr(self, "tab_buttons"):
            return
        for tab, btn in self.tab_buttons.items():
            active = tab == self.current_tab
            btn.config(
                relief=tk.SUNKEN if active else tk.RAISED,
                bg=self.accent_color if active else self.tertiary_bg,
                fg=self._contrast_fg(self.accent_color) if active else self.fg_color,
            )
        for code, btn in self.time_buttons.items():
            active = code == self.current_time_range
            btn.config(
                relief=tk.SUNKEN if active else tk.RAISED,
                bg=self.accent_color if active else self.tertiary_bg,
                fg=self._contrast_fg(self.accent_color) if active else self.fg_color,
            )

    # ── Vignette'd checkered background ───────────────────────────────────────

    def _draw_checkered_bg(self, canvas, canvas_key: str):
        """
        Render the checker pattern as a numpy pixel array, multiply every
        channel by the Gaussian vignette mask, then place a single PhotoImage
        on the canvas — no overlay, the effect is baked into the pixels.
        """
        canvas.delete("bg_img")

        w   = self.widget_width
        n   = max(len(self.artists_data), len(self.tracks_data), 15)
        h   = n * 62 + self.content_height
        sz  = 8

        c1 = np.array(self._hex_to_rgb(self.palette.get("check1", self.tertiary_bg)), dtype=np.float32)
        c2 = np.array(self._hex_to_rgb(self.palette.get("check2", self.bg_color)),    dtype=np.float32)

        # Build checker via index arithmetic — no Python loops
        row_idx = np.arange(h) // sz          # shape (h,)
        col_idx = np.arange(w) // sz          # shape (w,)
        grid    = (row_idx[:, None] + col_idx[None, :]) % 2   # h × w, values {0,1}

        # Broadcast: where grid==0 use c1, else c2  →  h × w × 3
        img_arr = np.where(grid[:, :, None] == 0, c1, c2).astype(np.float32)

        # Gaussian vignette mask  (GFG method, sigma tuned to viewport size so
        # the effect is visible even when scrolled — we use content_height × w)
        mask = self._make_vignette_mask(w, self.content_height, sigma_factor=0.38)

        # Tile the mask vertically to cover the full scroll height
        repeats = int(np.ceil(h / self.content_height))
        tall_mask = np.tile(mask, (repeats, 1))[:h, :]    # h × w

        # Multiply each channel by the mask
        img_arr *= tall_mask[:, :, None]

        # ── CRT scanlines: darken every 2nd row to mimic phosphor line gaps ──
        scanlines         = np.ones((h, 1, 1), dtype=np.float32)
        scanlines[1::2]   = 0.78          # odd rows dimmed ~22 %
        img_arr          *= scanlines

        img_arr  = np.clip(img_arr, 0, 255).astype(np.uint8)

        photo = ImageTk.PhotoImage(Image.fromarray(img_arr, "RGB"))
        self._bg_photos[canvas_key] = photo          # keep reference
        canvas.create_image(0, 0, anchor=tk.NW, image=photo, tags="bg_img")
        canvas.tag_lower("bg_img")

    # ── Bloom + vignette on album art ────────────────────────────────────────

    def _apply_vignette_to_image(self, arr: np.ndarray) -> np.ndarray:
        """
        Apply the Gaussian vignette mask to an RGB uint8 numpy array in-place.
        Returns the modified array.
        """
        h, w = arr.shape[:2]
        mask = self._make_vignette_mask(w, h, sigma_factor=0.50)
        out  = arr.astype(np.float32)
        out *= mask[:, :, None]
        return np.clip(out, 0, 255).astype(np.uint8)

    def _apply_bloom(self, pil_img, size=38, bloom_radius=7, bloom_strength=0.55):
        """
        Composite a soft Gaussian bloom halo behind the sharp image.
        Returns a padded RGBA PIL Image; the transparent padding carries the glow.
        """
        pad   = bloom_radius * 2
        total = size + pad * 2

        sharp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rgba  = pil_img.convert("RGBA")
        rgba.thumbnail((size, size), Image.LANCZOS)
        sharp.paste(rgba, ((size - rgba.width) // 2, (size - rgba.height) // 2), rgba)

        src   = Image.new("RGBA", (total, total), (0, 0, 0, 0))
        src.paste(sharp, (pad, pad), sharp)

        bloom = src.filter(ImageFilter.GaussianBlur(radius=bloom_radius))
        bloom = ImageEnhance.Brightness(bloom).enhance(1.0 + bloom_strength)
        bloom = bloom.filter(ImageFilter.GaussianBlur(radius=bloom_radius // 2))

        result = Image.new("RGBA", (total, total), (0, 0, 0, 0))
        result.paste(bloom, (0, 0), bloom)
        result.paste(sharp, (pad, pad), sharp)
        return result

    def load_item_image(self, image_url, size=38):
        """
        Fetch image → apply Gaussian vignette to its pixels → composite bloom halo.
        Returns an ImageTk.PhotoImage.
        """
        if not image_url:
            return None
        key = (image_url, size)
        if key in self.image_cache:
            return self.image_cache[key]
        try:
            resp = requests.get(image_url, timeout=5)
            resp.raise_for_status()
            pil_img = Image.open(BytesIO(resp.content))

            # Step 1: square + resize
            rgb = pil_img.convert("RGB")
            rgb.thumbnail((size, size), Image.LANCZOS)
            square = Image.new("RGB", (size, size), self._hex_to_rgb(self.tertiary_bg))
            square.paste(rgb, ((size - rgb.width) // 2, (size - rgb.height) // 2))

            # Step 2: apply Gaussian vignette directly to pixel data
            arr         = np.array(square)
            arr         = self._apply_vignette_to_image(arr)
            vignette_pil = Image.fromarray(arr, "RGB")

            # Step 3: bloom halo composited behind the now-vignette'd image
            bloomed = self._apply_bloom(vignette_pil, size=size,
                                        bloom_radius=10, bloom_strength=0.80)

            photo = ImageTk.PhotoImage(bloomed)
            self.image_cache[key] = photo
            return photo
        except Exception as e:
            print(f"Image load error: {e}")
            return None

    # ── Settings panel ────────────────────────────────────────────────────────

    def toggle_settings(self):
        if self.settings_open:
            self.close_settings()
        else:
            self.open_settings()

    def open_settings(self):
        self.settings_open    = True
        self.dragging_enabled = False
        self.settings_btn.config(
            relief=tk.SUNKEN,
            bg=self.accent_color,
            fg=self._contrast_fg(self.accent_color),
        )
        self.content_frame.pack_forget()
        for w in self.settings_frame.winfo_children():
            w.destroy()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.settings_frame, text="[ SETTINGS ]",
                 font=(FONT, 11, "bold"), bg=self.secondary_bg, fg=self.fg_color).pack(pady=10)
        tk.Frame(self.settings_frame, bg=self.accent_color, height=1).pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Label(self.settings_frame, text="> COLOR THEME",
                 font=(FONT, 8, "bold"), bg=self.secondary_bg, fg=self.text_secondary).pack(anchor=tk.W, padx=14, pady=(4, 4))

        pal_frame = tk.Frame(self.settings_frame, bg=self.secondary_bg)
        pal_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        for pal_key in self.PALETTES:
            pal      = self.PALETTES[pal_key]
            selected = pal_key == self.current_palette
            btn_bg   = self.accent_color if selected else self.tertiary_bg
            tk.Button(
                pal_frame, text=pal["name"], font=(FONT, 7, "bold"),
                bg=btn_bg, fg=self._contrast_fg(btn_bg),
                activebackground=self.accent_color,
                activeforeground=self._contrast_fg(self.accent_color),
                border=1, relief=tk.SUNKEN if selected else tk.RAISED,
                padx=6, pady=3,
                command=lambda k=pal_key: self.change_palette(k),
            ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        tk.Frame(self.settings_frame, bg=self.accent_color, height=1).pack(fill=tk.X, padx=10, pady=4)
        mode_text  = "DEMO MODE" if self.demo_mode else "LIVE DATA"
        mode_color = self.text_secondary if self.demo_mode else self.fg_color
        tk.Label(self.settings_frame, text=f"> MODE: {mode_text}",
                 font=(FONT, 8), bg=self.secondary_bg, fg=mode_color).pack(anchor=tk.W, padx=14, pady=4)
        tk.Button(
            self.settings_frame, text="[ CLOSE ]", font=(FONT, 9, "bold"),
            bg=self.accent_color, fg=self._contrast_fg(self.accent_color),
            activebackground=self.fg_color, activeforeground=self._contrast_fg(self.fg_color),
            border=1, relief=tk.RAISED, padx=20, pady=6, command=self.close_settings,
        ).pack(pady=10)

    def close_settings(self):
        self.settings_open    = False
        self.dragging_enabled = True
        self.settings_btn.config(relief=tk.RAISED, bg=self.tertiary_bg, fg=self.fg_color)
        self.settings_frame.pack_forget()
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        self.save_settings()
        self.update_control_states()

    # ── Tab / time-range navigation ───────────────────────────────────────────

    def change_tab(self, tab_name):
        self.current_tab = tab_name
        self.update_control_states()
        for canvas, _ in self.canvases.values():
            canvas.pack_forget()
        canvas, _ = self.canvases[tab_name]
        canvas.pack(fill=tk.BOTH, expand=True)

    def change_time_range(self, time_code):
        self.current_time_range = time_code
        self.update_control_states()
        if not self.demo_mode:
            self.load_data()

    # ── Drag ──────────────────────────────────────────────────────────────────

    def setup_drag(self):
        self.root.bind("<Button-1>",        self.drag_start)
        self.root.bind("<B1-Motion>",       self.drag_motion)
        self.root.bind("<ButtonRelease-1>", self.drag_stop)

    def drag_start(self, event):
        if self.dragging_enabled:
            self.drag_data["x"] = event.x_root - self.root.winfo_x()
            self.drag_data["y"] = event.y_root - self.root.winfo_y()

    def drag_motion(self, event):
        if self.dragging_enabled:
            x = event.x_root - self.drag_data["x"]
            y = event.y_root - self.drag_data["y"]
            self.root.geometry(f"+{x}+{y}")

    def drag_stop(self, event):
        if self.dragging_enabled:
            self.save_settings()

    def _on_mousewheel(self, event):
        if self.settings_open:
            return
        if self.current_tab == "artists":
            self.artists_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            self.songs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Spotify auth / data ───────────────────────────────────────────────────

    def _show_loading(self, message="LOADING..."):
        for canvas, frame in self.canvases.values():
            for w in frame.winfo_children():
                w.destroy()
            canvas.delete("overlay")
            canvas.create_text(
                self.widget_width // 2, self.content_height // 2,
                text=message, font=(FONT, 9, "bold"),
                fill=self.text_secondary, anchor=tk.CENTER, tags="overlay",
            )

    def _clear_overlay(self):
        for canvas, _ in self.canvases.values():
            canvas.delete("overlay")

    def _show_error(self, message):
        for canvas, frame in self.canvases.values():
            for w in frame.winfo_children():
                w.destroy()
            canvas.delete("overlay")
            canvas.create_text(
                self.widget_width // 2, self.content_height // 2 - 24,
                text=message, font=(FONT, 8), fill=self.fg_color,
                anchor=tk.CENTER, width=self.widget_width - 20, tags="overlay",
            )
        visible_canvas, _ = self.canvases[self.current_tab]
        btn = tk.Button(
            visible_canvas, text="[ RETRY ]", font=(FONT, 8, "bold"),
            bg=self.accent_color, fg=self._contrast_fg(self.accent_color),
            activebackground=self.fg_color, activeforeground=self._contrast_fg(self.fg_color),
            border=1, relief=tk.RAISED,
            command=lambda: [self._show_loading("CONNECTING TO SPOTIFY..."), self.authenticate()],
        )
        visible_canvas.create_window(
            self.widget_width // 2, self.content_height // 2 + 24,
            window=btn, tags="overlay",
        )

    def authenticate(self):
        threading.Thread(target=self._authenticate_thread, daemon=True).start()

    def _authenticate_thread(self):
        try:
            auth           = SpotifyAuthenticator()
            self.sp_client = auth.get_spotify_client()
            self.sp_api    = SpotifyAPI(self.sp_client)
            self.root.after(0, lambda: self._show_loading("FETCHING YOUR DATA..."))
            self.load_data()
        except Exception as e:
            print(f"Auth error: {e}")
            self.root.after(0, lambda: self._show_error(f"AUTH FAILED\n{e}"))

    def load_data(self):
        if not self.sp_api:
            return
        self.loading = True
        threading.Thread(target=self._load_data_thread, daemon=True).start()

    def _load_data_thread(self):
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f_artists = executor.submit(self.sp_api.get_top_artists, self.current_time_range, 15)
                f_tracks  = executor.submit(self.sp_api.get_top_tracks,  self.current_time_range, 15)
                try:
                    artists = f_artists.result(timeout=15)
                except concurrent.futures.TimeoutError:
                    artists = []
                try:
                    tracks = f_tracks.result(timeout=15)
                except concurrent.futures.TimeoutError:
                    tracks = []

            if artists:
                self.artists_data = artists
                self.root.after(0, self.display_artists)
            if tracks:
                self.tracks_data = tracks
                self.root.after(0, self.display_songs)
            if artists or tracks:
                self.demo_mode = False
            else:
                self.root.after(0, lambda: self._show_error(
                    "NO DATA RETURNED\nSpotify returned nothing — your account may have no listening history,\nor the app is not approved."
                ))
        except Exception as e:
            msg = f"FAILED TO LOAD DATA\n{e}"
            print(f"Data load error: {e}")
            self.root.after(0, lambda m=msg: self._show_error(m))
        finally:
            self.loading = False

    # ── Display ───────────────────────────────────────────────────────────────

    def display_artists(self):
        self._clear_overlay()
        self.item_images = []
        for w in self.artists_content.winfo_children():
            w.destroy()
        if not self.artists_data:
            return
        self._draw_checkered_bg(self.artists_canvas, "artists")
        for idx, artist in enumerate(self.artists_data, 1):
            self._create_artist_row(idx, artist)
        self.artists_content.update_idletasks()
        self.artists_canvas.config(scrollregion=(0, 0, self.widget_width, 15 * 62))

    def display_songs(self):
        self._clear_overlay()
        self.item_images = []
        for w in self.songs_content.winfo_children():
            w.destroy()
        if not self.tracks_data:
            return
        self._draw_checkered_bg(self.songs_canvas, "songs")
        for idx, track in enumerate(self.tracks_data, 1):
            self._create_track_row(idx, track)
        self.songs_content.update_idletasks()
        self.songs_canvas.config(scrollregion=(0, 0, self.widget_width, 15 * 62))

    # ── Row builders ──────────────────────────────────────────────────────────

    def _create_artist_row(self, rank, artist):
        row_bg = self.tertiary_bg
        frame  = tk.Frame(
            self.artists_content, bg=row_bg,
            height=self.row_height - 6,
            highlightbackground=self.accent_color, highlightthickness=1,
        )
        frame.pack(fill=tk.X, padx=4, pady=2)
        frame.pack_propagate(False)

        tk.Label(frame, text=f"{rank:02d}", font=(FONT, 9, "bold"),
                 bg=self.accent_color, fg=self._contrast_fg(self.accent_color),
                 width=3, relief=tk.FLAT).pack(side=tk.LEFT, padx=(4, 0), pady=6)

        img = self.load_item_image(artist.get("image"))
        if img:
            lbl = tk.Label(frame, image=img, bg=row_bg, borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=(2, 2), pady=4)
            self.item_images.append(img)

        info = tk.Frame(frame, bg=row_bg)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        artist_url = artist.get("url", "#")
        lbl = tk.Label(info, text=f"> {artist['name']}", font=(FONT, 8, "bold"),
                       bg=row_bg, fg=self.fg_color, wraplength=230,
                       justify=tk.LEFT, anchor=tk.W, cursor="hand2")
        lbl.place(relx=0, rely=0.5, anchor=tk.W)
        lbl.bind("<Button-1>", lambda e: webbrowser.open(artist_url) if artist_url != "#" else None)

    def _create_track_row(self, rank, track):
        row_bg = self.tertiary_bg
        frame  = tk.Frame(
            self.songs_content, bg=row_bg,
            height=self.row_height - 6,
            highlightbackground=self.accent_color, highlightthickness=1,
        )
        frame.pack(fill=tk.X, padx=4, pady=2)
        frame.pack_propagate(False)

        tk.Label(frame, text=f"{rank:02d}", font=(FONT, 9, "bold"),
                 bg=self.accent_color, fg=self._contrast_fg(self.accent_color),
                 width=3, relief=tk.FLAT).pack(side=tk.LEFT, padx=(4, 0), pady=6)

        img = self.load_item_image(track.get("image"))
        if img:
            lbl = tk.Label(frame, image=img, bg=row_bg, borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=(2, 2), pady=4)
            self.item_images.append(img)

        info = tk.Frame(frame, bg=row_bg)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)

        song_url = track.get("url", "#")
        slbl = tk.Label(info, text=f"> {track['name']}", font=(FONT, 8, "bold"),
                        bg=row_bg, fg=self.fg_color, wraplength=220,
                        justify=tk.LEFT, anchor=tk.W, cursor="hand2")
        slbl.pack(anchor=tk.W)
        slbl.bind("<Button-1>", lambda e: webbrowser.open(song_url) if song_url != "#" else None)

        artist_url = track.get("artist_url", "#")
        albl = tk.Label(info, text=track["artist"], font=(FONT, 6),
                        bg=row_bg, fg=self.text_secondary, wraplength=240,
                        justify=tk.LEFT, anchor=tk.W, cursor="hand2")
        albl.pack(anchor=tk.W)
        albl.bind("<Button-1>", lambda e: webbrowser.open(artist_url) if artist_url != "#" else None)

    def _draw_pixel_bar(self, parent, value: int, width: int = 24):
        blocks  = 10
        filled  = max(0, min(blocks, round(value / 10)))
        block_h = 3
        gap     = 1
        canvas  = tk.Canvas(parent, width=width, height=blocks * (block_h + gap),
                             bg=self.tertiary_bg, highlightthickness=0)
        canvas.pack()
        for i in range(blocks):
            y_top = (blocks - 1 - i) * (block_h + gap)
            color = self.accent_color if i < filled else self.bg_color
            canvas.create_rectangle(0, y_top, width, y_top + block_h,
                                    fill=color, outline=self.secondary_bg)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app  = SpotifyWidget(root)
    root.mainloop()
    app.save_settings()


if __name__ == "__main__":
    main()