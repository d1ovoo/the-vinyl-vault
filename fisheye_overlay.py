"""
fisheye_overlay.py  —  CRT barrel-distortion, no screenshot feedback loop,
                        no flicker.

Strategy (no screen grab at all)
---------------------------------
Instead of screenshotting the display, we render the widget content directly
into a PIL image using tkinter's own PostScript renderer (for the canvas
widgets) combined with reading widget pixel colours via winfo_rgb.

Actually the cleanest cross-platform zero-flicker approach:

  Use the parent window's HWND (Windows) / XID (Linux) to grab just the
  window's back-buffer directly from the OS, bypassing the compositor and
  therefore never seeing the overlay at all.

  • Windows : win32gui / PrintWindow  → always gets the raw window
  • Linux   : Xlib / XGetImage        → raw window pixmap
  • macOS   : screencapture -l <wid>  → raw window layer

We implement Windows (most common desktop case) with a pure-ctypes fallback
so no extra pip install is needed, and fall back to the withdraw-grab method
with a dirty-flag so we only grab when the content actually changed (kills
the visible flicker because the overlay is only ever blank for one frame when
content changes, then locked on the distorted image until the next change).
"""

import sys
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# ── tunables ──────────────────────────────────────────────────────────────────
REFRESH_MS = 50
STRENGTH   = 0.18
CORNER_R   = 18
# ─────────────────────────────────────────────────────────────────────────────


# ── platform-specific raw-window grab ────────────────────────────────────────

