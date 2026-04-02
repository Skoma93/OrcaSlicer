from __future__ import annotations

import colorsys
import re
import shutil
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
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


def sort_key_for_color(color: ColorKey) -> tuple[float, float, float, float, float]:
    r, g, b, a = color
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    hue, sat, val = colorsys.rgb_to_hsv(rf, gf, bf)
    is_gray = 1.0 if sat < 0.08 else 0.0
    return (is_gray, round(hue * 24), round(sat * 12), round(val * 16), a / 255.0)


class ColorRow:
    def __init__(self, parent: ttk.Frame, row_index: int, source_color: ColorKey, occurrence_count: int):
        self.source_color = source_color
        self.dest_var = tk.StringVar(value=color_to_display_string(source_color))

        self.source_canvas = tk.Canvas(parent, width=26, height=26, highlightthickness=1, highlightbackground="#666")
        self.source_canvas.grid(row=row_index, column=0, padx=(8, 6), pady=4, sticky="w")
        self.source_canvas.create_rectangle(0, 0, 26, 26, fill=color_to_preview_hex(source_color), outline="")

        self.source_label = ttk.Entry(parent, width=24)
        self.source_label.grid(row=row_index, column=1, padx=6, pady=4, sticky="ew")
        self.source_label.insert(0, color_to_display_string(source_color))
        self.source_label.config(state="readonly")

        self.count_label = ttk.Label(parent, text=str(occurrence_count), width=10)
        self.count_label.grid(row=row_index, column=2, padx=6, pady=4, sticky="w")

        self.dest_entry = ttk.Entry(parent, textvariable=self.dest_var, width=24)
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


class CssHtmlColorMapperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CSS + HTML Color Mapper")
        self.root.geometry("980x700")
        self.root.minsize(760, 500)

        self.folder_var = tk.StringVar()
        self.backup_var = tk.BooleanVar(value=True)

        self.target_files: list[Path] = []
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
        folder_entry = ttk.Entry(top_frame, textvariable=self.folder_var)
        folder_entry.grid(row=0, column=1, padx=0, pady=4, sticky="ew")

        ttk.Button(top_frame, text="Browse...", command=self.choose_folder).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Button(top_frame, text="Scan Files", command=self.scan_folder).grid(row=0, column=3, padx=(8, 0), pady=4)
        ttk.Button(top_frame, text="Apply Changes", command=self.apply_changes).grid(row=0, column=4, padx=(8, 0), pady=4)

        ttk.Checkbutton(top_frame, text="Create .bak backup", variable=self.backup_var).grid(
            row=1, column=1, padx=0, pady=(4, 0), sticky="w"
        )

        self.status_var = tk.StringVar(value="Select a folder and scan for CSS/HTML colors.")
        ttk.Label(top_frame, textvariable=self.status_var).grid(row=2, column=0, columnspan=5, pady=(8, 0), sticky="w")

        list_container = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.rowconfigure(1, weight=1)
        list_container.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(list_container)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(3, weight=1)

        headers = ["Src", "Source color", "Count", "Destination color", "Dst", "State"]
        for idx, header in enumerate(headers):
            ttk.Label(header_frame, text=header).grid(row=0, column=idx, padx=6, pady=(0, 4), sticky="w")

        self.canvas = tk.Canvas(list_container, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_frame.columnconfigure(3, weight=1)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")

        self.rows_frame.bind("<Configure>", self._on_rows_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_rows_configure(self, _event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select CSS/HTML root folder")
        if selected:
            self.folder_var.set(selected)

    def clear_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.rows.clear()
        self.color_counts.clear()

    def scan_folder(self) -> None:
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return

        folder = Path(folder_text)
        if not folder.is_dir():
            messagebox.showerror("Invalid folder", "The selected path is not a folder.")
            return

        self.clear_rows()
        self.target_files = sorted(set(list(folder.rglob("*.css")) + list(folder.rglob("*.html")) + list(folder.rglob("*.htm"))))

        if not self.target_files:
            self.status_var.set("No .css/.html/.htm files found.")
            messagebox.showinfo("No files", "No .css, .html or .htm files were found in the selected folder.")
            return

        for target_file in self.target_files:
            self._scan_single_file(target_file)

        if not self.color_counts:
            self.status_var.set(f"Scanned {len(self.target_files)} CSS/HTML files, but no supported colors were found.")
            messagebox.showinfo("No colors found", "No supported color values were found in the CSS/HTML files.")
            return

        for index, color in enumerate(sorted(self.color_counts.keys(), key=sort_key_for_color), start=0):
            row = ColorRow(self.rows_frame, index, color, self.color_counts[color])
            self.rows[color] = row

        self.status_var.set(
            f"Found {len(self.color_counts)} unique colors across {len(self.target_files)} CSS/HTML files."
        )

    def _scan_single_file(self, target_file: Path) -> None:
        try:
            text = target_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = target_file.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                text = target_file.read_text(encoding="latin-1")
        except OSError:
            return

        for match in COLOR_TOKEN_PATTERN.finditer(text):
            token = match.group(0)
            color = parse_color(token)
            if color is not None:
                self.color_counts[color] += 1

    def build_mapping(self) -> Optional[dict[str, str]]:
        mapping: dict[str, str] = {}
        invalid_sources: list[str] = []

        for source_color, row in self.rows.items():
            source_text = color_to_display_string(source_color)
            dest_text = row.get_destination()
            if dest_text is None:
                invalid_sources.append(source_text)
                continue
            mapping[source_text.lower()] = dest_text

        if invalid_sources:
            preview = "\n".join(invalid_sources[:10])
            if len(invalid_sources) > 10:
                preview += "\n..."
            messagebox.showerror("Invalid destination colors", f"These source rows have invalid destination colors:\n\n{preview}")
            return None

        return mapping

    def apply_changes(self) -> None:
        if not self.target_files:
            messagebox.showwarning("Nothing to apply", "Please scan a folder first.")
            return

        mapping = self.build_mapping()
        if mapping is None:
            return

        changed_files = 0
        changed_occurrences = 0

        for target_file in self.target_files:
            file_changed, replacements = self._apply_to_file(target_file, mapping)
            if file_changed:
                changed_files += 1
                changed_occurrences += replacements

        self.status_var.set(
            f"Updated {changed_occurrences} color occurrences in {changed_files} CSS/HTML files."
        )
        messagebox.showinfo(
            "Done",
            f"Updated {changed_occurrences} color occurrences in {changed_files} CSS/HTML files.",
        )

    def _apply_to_file(self, target_file: Path, mapping: dict[str, str]) -> tuple[bool, int]:
        try:
            text = target_file.read_text(encoding="utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            try:
                text = target_file.read_text(encoding="utf-8-sig")
                encoding = "utf-8-sig"
            except UnicodeDecodeError:
                text = target_file.read_text(encoding="latin-1")
                encoding = "latin-1"
        except OSError:
            return (False, 0)

        replacements = 0

        def replace_match(match: re.Match[str]) -> str:
            nonlocal replacements
            token = match.group(0)
            color = parse_color(token)
            if color is None:
                return token

            key = color_to_display_string(color).lower()
            replacement = mapping.get(key)
            if replacement is None:
                return token

            replacements += 1
            return replacement

        new_text = COLOR_TOKEN_PATTERN.sub(replace_match, text)
        if new_text == text:
            return (False, 0)

        try:
            if self.backup_var.get():
                backup_path = target_file.with_suffix(target_file.suffix + ".bak")
                if not backup_path.exists():
                    shutil.copy2(target_file, backup_path)
            target_file.write_text(new_text, encoding=encoding)
        except OSError:
            return (False, 0)

        return (True, replacements)


def main() -> None:
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.1)
    except tk.TclError:
        pass
    app = CssHtmlColorMapperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
