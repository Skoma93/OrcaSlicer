from __future__ import annotations

import colorsys
import re
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from collections import Counter
from typing import Optional


HEX_PATTERN = r"(?:#[0-9A-Fa-f]{8}\b|#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{4}\b|#[0-9A-Fa-f]{3}\b)"
RGB_PATTERN = (
    r"(?:rgba?\(\s*"
    r"(?:[0-9]{1,3}%?)\s*,\s*"
    r"(?:[0-9]{1,3}%?)\s*,\s*"
    r"(?:[0-9]{1,3}%?)"
    r"(?:\s*,\s*(?:0|1|0?\.\d+|[0-9]{1,3}%))?"
    r"\s*\))"
)
COLOR_TOKEN_PATTERN = re.compile(rf"{HEX_PATTERN}|{RGB_PATTERN}", re.IGNORECASE)


ColorKey = tuple[int, int, int, int]


def clamp_byte(value: float) -> int:
    return max(0, min(255, int(round(value))))


def parse_channel(value: str) -> Optional[int]:
    value = value.strip()
    if value.endswith("%"):
        try:
            percent = float(value[:-1])
        except ValueError:
            return None
        return clamp_byte(percent * 255.0 / 100.0)

    try:
        numeric = float(value)
    except ValueError:
        return None

    return clamp_byte(numeric)


def parse_alpha(value: str) -> Optional[int]:
    value = value.strip()
    if value.endswith("%"):
        try:
            percent = float(value[:-1])
        except ValueError:
            return None
        return clamp_byte(percent * 255.0 / 100.0)

    try:
        numeric = float(value)
    except ValueError:
        return None

    if numeric <= 1.0:
        return clamp_byte(numeric * 255.0)
    return clamp_byte(numeric)


def parse_hex_color(token: str) -> Optional[ColorKey]:
    token = token.strip().lstrip("#")

    if len(token) == 3:
        r, g, b = (int(ch * 2, 16) for ch in token)
        return (r, g, b, 255)
    if len(token) == 4:
        r, g, b, a = (int(ch * 2, 16) for ch in token)
        return (r, g, b, a)
    if len(token) == 6:
        return (int(token[0:2], 16), int(token[2:4], 16), int(token[4:6], 16), 255)
    if len(token) == 8:
        return (
            int(token[0:2], 16),
            int(token[2:4], 16),
            int(token[4:6], 16),
            int(token[6:8], 16),
        )
    return None


def parse_rgb_color(token: str) -> Optional[ColorKey]:
    match = re.fullmatch(
        r"rgba?\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,\)]+)(?:\s*,\s*([^\)]+))?\s*\)",
        token,
        re.IGNORECASE,
    )
    if not match:
        return None

    r = parse_channel(match.group(1))
    g = parse_channel(match.group(2))
    b = parse_channel(match.group(3))
    a = 255 if match.group(4) is None else parse_alpha(match.group(4))

    if None in (r, g, b, a):
        return None

    return (r, g, b, a)


def parse_color(token: str) -> Optional[ColorKey]:
    token = token.strip()
    if not token:
        return None

    if token.startswith("#"):
        return parse_hex_color(token)

    if token.lower().startswith("rgb"):
        return parse_rgb_color(token)

    return None


def color_to_preview_hex(color: ColorKey) -> str:
    r, g, b, _ = color
    return f"#{r:02X}{g:02X}{b:02X}"


def format_alpha(alpha: int) -> str:
    value = alpha / 255.0
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def color_to_display_string(color: ColorKey) -> str:
    r, g, b, a = color
    if a == 255:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"rgba({r}, {g}, {b}, {format_alpha(a)})"


def color_similarity_sort_key(color: ColorKey) -> tuple[float, float, float, int]:
    r, g, b, a = color

    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0

    hue, saturation, value = colorsys.rgb_to_hsv(rf, gf, bf)

    if saturation < 0.08:
        return (2.0, value, 0.0, a)

    hue_bucket = round(hue * 24) / 24.0
    value_bucket = round(value * 12) / 12.0
    return (hue_bucket, -saturation, value_bucket, a)


def should_skip_hex_match(text: str, start_index: int) -> bool:
    prefix = text[max(0, start_index - 16):start_index].lower()
    return bool(re.search(r"url\(\s*$", prefix))