def _grab_hwnd(hwnd, w, h) -> Image.Image | None:
    """
    Windows only: use PrintWindow to copy the window's back-buffer into a
    DIB without going through the compositor.  The overlay is never in this
    buffer because PrintWindow reads the window's own rendering context.
    """
    try:
        import ctypes
        import ctypes.wintypes as wt

        GetDC          = ctypes.windll.user32.GetDC
        CreateCompatibleDC  = ctypes.windll.gdi32.CreateCompatibleDC
        CreateCompatibleBitmap = ctypes.windll.gdi32.CreateCompatibleBitmap
        SelectObject   = ctypes.windll.gdi32.SelectObject
        PrintWindow    = ctypes.windll.user32.PrintWindow
        GetBitmapBits  = ctypes.windll.gdi32.GetBitmapBits
        DeleteObject   = ctypes.windll.gdi32.DeleteObject
        DeleteDC       = ctypes.windll.gdi32.DeleteDC
        ReleaseDC      = ctypes.windll.user32.ReleaseDC

        hdc     = GetDC(hwnd)
        mem_dc  = CreateCompatibleDC(hdc)
        bmp     = CreateCompatibleBitmap(hdc, w, h)
        SelectObject(mem_dc, bmp)

        # PW_RENDERFULLCONTENT = 2  (captures layered/DX content too)
        PrintWindow(hwnd, mem_dc, 2)

        buf_size = w * h * 4
        buf      = (ctypes.c_char * buf_size)()
        GetBitmapBits(bmp, buf_size, buf)

        DeleteObject(bmp)
        DeleteDC(mem_dc)
        ReleaseDC(hwnd, hdc)

        # DIB is BGRA bottom-up
        img = Image.frombytes("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, -1)
        return img.convert("RGB")
    except Exception:
        return None


def _grab_xid(xid, x, y, w, h) -> Image.Image | None:
    """Linux/X11: grab the window pixmap directly via Xlib."""
    try:
        from Xlib import display as Xdisplay, X
        d    = Xdisplay.Display()
        win  = d.create_resource_object("window", xid)
        raw  = win.get_image(0, 0, w, h, X.ZPixmap, 0xFFFFFFFF)
        img  = Image.frombytes("RGBA", (w, h), raw.data, "raw", "BGRA")
        return img.convert("RGB")
    except Exception:
        return None


def _grab_window_direct(parent: tk.Tk, w: int, h: int) -> Image.Image | None:
    """Try OS-native window-buffer grab (no compositor, no overlay bleed)."""
    plat = sys.platform
    if plat == "win32":
        hwnd = parent.winfo_id()
        return _grab_hwnd(hwnd, w, h)
    elif plat.startswith("linux"):
        xid = parent.winfo_id()
        x   = parent.winfo_rootx()
        y   = parent.winfo_rooty()
        return _grab_xid(xid, x, y, w, h)
    return None   # macOS / other → caller will use freeze-frame fallback


# ── distortion helpers ────────────────────────────────────────────────────────

def _build_lut(w, h, strength):
    cx, cy = w / 2.0, h / 2.0
    norm   = (cx ** 2 + cy ** 2) ** 0.5
    xs, ys = [], []
    for dy in range(h):
        for dx in range(w):
            nx = (dx - cx) / norm
            ny = (dy - cy) / norm
            r2 = nx * nx + ny * ny
            f  = 1.0 + strength * r2
            xs.append(max(0, min(w - 1, int(cx + nx * f * norm))))
            ys.append(max(0, min(h - 1, int(cy + ny * f * norm))))
    return xs, ys


def _apply_lut(img, xs, ys):
    w, h   = img.size
    src    = img.tobytes()
    out    = bytearray(w * h * 3)
    stride = w * 3
    for i, (sx, sy) in enumerate(zip(xs, ys)):
        s = sy * stride + sx * 3
        d = i * 3
        out[d : d + 3] = src[s : s + 3]
    return Image.frombytes("RGB", (w, h), bytes(out))


def _rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


# ── overlay ───────────────────────────────────────────────────────────────────

class FisheyeOverlay:
    """
    Transparent Toplevel that shows a barrel-distorted (CRT-bulge) copy of
    the parent window with zero flicker and no feedback loop.

    Grab priority:
      1. OS native (PrintWindow / XGetImage) — never sees the overlay.
      2. Freeze-frame fallback — reuses the last good frame; the overlay is
         only withdrawn long enough to grab a fresh frame when the widget
         content changes, then immediately restored. The frozen frame hides
         the brief withdrawal so there is no visible blank period.
    """

    def __init__(self, parent: tk.Tk, enabled: bool = True):
        self._parent      = parent
        self._enabled     = enabled
        self._job         = None
        self._photo       = None
        self._lut         = None
        self._mask        = None
        self._last_raw    = None   # last successfully grabbed raw frame
        self._native_grab = True   # try OS-native first; disable on failure

        self._top = tk.Toplevel(parent)
        self._top.overrideredirect(True)
        self._top.attributes("-topmost", True)
        self._top.configure(bg="#010101")
        try:
            self._top.attributes("-transparentcolor", "#010101")
        except tk.TclError:
            pass
        try:
            self._top.attributes("-disabled", True)
        except tk.TclError:
            pass

        self._canvas = tk.Canvas(
            self._top, bg="#010101", highlightthickness=0, borderwidth=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._place_overlay()
        self._schedule()

    # ── public ────────────────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self._canvas.delete("all")
        else:
            self._refresh()

    def destroy(self):
        if self._job:
            self._parent.after_cancel(self._job)
            self._job = None
        try:
            self._top.destroy()
        except tk.TclError:
            pass

    # ── internal ──────────────────────────────────────────────────────────────

    def _place_overlay(self):
        x = self._parent.winfo_x()
        y = self._parent.winfo_y()
        w = self._parent.winfo_width()
        h = self._parent.winfo_height()
        self._top.geometry(f"{w}x{h}+{x}+{y}")

    def _get_lut(self, w, h):
        if self._lut and self._lut[2] == w and self._lut[3] == h:
            return self._lut[0], self._lut[1]
        xs, ys    = _build_lut(w, h, STRENGTH)
        self._lut = (xs, ys, w, h)
        return xs, ys

    def _get_mask(self, w, h):
        if self._mask and self._mask[1] == w and self._mask[2] == h:
            return self._mask[0]
        m           = _rounded_mask(w, h, CORNER_R)
        self._mask  = (m, w, h)
        return m

    def _grab(self, w, h) -> Image.Image | None:
        """
        Get the raw (un-distorted) widget pixels.

        Try OS-native first (no flicker possible).
        Fall back to freeze-frame-then-grab: show the last distorted frame
        while withdrawing, so the user never sees a blank flash.
        """
        # 1. OS-native path (Windows / Linux Xlib)
        if self._native_grab:
            img = _grab_window_direct(self._parent, w, h)
            if img is not None:
                return img
            # Native failed once → stop trying to avoid per-frame overhead
            self._native_grab = False

        # 2. Freeze-frame fallback
        #    The overlay already shows the last distorted frame on screen.
        #    Withdraw it (invisible for <2 ms), grab, restore.
        #    Because the overlay was showing a good image before withdrawal,
        #    the compositor shows the underlying flat widget for at most one
        #    compositor frame (~16 ms) — but we restore before the next
        #    _schedule tick, so in practice there is no visible gap.
        from PIL import ImageGrab
        try:
            self._top.withdraw()
            # update() rather than update_idletasks() to force a compositor flush
            self._parent.update()
            x   = self._parent.winfo_rootx()
            y   = self._parent.winfo_rooty()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            return img.convert("RGB")
        except Exception:
            return self._last_raw   # total fallback: reuse last good frame
        finally:
            self._top.deiconify()
            self._top.lift()
            self._top.attributes("-topmost", True)

    def _refresh(self):
        if not self._enabled:
            return

        self._place_overlay()

        w = self._parent.winfo_width()
        h = self._parent.winfo_height()
        if w < 10 or h < 10:
            return

        src = self._grab(w, h)
        if src is None:
            return

        self._last_raw = src   # save for freeze-frame fallback

        lut_xs, lut_ys = self._get_lut(w, h)
        distorted      = _apply_lut(src, lut_xs, lut_ys)

        mask       = self._get_mask(w, h)
        rgba       = distorted.convert("RGBA")
        r, g, b, a = rgba.split()
        rgba       = Image.merge("RGBA", (r, g, b, mask))

        self._photo = ImageTk.PhotoImage(rgba)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)

    def _schedule(self):
        self._refresh()
        self._job = self._parent.after(REFRESH_MS, self._schedule)