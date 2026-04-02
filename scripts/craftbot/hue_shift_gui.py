import math
import re
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import colorsys

HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RGB_RE = re.compile(
    r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$",
    re.IGNORECASE,
)


class HueShiftApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Hue Shift GUI")
        self.root.geometry("900x650")
        self.root.minsize(760, 520)

        self.mode_var = tk.StringVar(value="set_hue")
        self.value_var = tk.DoubleVar(value=290.0)
        self.value_text_var = tk.StringVar(value="290")
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self._sync_slider_to_entry()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        intro = ttk.Label(
            main,
            text=(
                "Enter one color per line. Supported formats: #RGB, #RRGGBB, rgb(r,g,b).\n"
                "The tool keeps lightness and saturation, and changes only the hue."
            ),
            justify="left",
        )
        intro.grid(row=0, column=0, sticky="w", pady=(0, 10))

        input_frame = ttk.LabelFrame(main, text="Source colors", padding=10)
        input_frame.grid(row=1, column=0, sticky="nsew")
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        self.source_text = tk.Text(input_frame, height=8, wrap="none")
        self.source_text.grid(row=0, column=0, sticky="nsew")
        self.source_text.insert(
            "1.0",
            "#009688\n#009789\n#26A69A\n#33ABA1\n#4DB6AC\n",
        )

        input_button_frame = ttk.Frame(input_frame)
        input_button_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        input_button_frame.columnconfigure(0, weight=1)

        ttk.Button(input_button_frame, text="Pick and add color", command=self._pick_color).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(input_button_frame, text="Clear", command=self._clear_input).grid(
            row=0, column=1, sticky="e", padx=(8, 0)
        )

        control_frame = ttk.LabelFrame(main, text="Hue settings", padding=10)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(10, 10))
        control_frame.columnconfigure(2, weight=1)

        ttk.Radiobutton(
            control_frame,
            text="Set absolute hue",
            variable=self.mode_var,
            value="set_hue",
            command=self._refresh_mode_labels,
        ).grid(row=0, column=0, sticky="w")

        ttk.Radiobutton(
            control_frame,
            text="Shift hue by delta",
            variable=self.mode_var,
            value="shift_hue",
            command=self._refresh_mode_labels,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.value_label = ttk.Label(control_frame, text="Target hue (0-359):")
        self.value_label.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.value_entry = ttk.Entry(control_frame, width=10, textvariable=self.value_text_var)
        self.value_entry.grid(row=1, column=1, sticky="w", pady=(10, 0), padx=(12, 0))
        self.value_entry.bind("<Return>", self._on_entry_commit)
        self.value_entry.bind("<FocusOut>", self._on_entry_commit)

        self.value_slider = ttk.Scale(
            control_frame,
            from_=0,
            to=359,
            variable=self.value_var,
            command=self._on_slider_move,
        )
        self.value_slider.grid(row=1, column=2, sticky="ew", pady=(10, 0), padx=(12, 0))

        preset_frame = ttk.Frame(control_frame)
        preset_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(preset_frame, text="Presets:").pack(side="left")
        ttk.Button(preset_frame, text="Purple", command=lambda: self._set_value(290)).pack(side="left", padx=(8, 0))
        ttk.Button(preset_frame, text="Blue", command=lambda: self._set_value(240)).pack(side="left", padx=(8, 0))
        ttk.Button(preset_frame, text="Red", command=lambda: self._set_value(0)).pack(side="left", padx=(8, 0))
        ttk.Button(preset_frame, text="Green", command=lambda: self._set_value(120)).pack(side="left", padx=(8, 0))

        action_frame = ttk.Frame(main)
        action_frame.grid(row=3, column=0, sticky="nsew")
        action_frame.columnconfigure(0, weight=1)
        action_frame.rowconfigure(1, weight=1)

        button_row = ttk.Frame(action_frame)
        button_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(button_row, text="Apply hue change", command=self.process_colors).pack(side="left")
        ttk.Button(button_row, text="Copy mapping", command=self._copy_mapping).pack(side="left", padx=(8, 0))

        result_frame = ttk.LabelFrame(action_frame, text="Results", padding=10)
        result_frame.grid(row=1, column=0, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(result_frame)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text="Source", width=18).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Destination", width=18).grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Label(header, text="Mapping").grid(row=0, column=2, sticky="w", padx=(20, 0))

        self.canvas = tk.Canvas(result_frame, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.canvas.yview)
        y_scroll.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=y_scroll.set)

        self.result_container = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.result_container, anchor="nw")

        self.result_container.bind("<Configure>", self._on_result_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        status = ttk.Label(main, textvariable=self.status_var)
        status.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        self.result_rows = []
        self.mapping_lines = []
        self._refresh_mode_labels()

    def _clear_input(self) -> None:
        self.source_text.delete("1.0", "end")
        self._clear_results()
        self.status_var.set("Input cleared")

    def _pick_color(self) -> None:
        _, hex_color = colorchooser.askcolor(parent=self.root, title="Pick source color")
        if not hex_color:
            return
        current = self.source_text.get("1.0", "end").strip()
        if current:
            self.source_text.insert("end", f"{hex_color}\n")
        else:
            self.source_text.insert("1.0", f"{hex_color}\n")
        self.status_var.set(f"Added color: {hex_color}")

    def _set_value(self, value: float) -> None:
        self.value_var.set(float(value))
        self._sync_slider_to_entry()

    def _on_slider_move(self, _event=None) -> None:
        self._sync_slider_to_entry()

    def _sync_slider_to_entry(self) -> None:
        self.value_text_var.set(str(int(round(self.value_var.get()))))

    def _on_entry_commit(self, _event=None) -> None:
        text = self.value_text_var.get().strip()
        try:
            value = float(text)
        except ValueError:
            self._sync_slider_to_entry()
            return

        if self.mode_var.get() == "set_hue":
            value = max(0.0, min(359.0, value))
        self.value_var.set(value % 360.0)
        self._sync_slider_to_entry()

    def _refresh_mode_labels(self) -> None:
        if self.mode_var.get() == "set_hue":
            self.value_label.configure(text="Target hue (0-359):")
        else:
            self.value_label.configure(text="Hue delta in degrees:")

    def _clear_results(self) -> None:
        for row in self.result_rows:
            row.destroy()
        self.result_rows.clear()
        self.mapping_lines.clear()
        self.canvas.yview_moveto(0)

    def _on_result_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def process_colors(self) -> None:
        lines = [line.strip() for line in self.source_text.get("1.0", "end").splitlines()]
        colors = [line for line in lines if line]

        if not colors:
            messagebox.showwarning("No input", "Please enter at least one color.")
            return

        value = self.value_var.get()
        mode = self.mode_var.get()

        parsed_colors = []
        invalid_colors = []
        for color_text in colors:
            try:
                rgb = parse_color(color_text)
                parsed_colors.append((color_text, rgb))
            except ValueError:
                invalid_colors.append(color_text)

        if invalid_colors:
            messagebox.showerror(
                "Invalid color",
                "These values are invalid:\n\n" + "\n".join(invalid_colors),
            )
            return

        self._clear_results()

        for index, (source_text, rgb) in enumerate(parsed_colors):
            if mode == "set_hue":
                shifted = set_hue(rgb, value)
            else:
                shifted = shift_hue(rgb, value)

            dest_text = rgb_to_hex(shifted)
            mapping_line = f"{source_text} -> {dest_text}"
            self.mapping_lines.append(mapping_line)

            row = ttk.Frame(self.result_container, padding=(0, 6))
            row.grid(row=index, column=0, sticky="ew")
            row.columnconfigure(2, weight=1)

            source_swatch = tk.Label(row, width=4, height=2, bg=rgb_to_hex(rgb), relief="solid", bd=1)
            source_swatch.grid(row=0, column=0, sticky="w")
            ttk.Label(row, text=source_text, width=16).grid(row=0, column=1, sticky="w", padx=(8, 20))

            dest_swatch = tk.Label(row, width=4, height=2, bg=dest_text, relief="solid", bd=1)
            dest_swatch.grid(row=0, column=2, sticky="w")
            ttk.Label(row, text=dest_text, width=16).grid(row=0, column=3, sticky="w", padx=(8, 20))
            ttk.Label(row, text=mapping_line).grid(row=0, column=4, sticky="w")

            self.result_rows.append(row)

        self.status_var.set(f"Processed {len(parsed_colors)} color(s)")

    def _copy_mapping(self) -> None:
        if not self.mapping_lines:
            messagebox.showinfo("Nothing to copy", "Run the conversion first.")
            return
        text = "\n".join(self.mapping_lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_var.set("Mapping copied to clipboard")


def parse_color(text: str) -> tuple[int, int, int]:
    text = text.strip()

    if HEX_RE.fullmatch(text):
        hex_value = text[1:]
        if len(hex_value) == 3:
            hex_value = "".join(ch * 2 for ch in hex_value)
        return (
            int(hex_value[0:2], 16),
            int(hex_value[2:4], 16),
            int(hex_value[4:6], 16),
        )

    rgb_match = RGB_RE.fullmatch(text)
    if rgb_match:
        values = tuple(int(part) for part in rgb_match.groups())
        if any(value < 0 or value > 255 for value in values):
            raise ValueError("RGB value out of range")
        return values

    raise ValueError(f"Unsupported color format: {text}")


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def set_hue(rgb: tuple[int, int, int], target_hue_deg: float) -> tuple[int, int, int]:
    r, g, b = [channel / 255.0 for channel in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    new_h = (target_hue_deg % 360.0) / 360.0
    nr, ng, nb = colorsys.hls_to_rgb(new_h, l, s)
    return (
        int(round(nr * 255)),
        int(round(ng * 255)),
        int(round(nb * 255)),
    )


def shift_hue(rgb: tuple[int, int, int], delta_deg: float) -> tuple[int, int, int]:
    r, g, b = [channel / 255.0 for channel in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    new_h = (h + (delta_deg / 360.0)) % 1.0
    nr, ng, nb = colorsys.hls_to_rgb(new_h, l, s)
    return (
        int(round(nr * 255)),
        int(round(ng * 255)),
        int(round(nb * 255)),
    )


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    app = HueShiftApp(root)
    root.mainloop()
