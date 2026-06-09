
import colorsys
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError as exc:
    raise SystemExit(
        "This script requires Pillow. Install it with: pip install pillow"
    ) from exc


class PngHueShifterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PNG Hue Shifter")
        self.root.geometry("1180x760")

        self.original_image = None
        self.result_image = None
        self.preview_original = None
        self.preview_result = None
        self.loaded_path = ""

        self.mode_var = tk.StringVar(value="absolute")
        self.absolute_hue_var = tk.DoubleVar(value=290.0)
        self.delta_hue_var = tk.DoubleVar(value=120.0)
        self.skip_grayscale_var = tk.BooleanVar(value=False)
        self.alpha_threshold_var = tk.IntVar(value=0)

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="Open PNG", command=self.open_png).pack(side="left")
        ttk.Button(top, text="Apply", command=self.apply_shift).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Save As", command=self.save_png).pack(side="left", padx=(8, 0))

        self.path_label = ttk.Label(top, text="No file loaded")
        self.path_label.pack(side="left", padx=(14, 0), fill="x", expand=True)

        controls = ttk.LabelFrame(self.root, text="Hue Settings", padding=10)
        controls.pack(fill="x", padx=10, pady=(0, 10))

        mode_frame = ttk.Frame(controls)
        mode_frame.pack(fill="x")

        ttk.Radiobutton(
            mode_frame,
            text="Set absolute hue",
            variable=self.mode_var,
            value="absolute",
            command=self.apply_shift,
        ).pack(side="left")

        ttk.Radiobutton(
            mode_frame,
            text="Shift hue by delta",
            variable=self.mode_var,
            value="delta",
            command=self.apply_shift,
        ).pack(side="left", padx=(16, 0))

        absolute_row = ttk.Frame(controls)
        absolute_row.pack(fill="x", pady=(10, 0))
        ttk.Label(absolute_row, text="Absolute hue (0-360):", width=22).pack(side="left")
        absolute_scale = ttk.Scale(
            absolute_row,
            from_=0,
            to=360,
            variable=self.absolute_hue_var,
            command=self._on_slider_change,
        )
        absolute_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.absolute_entry = ttk.Entry(absolute_row, width=8, textvariable=self.absolute_hue_var)
        self.absolute_entry.pack(side="left")
        self.absolute_entry.bind("<Return>", lambda _e: self.apply_shift())

        delta_row = ttk.Frame(controls)
        delta_row.pack(fill="x", pady=(8, 0))
        ttk.Label(delta_row, text="Hue delta (-360 to 360):", width=22).pack(side="left")
        delta_scale = ttk.Scale(
            delta_row,
            from_=-360,
            to=360,
            variable=self.delta_hue_var,
            command=self._on_slider_change,
        )
        delta_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.delta_entry = ttk.Entry(delta_row, width=8, textvariable=self.delta_hue_var)
        self.delta_entry.pack(side="left")
        self.delta_entry.bind("<Return>", lambda _e: self.apply_shift())

        options_row = ttk.Frame(controls)
        options_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            options_row,
            text="Skip grayscale / low saturation pixels",
            variable=self.skip_grayscale_var,
            command=self.apply_shift,
        ).pack(side="left")

        ttk.Label(options_row, text="Alpha threshold:").pack(side="left", padx=(18, 6))
        alpha_spin = ttk.Spinbox(
            options_row,
            from_=0,
            to=255,
            width=5,
            textvariable=self.alpha_threshold_var,
            command=self.apply_shift,
        )
        alpha_spin.pack(side="left")
        alpha_spin.bind("<Return>", lambda _e: self.apply_shift())

        preview_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        preview_frame.pack(fill="both", expand=True)

        left_frame = ttk.LabelFrame(preview_frame, text="Original", padding=8)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        right_frame = ttk.LabelFrame(preview_frame, text="Result", padding=8)
        right_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.original_canvas = tk.Label(left_frame, anchor="center", bg="#202020")
        self.original_canvas.pack(fill="both", expand=True)

        self.result_canvas = tk.Label(right_frame, anchor="center", bg="#202020")
        self.result_canvas.pack(fill="both", expand=True)

        info_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        info_frame.pack(fill="x")

        self.info_label = ttk.Label(
            info_frame,
            text="Open a PNG to start. Transparency is preserved.",
        )
        self.info_label.pack(side="left")

        self.root.bind("<Configure>", self._on_resize)

    def _on_slider_change(self, _value=None) -> None:
        self.root.after_cancel(getattr(self, "_slider_job", "after#0")) if hasattr(self, "_slider_job") else None
        self._slider_job = self.root.after(120, self.apply_shift)

    def _on_resize(self, _event=None) -> None:
        if self.original_image is not None:
            self._update_previews()

    def open_png(self) -> None:
        path = filedialog.askopenfilename(
            title="Select PNG file",
            filetypes=[("PNG files", "*.png")],
        )
        if not path:
            return

        try:
            image = Image.open(path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open image:\n{exc}")
            return

        self.loaded_path = path
        self.original_image = image
        self.result_image = image.copy()
        self.path_label.config(text=path)
        self.info_label.config(text=f"Loaded: {image.width} x {image.height}")
        self._update_previews()
        self.apply_shift()

    def _display_size(self, container_width: int, container_height: int, img_width: int, img_height: int):
        if container_width <= 1 or container_height <= 1:
            return img_width, img_height
        ratio = min(container_width / img_width, container_height / img_height)
        ratio = min(ratio, 1.0)
        return max(1, int(img_width * ratio)), max(1, int(img_height * ratio))

    def _make_preview(self, image: Image.Image, target_widget: tk.Widget):
        w = max(200, target_widget.winfo_width())
        h = max(200, target_widget.winfo_height())
        new_size = self._display_size(w, h, image.width, image.height)
        preview = image.copy()
        preview.thumbnail(new_size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(preview)

    def _update_previews(self) -> None:
        if self.original_image is None:
            return

        self.preview_original = self._make_preview(self.original_image, self.original_canvas)
        self.original_canvas.configure(image=self.preview_original)

        if self.result_image is not None:
            self.preview_result = self._make_preview(self.result_image, self.result_canvas)
            self.result_canvas.configure(image=self.preview_result)

    def apply_shift(self) -> None:
        if self.original_image is None:
            return

        try:
            mode = self.mode_var.get()
            absolute_hue = float(self.absolute_hue_var.get()) % 360.0
            delta_hue = float(self.delta_hue_var.get())
            alpha_threshold = int(self.alpha_threshold_var.get())
        except ValueError:
            messagebox.showerror("Invalid value", "Hue and alpha values must be numeric.")
            return

        skip_grayscale = self.skip_grayscale_var.get()

        src = self.original_image
        pixels = list(src.getdata())
        result_pixels = []

        changed = 0
        for r, g, b, a in pixels:
            if a <= alpha_threshold:
                result_pixels.append((r, g, b, a))
                continue

            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            if skip_grayscale and s < 0.02:
                result_pixels.append((r, g, b, a))
                continue

            if mode == "absolute":
                new_h = absolute_hue / 360.0
            else:
                new_h = (h + (delta_hue / 360.0)) % 1.0

            nr, ng, nb = colorsys.hsv_to_rgb(new_h, s, v)
            rr = int(round(nr * 255.0))
            gg = int(round(ng * 255.0))
            bb = int(round(nb * 255.0))
            result_pixels.append((rr, gg, bb, a))

            if (rr, gg, bb) != (r, g, b):
                changed += 1

        result = Image.new("RGBA", src.size)
        result.putdata(result_pixels)
        self.result_image = result
        self._update_previews()

        mode_text = (
            f"absolute hue = {absolute_hue:.1f}°"
            if mode == "absolute"
            else f"delta = {delta_hue:.1f}°"
        )
        self.info_label.config(
            text=f"Pixels updated: {changed:,} | Mode: {mode_text} | Transparency preserved"
        )

    def save_png(self) -> None:
        if self.result_image is None or self.original_image is None:
            messagebox.showinfo("No image", "Open a PNG first.")
            return

        initial_name = "shifted.png"
        if self.loaded_path:
            base = os.path.splitext(os.path.basename(self.loaded_path))[0]
            initial_name = f"{base}_shifted.png"

        path = filedialog.asksaveasfilename(
            title="Save shifted PNG",
            defaultextension=".png",
            initialfile=initial_name,
            filetypes=[("PNG files", "*.png")],
        )
        if not path:
            return

        try:
            self.result_image.save(path, format="PNG")
        except Exception as exc:
            messagebox.showerror("Save error", f"Failed to save image:\n{exc}")
            return

        messagebox.showinfo("Saved", f"Saved:\n{path}")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    app = PngHueShifterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