class ColorRow:
    def __init__(self, parent: ttk.Frame, row_index: int, source_color: ColorKey, occurrence_count: int):
        self.source_color = source_color
        self.dest_var = tk.StringVar(value=color_to_display_string(source_color))

        self.source_canvas = tk.Canvas(parent, width=26, height=26, highlightthickness=1, highlightbackground="#666")
        self.source_canvas.grid(row=row_index, column=0, padx=(8, 6), pady=4, sticky="w")
        self.source_canvas.create_rectangle(0, 0, 26, 26, fill=color_to_preview_hex(source_color), outline="")

        self.source_label = ttk.Label(parent, text=color_to_display_string(source_color), width=22)
        self.source_label.grid(row=row_index, column=1, padx=6, pady=4, sticky="w")

        self.count_label = ttk.Label(parent, text=str(occurrence_count), width=10)
        self.count_label.grid(row=row_index, column=2, padx=6, pady=4, sticky="w")

        self.dest_entry = ttk.Entry(parent, textvariable=self.dest_var, width=22)
        self.dest_entry.grid(row=row_index, column=3, padx=6, pady=4, sticky="ew")

        self.dest_canvas = tk.Canvas(parent, width=26, height=26, highlightthickness=1, highlightbackground="#666")
        self.dest_canvas.grid(row=row_index, column=4, padx=6, pady=4, sticky="w")

        self.status_label = ttk.Label(parent, text="", width=12)
        self.status_label.grid(row=row_index, column=5, padx=(6, 8), pady=4, sticky="w")

        self.dest_var.trace_add("write", self._refresh_dest_preview)
        self._refresh_dest_preview()

    def _refresh_dest_preview(self, *_args) -> None:
        self.dest_canvas.delete("all")
        raw_value = self.dest_var.get().strip()
        parsed = parse_color(raw_value)

        if parsed is None:
            self.dest_canvas.create_rectangle(0, 0, 26, 26, fill="#FFFFFF", outline="")
            self.dest_canvas.create_line(2, 2, 24, 24, width=2, fill="#CC0000")
            self.dest_canvas.create_line(24, 2, 2, 24, width=2, fill="#CC0000")
            self.status_label.config(text="Invalid", foreground="#CC0000")
            return

        self.dest_canvas.create_rectangle(0, 0, 26, 26, fill=color_to_preview_hex(parsed), outline="")
        self.status_label.config(text="OK", foreground="#007700")

    def get_destination(self) -> Optional[str]:
        value = self.dest_var.get().strip()
        if not value:
            return None
        if parse_color(value) is None:
            return None
        return value


class SvgColorMapperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SVG Color Mapper")
        self.root.geometry("980x700")
        self.root.minsize(760, 500)

        self.folder_var = tk.StringVar()
        self.backup_var = tk.BooleanVar(value=True)

        self.svg_files: list[Path] = []
        self.rows: dict[ColorKey, ColorRow] = {}
        self.color_counts: Counter[ColorKey] = Counter()

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self.root, padding=12)
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="Folder:").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
        ttk.Entry(top_frame, textvariable=self.folder_var).grid(row=0, column=1, padx=0, pady=4, sticky="ew")
        ttk.Button(top_frame, text="Browse...", command=self.select_folder).grid(row=0, column=2, padx=8, pady=4)
        ttk.Button(top_frame, text="Scan SVG files", command=self.scan_folder).grid(row=0, column=3, padx=(0, 8), pady=4)
        ttk.Button(top_frame, text="Apply changes", command=self.apply_changes).grid(row=0, column=4, pady=4)

        ttk.Checkbutton(top_frame, text="Create .bak backups", variable=self.backup_var).grid(
            row=1, column=1, padx=0, pady=(6, 0), sticky="w"
        )

        content_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(content_frame, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.columnconfigure(3, weight=1)

        self.canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.results_canvas = canvas

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.results_canvas.bind("<Configure>", self._on_canvas_configure)
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_table_header()

        bottom_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        bottom_frame.grid(row=2, column=0, sticky="ew")
        bottom_frame.columnconfigure(0, weight=1)

        self.summary_label = ttk.Label(bottom_frame, text="Select a folder and scan for SVG colors.")
        self.summary_label.grid(row=0, column=0, sticky="w")

        self.log_text = tk.Text(bottom_frame, height=10, wrap="word")
        self.log_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.log_text.configure(state="disabled")

    def _build_table_header(self) -> None:
        header_style = {"padding": (8, 6)}
        ttk.Label(self.scrollable_frame, text="Source", **header_style).grid(row=0, column=0, sticky="w")
        ttk.Label(self.scrollable_frame, text="Source value", **header_style).grid(row=0, column=1, sticky="w")
        ttk.Label(self.scrollable_frame, text="Count", **header_style).grid(row=0, column=2, sticky="w")
        ttk.Label(self.scrollable_frame, text="Destination value", **header_style).grid(row=0, column=3, sticky="w")
        ttk.Label(self.scrollable_frame, text="Dest", **header_style).grid(row=0, column=4, sticky="w")
        ttk.Label(self.scrollable_frame, text="State", **header_style).grid(row=0, column=5, sticky="w")

    def _clear_rows(self) -> None:
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.rows.clear()
        self._build_table_header()

    def _on_frame_configure(self, _event=None) -> None:
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.results_canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.results_canvas.winfo_exists():
            self.results_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def select_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select SVG root folder")
        if selected:
            self.folder_var.set(selected)

    def scan_folder(self) -> None:
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        folder = Path(folder_text)
        if not folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected path is not a valid folder.")
            return

        self._clear_rows()
        self.svg_files = []
        self.color_counts = Counter()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        self.log(f"Scanning: {folder}")
        self.svg_files = sorted(folder.rglob("*.svg"))

        if not self.svg_files:
            self.summary_label.config(text="No SVG files were found.")
            self.log("No .svg files found in the selected folder or subfolders.")
            return

        for svg_file in self.svg_files:
            try:
                text = svg_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self.log(f"Skipped {svg_file}: {exc}")
                continue

            for match in COLOR_TOKEN_PATTERN.finditer(text):
                token = match.group(0)
                if token.startswith("#") and should_skip_hex_match(text, match.start()):
                    continue
                parsed = parse_color(token)
                if parsed is not None:
                    self.color_counts[parsed] += 1

        if not self.color_counts:
            self.summary_label.config(text=f"{len(self.svg_files)} SVG files found, but no supported colors were detected.")
            self.log("No supported colors were found. Supported formats: #RGB, #RGBA, #RRGGBB, #RRGGBBAA, rgb(), rgba().")
            return

        sorted_colors = sorted(self.color_counts.items(), key=lambda item: color_similarity_sort_key(item[0]))
        for row_index, (color_key, occurrence_count) in enumerate(sorted_colors, start=1):
            self.rows[color_key] = ColorRow(self.scrollable_frame, row_index, color_key, occurrence_count)

        self.summary_label.config(
            text=f"Found {len(self.color_counts)} unique colors in {len(self.svg_files)} SVG files."
        )
        self.log(f"Found {len(self.color_counts)} unique colors in {len(self.svg_files)} files.")

    def apply_changes(self) -> None:
        if not self.svg_files:
            messagebox.showwarning("Nothing to apply", "Scan a folder before applying changes.")
            return

        destination_map: dict[ColorKey, str] = {}
        invalid_sources: list[str] = []

        for source_color, row in self.rows.items():
            destination = row.get_destination()
            if destination is None:
                invalid_sources.append(color_to_display_string(source_color))
            else:
                destination_map[source_color] = destination

        if invalid_sources:
            preview = ", ".join(invalid_sources[:5])
            extra = "" if len(invalid_sources) <= 5 else f" and {len(invalid_sources) - 5} more"
            messagebox.showerror("Invalid destination colors", f"Fix invalid destination values: {preview}{extra}")
            return

        should_continue = messagebox.askyesno(
            "Apply changes",
            f"This will update colors in {len(self.svg_files)} SVG files. Continue?",
        )
        if not should_continue:
            return

        files_changed = 0
        total_replacements = 0

        for svg_file in self.svg_files:
            try:
                original_text = svg_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self.log(f"Skipped {svg_file}: {exc}")
                continue

            replacements_in_file = 0

            def replace_match(match: re.Match[str]) -> str:
                nonlocal replacements_in_file
                token = match.group(0)
                if token.startswith("#") and should_skip_hex_match(original_text, match.start()):
                    return token

                parsed = parse_color(token)
                if parsed is None:
                    return token

                replacement = destination_map.get(parsed)
                if replacement is None:
                    return token

                if replacement == token:
                    return token

                replacements_in_file += 1
                return replacement

            updated_text = COLOR_TOKEN_PATTERN.sub(replace_match, original_text)

            if replacements_in_file == 0 or updated_text == original_text:
                continue

            try:
                if self.backup_var.get():
                    backup_file = svg_file.with_suffix(svg_file.suffix + ".bak")
                    shutil.copyfile(svg_file, backup_file)
                svg_file.write_text(updated_text, encoding="utf-8", newline="")
            except OSError as exc:
                self.log(f"Failed to write {svg_file}: {exc}")
                continue

            files_changed += 1
            total_replacements += replacements_in_file
            self.log(f"Updated {svg_file} ({replacements_in_file} replacements)")

        self.summary_label.config(
            text=f"Done. Updated {files_changed} files with {total_replacements} replacements."
        )
        self.log(f"Done. Updated {files_changed} files with {total_replacements} replacements.")
        messagebox.showinfo("Finished", f"Updated {files_changed} files with {total_replacements} replacements.")


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = SvgColorMapperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
