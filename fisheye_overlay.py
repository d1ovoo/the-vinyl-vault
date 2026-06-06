"""
fisheye_overlay.py
──────────────────
Whole-widget CRT barrel-distortion overlay for SpotifyWidget.

The feedback-loop bug fix
-------------------------
The old version screenshotted the screen region including the overlay itself,
so each frame distorted an already-distorted image → widget shrank to a ball.

Fix: the overlay window is withdrawn (hidden) BEFORE the grab, then restored
AFTER. Because withdraw/deiconify + update() happen synchronously inside one
call before any screen repaint occurs, the grab always sees the raw flat
widget, never the distorted overlay. No flicker, no feedback.
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# ── tunables ──────────────────────────────────────────────────────────────────
REFRESH_MS = 50       # repaint interval in ms (~20 fps)
STRENGTH   = 0.18     # barrel strength: 0 = flat, 0.3 = heavy bulge
CORNER_R   = 18       # rounded-corner radius in pixels
# ─────────────────────────────────────────────────────────────────────────────


def _build_lut(w: int, h: int, strength: float):
    """
    Pre-compute destination→source pixel mapping for barrel distortion.
    Cached so it's only built once per window size.
    """
    cx, cy = w / 2.0, h / 2.0
    norm   = (cx ** 2 + cy ** 2) ** 0.5

    src_xs = []
    src_ys = []
    for dy in range(h):
        for dx in range(w):
            nx = (dx - cx) / norm
            ny = (dy - cy) / norm
            r2 = nx * nx + ny * ny
            # Pull source inward → destination appears to bulge outward
            factor = 1.0 + strength * r2
            sx = int(cx + nx * factor * norm)
            sy = int(cy + ny * factor * norm)
            src_xs.append(max(0, min(w - 1, sx)))
            src_ys.append(max(0, min(h - 1, sy)))

    return src_xs, src_ys


def _apply_lut(img: Image.Image, lut_xs, lut_ys) -> Image.Image:
    w, h   = img.size
    src    = img.tobytes()
    out    = bytearray(w * h * 3)
    stride = w * 3
    for i, (sx, sy) in enumerate(zip(lut_xs, lut_ys)):
        s = sy * stride + sx * 3
        d = i * 3
        out[d]     = src[s]
        out[d + 1] = src[s + 1]
        out[d + 2] = src[s + 2]
    return Image.frombytes("RGB", (w, h), bytes(out))


def _rounded_mask(w: int, h: int, r: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return mask


class FisheyeOverlay:
    """
    Transparent Toplevel that renders a barrel-distorted (CRT bulge) copy of
    the parent window on top of it.

    The overlay hides itself before each screenshot so it never captures its
    own output — eliminating the feedback / shrinking-ball problem.
    """

    def __init__(self, parent: tk.Tk, enabled: bool = True):
        self._parent  = parent
        self._enabled = enabled
        self._job     = None
        self._photo   = None
        self._lut     = None   # (xs, ys, w, h)
        self._mask    = None   # (img, w, h)

        self._top = tk.Toplevel(parent)
        self._top.overrideredirect(True)
        self._top.attributes("-topmost", True)
        self._top.configure(bg="#010101")
        try:
            self._top.attributes("-transparentcolor", "#010101")
        except tk.TclError:
            pass
        try:
            self._top.attributes("-disabled", True)   # pass clicks through (Windows)
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
        xs, ys   = _build_lut(w, h, STRENGTH)
        self._lut = (xs, ys, w, h)
        return xs, ys

    def _get_mask(self, w, h):
        if self._mask and self._mask[1] == w and self._mask[2] == h:
            return self._mask[0]
        m          = _rounded_mask(w, h, CORNER_R)
        self._mask = (m, w, h)
        return m

    def _grab_parent_only(self):
        """
        Grab the parent window's screen region WITHOUT the overlay in the shot.

        Steps:
          1. Withdraw the overlay (makes it invisible to the compositor).
          2. Call update_idletasks() so the compositor actually removes it
             before we grab.
          3. Grab the screen region.
          4. Restore the overlay.

        This is synchronous — no after() calls — so the overlay is hidden for
        only the duration of the grab (~1 ms) and reappears immediately after.
        """
        from PIL import ImageGrab

        x = self._parent.winfo_rootx()
        y = self._parent.winfo_rooty()
        w = self._parent.winfo_width()
        h = self._parent.winfo_height()
        if w < 10 or h < 10:
            return None

        try:
            # Hide overlay so it isn't in the screenshot
            self._top.withdraw()
            self._parent.update_idletasks()   # flush pending draws

            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        except Exception:
            img = None
        finally:
            # Always restore, even if grab failed
            self._top.deiconify()
            self._top.attributes("-topmost", True)

        return img

    def _refresh(self):
        if not self._enabled:
            return

        self._place_overlay()

        src = self._grab_parent_only()
        if src is None:
            return

        w, h = src.size
        src  = src.convert("RGB")

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