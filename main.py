"""
Spotify Dashboard Widget
Modern minimal desktop widget for displaying top Spotify artists and songs
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from io import BytesIO
import requests
import threading

from spotify_auth import SpotifyAuthenticator
from spotify_api import SpotifyAPI


class SpotifyWidget:
    """Modern minimal Spotify Dashboard Widget"""

    def __init__(self, root):
        self.root = root
        self.root.title("Spotify Widget")
        self.root.geometry("380x650")
        self.root.resizable(False, False)
        
        # Make window draggable
        self.drag_data = {"x": 0, "y": 0}
        
        # Initialize variables
        self.sp_client = None
        self.sp_api = None
        self.current_time_range = "medium_term"
        self.current_tab = "artists"
        self.loading = False
        self.artists_data = []
        self.tracks_data = []
        self.image_cache = {}
        
        # Configure styles
        self.setup_styles()
        
        # Create UI
        self.create_ui()
        
        # Make window draggable
        self.setup_drag()
        
        # Try to authenticate
        self.authenticate()

    def setup_styles(self):
        """Setup custom styles for the widget"""
        # Colors (Spotify theme)
        self.bg_color = "#0F0F0F"
        self.secondary_bg = "#1a1a1a"
        self.tertiary_bg = "#252525"
        self.fg_color = "#FFFFFF"
        self.spotify_green = "#1DB954"
        self.text_secondary = "#B3B3B3"
        
        self.root.configure(bg=self.bg_color)
        self.root.attributes('-alpha', 0.98)  # Slight transparency
        
        # Configure ttk style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', padding=[20, 10])

    def create_ui(self):
        """Create the widget UI"""
        # Main container with rounded effect
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Header with title and drag handle
        header_frame = tk.Frame(main_frame, bg=self.secondary_bg, height=50)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Title with icon
        title_label = tk.Label(
            header_frame,
            text="🎵 Spotify",
            font=("Segoe UI", 14, "bold"),
            bg=self.secondary_bg,
            fg=self.spotify_green
        )
        title_label.pack(side=tk.LEFT, padx=15, pady=12)
        
        # Stay on top button
        self.stay_on_top_var = tk.BooleanVar(value=False)
        stay_btn = tk.Button(
            header_frame,
            text="📌",
            font=("Arial", 10),
            bg=self.secondary_bg,
            fg=self.text_secondary,
            border=0,
            command=self.toggle_stay_on_top,
            activebackground=self.tertiary_bg,
            activeforeground=self.spotify_green
        )
        stay_btn.pack(side=tk.RIGHT, padx=10, pady=10)
        self.stay_btn = stay_btn
        
        # Time range selector frame
        time_frame = tk.Frame(main_frame, bg=self.bg_color)
        time_frame.pack(fill=tk.X, padx=12, pady=10)
        
        self.time_buttons = {}
        button_configs = [
            ("Week", "short_term"),
            ("Month", "medium_term"),
            ("6M", "long_term")
        ]
        
        for label, code in button_configs:
            is_selected = code == self.current_time_range
            btn = tk.Button(
                time_frame,
                text=label,
                font=("Segoe UI", 9, "bold"),
                bg=self.spotify_green if is_selected else self.tertiary_bg,
                fg=self.bg_color if is_selected else self.fg_color,
                border=0,
                command=lambda c=code: self.change_time_range(c),
                relief=tk.FLAT,
                padx=12,
                pady=6,
                activebackground=self.spotify_green,
                activeforeground=self.bg_color
            )
            btn.pack(side=tk.LEFT, padx=4)
            self.time_buttons[code] = btn
        
        # Tab container
        tab_frame = tk.Frame(main_frame, bg=self.bg_color)
        tab_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(tab_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Artists tab
        self.artists_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.artists_frame, text="  🎤 Artists  ")
        
        # Songs tab
        self.songs_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.songs_frame, text="  🎵 Songs  ")
        
        # Bind tab change
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Create scrollable content for artists
        self.artists_canvas = tk.Canvas(
            self.artists_frame,
            bg=self.bg_color,
            highlightthickness=0,
            borderwidth=0
        )
        self.artists_canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Scrollbar for artists
        artists_scroll = ttk.Scrollbar(
            self.artists_frame,
            orient=tk.VERTICAL,
            command=self.artists_canvas.yview
        )
        artists_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.artists_canvas.config(yscrollcommand=artists_scroll.set)
        self.artists_content = tk.Frame(self.artists_canvas, bg=self.bg_color)
        self.artists_canvas.create_window((0, 0), window=self.artists_content, anchor=tk.NW, width=365)
        
        # Bind mouse wheel to canvas
        self.artists_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Create scrollable content for songs
        self.songs_canvas = tk.Canvas(
            self.songs_frame,
            bg=self.bg_color,
            highlightthickness=0,
            borderwidth=0
        )
        self.songs_canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Scrollbar for songs
        songs_scroll = ttk.Scrollbar(
            self.songs_frame,
            orient=tk.VERTICAL,
            command=self.songs_canvas.yview
        )
        songs_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.songs_canvas.config(yscrollcommand=songs_scroll.set)
        self.songs_content = tk.Frame(self.songs_canvas, bg=self.bg_color)
        self.songs_canvas.create_window((0, 0), window=self.songs_content, anchor=tk.NW, width=365)
        
        # Status bar
        self.status_label = tk.Label(
            main_frame,
            text="Connecting...",
            font=("Segoe UI", 8),
            bg=self.secondary_bg,
            fg=self.text_secondary,
            justify=tk.LEFT
        )
        self.status_label.pack(fill=tk.X, padx=12, pady=8)

    def setup_drag(self):
        """Setup window dragging"""
        self.root.bind("<Button-1>", self.drag_start)
        self.root.bind("<B1-Motion>", self.drag_motion)

    def drag_start(self, event):
        """Start dragging"""
        self.drag_data["x"] = event.x_root - self.root.winfo_x()
        self.drag_data["y"] = event.y_root - self.root.winfo_y()

    def drag_motion(self, event):
        """Handle dragging"""
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def toggle_stay_on_top(self):
        """Toggle always on top"""
        self.stay_on_top_var.set(not self.stay_on_top_var.get())
        self.root.attributes('-topmost', self.stay_on_top_var.get())
        color = self.spotify_green if self.stay_on_top_var.get() else self.text_secondary
        self.stay_btn.config(fg=color)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if self.current_tab == "artists":
            self.artists_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        else:
            self.songs_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def authenticate(self):
        """Authenticate with Spotify API"""
        self.set_status("🔐 Authenticating...")
        threading.Thread(target=self._authenticate_thread, daemon=True).start()

    def _authenticate_thread(self):
        """Run authentication in background thread"""
        try:
            auth = SpotifyAuthenticator()
            self.sp_client = auth.get_spotify_client()
            self.sp_api = SpotifyAPI(self.sp_client)
            
            # Verify authentication
            user = self.sp_api.get_user_profile()
            self.set_status(f"✓ Logged in as {user['name']}")
            
            # Load initial data
            self.load_data()
        except Exception as e:
            self.set_status(f"✗ Auth failed: {str(e)[:40]}")
            self.root.after(2000, lambda: messagebox.showerror(
                "Authentication Error",
                f"Failed to authenticate:\n{str(e)}"
            ))

    def change_time_range(self, time_code):
        """Change time range and reload data"""
        self.current_time_range = time_code
        
        # Update button states
        for code, btn in self.time_buttons.items():
            if code == time_code:
                btn.config(bg=self.spotify_green, fg=self.bg_color)
            else:
                btn.config(bg=self.tertiary_bg, fg=self.fg_color)
        
        self.load_data()

    def load_data(self):
        """Load top artists and tracks"""
        if not self.sp_api:
            self.set_status("✗ Not authenticated")
            return
        
        self.loading = True
        self.set_status("📊 Loading...")
        threading.Thread(target=self._load_data_thread, daemon=True).start()

    def _load_data_thread(self):
        """Load data in background thread"""
        try:
            artists = self.sp_api.get_top_artists(self.current_time_range, limit=15)
            tracks = self.sp_api.get_top_tracks(self.current_time_range, limit=15)
            
            self.artists_data = artists
            self.tracks_data = tracks
            
            self.root.after(0, self.display_artists)
            self.root.after(0, self.display_songs)
            self.set_status("✓ Data loaded")
        except Exception as e:
            self.set_status(f"✗ Error: {str(e)[:40]}")
        finally:
            self.loading = False

    def display_artists(self):
        """Display artists in tab"""
        # Clear
        for widget in self.artists_content.winfo_children():
            widget.destroy()
        
        if not self.artists_data:
            label = tk.Label(
                self.artists_content,
                text="No data available",
                bg=self.bg_color,
                fg=self.text_secondary,
                font=("Segoe UI", 10)
            )
            label.pack(pady=20)
            self.artists_canvas.config(scrollregion=self.artists_canvas.bbox("all"))
            return
        
        for idx, artist in enumerate(self.artists_data, 1):
            self.create_artist_item(idx, artist)
        
        self.artists_content.update_idletasks()
        self.artists_canvas.config(scrollregion=self.artists_canvas.bbox("all"))

    def display_songs(self):
        """Display songs in tab"""
        # Clear
        for widget in self.songs_content.winfo_children():
            widget.destroy()
        
        if not self.tracks_data:
            label = tk.Label(
                self.songs_content,
                text="No data available",
                bg=self.bg_color,
                fg=self.text_secondary,
                font=("Segoe UI", 10)
            )
            label.pack(pady=20)
            self.songs_canvas.config(scrollregion=self.songs_canvas.bbox("all"))
            return
        
        for idx, track in enumerate(self.tracks_data, 1):
            self.create_track_item(idx, track)
        
        self.songs_content.update_idletasks()
        self.songs_canvas.config(scrollregion=self.songs_canvas.bbox("all"))

    def create_artist_item(self, rank, artist):
        """Create artist item"""
        item_frame = tk.Frame(self.artists_content, bg=self.tertiary_bg)
        item_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Rank circle
        rank_label = tk.Label(
            item_frame,
            text=f"{rank}",
            font=("Segoe UI", 10, "bold"),
            bg=self.spotify_green,
            fg=self.bg_color,
            width=3,
            height=1
        )
        rank_label.pack(side=tk.LEFT, padx=8, pady=8)
        
        # Info
        info_frame = tk.Frame(item_frame, bg=self.tertiary_bg)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        name_label = tk.Label(
            info_frame,
            text=artist['name'],
            font=("Segoe UI", 10, "bold"),
            bg=self.tertiary_bg,
            fg=self.fg_color,
            wraplength=250,
            justify=tk.LEFT
        )
        name_label.pack(anchor=tk.W)
        
        # Popularity bar
        popularity = artist['popularity']
        bar_frame = tk.Frame(info_frame, bg=self.secondary_bg, height=4)
        bar_frame.pack(fill=tk.X, pady=(4, 0))
        
        bar_fill = tk.Frame(
            bar_frame,
            bg=self.spotify_green,
            height=4
        )
        bar_fill.pack(side=tk.LEFT, fill=tk.BOTH)
        bar_fill.config(width=int(250 * popularity / 100))

    def create_track_item(self, rank, track):
        """Create track item"""
        item_frame = tk.Frame(self.songs_content, bg=self.tertiary_bg)
        item_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Rank circle
        rank_label = tk.Label(
            item_frame,
            text=f"{rank}",
            font=("Segoe UI", 10, "bold"),
            bg=self.spotify_green,
            fg=self.bg_color,
            width=3,
            height=1
        )
        rank_label.pack(side=tk.LEFT, padx=8, pady=8)
        
        # Info
        info_frame = tk.Frame(item_frame, bg=self.tertiary_bg)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        name_label = tk.Label(
            info_frame,
            text=track['name'],
            font=("Segoe UI", 10, "bold"),
            bg=self.tertiary_bg,
            fg=self.fg_color,
            wraplength=250,
            justify=tk.LEFT
        )
        name_label.pack(anchor=tk.W)
        
        artist_label = tk.Label(
            info_frame,
            text=track['artist'],
            font=("Segoe UI", 8),
            bg=self.tertiary_bg,
            fg=self.text_secondary,
            wraplength=250,
            justify=tk.LEFT
        )
        artist_label.pack(anchor=tk.W)
        
        # Popularity bar
        popularity = track['popularity']
        bar_frame = tk.Frame(info_frame, bg=self.secondary_bg, height=4)
        bar_frame.pack(fill=tk.X, pady=(4, 0))
        
        bar_fill = tk.Frame(
            bar_frame,
            bg=self.spotify_green,
            height=4
        )
        bar_fill.pack(side=tk.LEFT, fill=tk.BOTH)
        bar_fill.config(width=int(250 * popularity / 100))

    def on_tab_changed(self, event):
        """Handle tab change"""
        current_tab = self.notebook.index(self.notebook.select())
        self.current_tab = "artists" if current_tab == 0 else "songs"

    def set_status(self, message):
        """Update status"""
        self.status_label.config(text=message)


def main():
    """Main entry point"""
    root = tk.Tk()
    root.configure(bg="#0F0F0F")
    
    # Set modern window style
    root.resizable(False, False)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"+{x}+{y}")
    
    app = SpotifyWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
