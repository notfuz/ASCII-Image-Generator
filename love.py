import tkinter as tk
from tkinter import filedialog, ttk
import random
import time
import threading
from PIL import Image, ImageOps

CHARSET_PRESETS = {
    "01": "01",
    "0123456789": "0123456789",
    "01 (threshold)": "01",
    "Dense ASCII": "@#&$%8*o!;.'",
}

class ImageCharMorphApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Image → Colored ASCII Morph")
        self.bg = "black"
        self.default_fg = "#FFFFFF"
        self.root.configure(bg=self.bg)

        # UI: top controls
        ctrl = tk.Frame(self.root, bg=self.bg)
        ctrl.pack(fill="x", padx=8, pady=6)

        tk.Button(ctrl, text="Open Image", command=self.open_image).pack(side="left")

        tk.Label(ctrl, text="Scale:", bg=self.bg, fg=self.default_fg).pack(side="left", padx=(8,0))
        self.scale_var = tk.IntVar(value=10)
        tk.Spinbox(ctrl, from_=4, to=48, textvariable=self.scale_var, width=4).pack(side="left")

        tk.Label(ctrl, text="Charset:", bg=self.bg, fg=self.default_fg).pack(side="left", padx=(8,0))
        self.charset_var = tk.StringVar(value="01")
        ttk.Combobox(ctrl, values=list(CHARSET_PRESETS.keys()), textvariable=self.charset_var, width=14).pack(side="left")

        self.color_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="Color Mode", variable=self.color_mode_var, bg=self.bg, fg=self.default_fg, selectcolor=self.bg, activebackground=self.bg).pack(side="left", padx=(8,0))

        tk.Label(ctrl, text="Speed:", bg=self.bg, fg=self.default_fg).pack(side="left", padx=(8,0))
        self.speed_var = tk.DoubleVar(value=0.04)
        tk.Scale(ctrl, variable=self.speed_var, from_=0.005, to=0.2, resolution=0.005, orient="horizontal", length=120, bg=self.bg, fg=self.default_fg).pack(side="left")

        tk.Button(ctrl, text="Start Morph", command=self.start_morph).pack(side="right")

        # Canvas for drawing
        self.canvas_frame = tk.Frame(self.root, bg=self.bg)
        self.canvas_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg=self.bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # state
        self.image = None               # original PIL image (RGB)
        self.target_chars = None        # 2D list of target characters
        self.target_colors = None       # 2D list of target hex colors (strings)
        self.current_chars = None       # 2D list of current characters
        self.current_colors = None      # 2D list of current colors
        self.animating = False

        # Resize handling
        self.root.bind("<Configure>", self.on_resize)

        self.root.geometry("1200x700")
        self.root.minsize(600,300)
        self.root.mainloop()

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files","*.png;*.jpg;*.jpeg;*.bmp;*.gif" )])
        if not path:
            return
        # keep a color copy
        self.image = Image.open(path).convert("RGB")
        self.prepare_target()
        self.draw_static_preview()

    def get_charset(self):
        key = self.charset_var.get()
        preset = CHARSET_PRESETS.get(key)
        if preset is not None:
            return preset
        # fallback to literal text in combobox
        s = key.strip()
        return s if s else "01"

    def prepare_target(self):
        if self.image is None:
            return
        scale = max(4, int(self.scale_var.get()))
        # compute grid size based on canvas size
        c_w = max(80, self.canvas.winfo_width())
        c_h = max(40, self.canvas.winfo_height())

        cols = max(2, c_w // scale)
        rows = max(2, c_h // scale)

        img = self.image.copy()
        img = ImageOps.fit(img, (cols, rows), Image.LANCZOS)

        pixels = list(img.getdata())
        charset = self.get_charset()

        target_chars = []
        target_colors = []

        use_threshold = (self.charset_var.get() == "01 (threshold)")

        for r in range(rows):
            row_chars = []
            row_cols = []
            for c in range(cols):
                pr,pg,pb = pixels[r*cols + c]
                brightness = int(0.299*pr + 0.587*pg + 0.114*pb)

                # choose character
                if use_threshold and charset == "01":
                    ch = "1" if brightness < 128 else "0"
                else:
                    # invert brightness so dark -> denser character
                    val = 255 - brightness
                    idx = int((val/255) * (len(charset)-1)) if len(charset) > 1 else 0
                    ch = charset[idx]

                # color string for drawing
                color = f"#{pr:02x}{pg:02x}{pb:02x}" if self.color_mode_var.get() else self.default_fg

                row_chars.append(ch)
                row_cols.append(color)
            target_chars.append(row_chars)
            target_colors.append(row_cols)

        self.target_chars = target_chars
        self.target_colors = target_colors

        # start current grids as random noise
        self.current_chars = [[random.choice(self.get_charset()) for _ in range(len(target_chars[0]))] for _ in range(len(target_chars))]
        self.current_colors = [[random.choice([self.default_fg, "#888888"]) for _ in range(len(target_chars[0]))] for _ in range(len(target_chars))]

    def draw_static_preview(self):
        # Draw target (no animation) scaled up for preview
        if self.target_chars is None:
            return
        self.canvas.delete("all")
        scale = max(4, int(self.scale_var.get()))
        rows = len(self.target_chars)
        cols = len(self.target_chars[0])
        w = cols * scale
        h = rows * scale
        self.canvas.config(scrollregion=(0,0,w,h))
        self.canvas.config(width=min(w, self.canvas.winfo_width()), height=min(h, self.canvas.winfo_height()))

        for r in range(rows):
            for c in range(cols):
                ch = self.target_chars[r][c]
                col = self.target_colors[r][c]
                if ch.strip() == "":
                    continue
                self.canvas.create_text(c*scale, r*scale, text=ch, fill=col, font=("Consolas", int(scale*0.8)), anchor="nw")
        self.canvas.update()

    def start_morph(self):
        if self.image is None:
            return
        # reprepare in case settings changed
        self.prepare_target()
        if self.target_chars is None:
            return
        if self.animating:
            return
        self.animating = True
        threading.Thread(target=self.animate, daemon=True).start()

    def animate(self):
        rows = len(self.target_chars)
        cols = len(self.target_chars[0])
        steps = 140
        for step in range(steps):
            if not self.animating:
                break
            progress = step / float(steps)
            # probability that a cell has settled to target increases with progress
            prob_settle = min(0.98, 0.02 + progress*1.6)
            # flicker probability decreases over time
            flicker = max(0.005, 0.12*(1-progress))

            for r in range(rows):
                for c in range(cols):
                    if random.random() < flicker:
                        # flicker: choose random char and random nearby color
                        self.current_chars[r][c] = random.choice(self.get_charset())
                        if self.color_mode_var.get():
                            # pick a random jitter of the target color if available
                            tr, tg, tb = self._hex_to_rgb(self.target_colors[r][c])
                            jitter = 20
                            nr = max(0, min(255, tr + random.randint(-jitter, jitter)))
                            ng = max(0, min(255, tg + random.randint(-jitter, jitter)))
                            nb = max(0, min(255, tb + random.randint(-jitter, jitter)))
                            self.current_colors[r][c] = f"#{nr:02x}{ng:02x}{nb:02x}"
                        else:
                            self.current_colors[r][c] = self.default_fg
                    elif random.random() < prob_settle:
                        self.current_chars[r][c] = self.target_chars[r][c]
                        self.current_colors[r][c] = self.target_colors[r][c]

            self.draw_current()
            time.sleep(max(0.005, float(self.speed_var.get())))

        # final pass: ensure everything matches
        for r in range(rows):
            for c in range(cols):
                self.current_chars[r][c] = self.target_chars[r][c]
                self.current_colors[r][c] = self.target_colors[r][c]
        self.draw_current()
        self.animating = False

    def draw_current(self):
        self.canvas.delete("all")
        scale = max(4, int(self.scale_var.get()))
        rows = len(self.current_chars)
        cols = len(self.current_chars[0])
        for r in range(rows):
            for c in range(cols):
                ch = self.current_chars[r][c]
                col = self.current_colors[r][c]
                if ch is None or ch == " ":
                    continue
                self.canvas.create_text(c*scale, r*scale, text=ch, fill=col, font=("Consolas", int(scale*0.8)), anchor="nw")
        self.canvas.update()

    def on_resize(self, event):
        # When window changes size, adjust preview grid if image loaded
        if self.image is None:
            return
        # slight debounce
        if hasattr(self, '_resize_after'):
            try: self.root.after_cancel(self._resize_after)
            except: pass
        self._resize_after = self.root.after(150, self.prepare_target)

    def _hex_to_rgb(self, hexc):
        hexc = hexc.lstrip('#')
        return tuple(int(hexc[i:i+2], 16) for i in (0, 2, 4))

if __name__ == "__main__":
    print("Image → Colored ASCII Morph App")
    print("Requires: Pillow. Install with: pip install pillow")
    ImageCharMorphApp()
