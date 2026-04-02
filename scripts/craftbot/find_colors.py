#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


SOURCE_COLORS: list[str] = [
    "#009688",
    "#26A69A",
    "#00675b",
    "#267E73",
    "0x009688",
    "0x52c7b8",
    "0xBFE1DE",
    "0xE5F0EE",
    'wxColour(0, 150, 136)',
    'wxColour(38, 166, 154)',
    'wxColour(0, 137, 123)',
    'wxColour("#BFE1DE")',
    'wxColour("#009688")',
    'wxColour(0x009688)',
    'wxColour("#E5F0EE")',
    'wxColour("#00C1AE")',
    'wxColour(0, 151, 137)',
    'wxColour(0,150, 136)',
    'wxColour(48, 221, 112)',
    'ImVec4(0, .75f, .75f, 1.f)',
    'ImVec4(0.00f, 0.59f, 0.53f, 1.00f)',
    'ImVec4(0.f / 255.f, 150.f / 255.f, 136.f / 255.f, 1.f)',
    'ImVec4(0, 0.588, 0.533, 1)',
    'ImVec4(0 / 255.0, 150 / 255.0, 136 / 255.0, 1.0)',
    'ImVec4(0.f, 150.f / 255.f, 136.f / 255.f, 0.25f)',
    'ImVec4(0.f, 150.f / 255.f, 136.f / 255.f, 0.6f)',
    '{ 0, 150.0f / 255.0f, 136.0f / 255.0f, 1.0f }',
    '{0.0f, 150.0f / 255.0f, 136.0f / 255.0f}',
    '{0.0f, 150.f / 255.0f, 136.0f / 255, 1.0f}',
    '{0.0f, 150.f / 255.0f, 136.0f / 255}',
]

SKIP_EXTENSIONS = {
    ".svg",
    ".css",
}

SKIP_DIR_NAMES = {
    ".git",
    ".idea",
    ".vs",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "out",
    "bin",
    "obj",
    "node_modules",
}

TEXT_FILE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
    ".ipp", ".inl",
    ".py",
    ".txt", ".md", ".rst",
    ".cmake",
    ".json", ".yaml", ".yml", ".toml", ".ini",
    ".vcxproj", ".filters", ".props", ".sln",
    ".ui", ".qrc",
    ".lua", ".js", ".ts",
    ".java", ".kt", ".cs", ".go", ".rs", ".swift",
    ".mm", ".m",
    ".xml",
}


def should_scan_file(path: Path, scan_all_files: bool) -> bool:
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return False
    if scan_all_files:
        return True
    return path.suffix.lower() in TEXT_FILE_EXTENSIONS or path.suffix == ""


def iter_files(root: Path, scan_all_files: bool):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if should_scan_file(path, scan_all_files):
            yield path


def read_text_safely(path: Path) -> str | None:
    encodings = ("utf-8", "utf-8-sig", "cp1250", "cp1252", "latin-1")
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding, errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
    return None


def build_pattern(source_colors: list[str], ignore_case: bool) -> re.Pattern[str]:
    escaped = sorted((re.escape(x) for x in source_colors), key=len, reverse=True)
    flags = re.MULTILINE
    if ignore_case:
        flags |= re.IGNORECASE
    return re.compile("|".join(escaped), flags)


def scan_source_colors(root: Path, ignore_case: bool, scan_all_files: bool):
    pattern = build_pattern(SOURCE_COLORS, ignore_case)

    hits: list[dict[str, object]] = []
    total_files = 0

    for file_path in iter_files(root, scan_all_files):
        total_files += 1
        text = read_text_safely(file_path)
        if text is None:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            matches = list(pattern.finditer(line))
            if not matches:
                continue

            for match in matches:
                hits.append(
                    {
                        "match": match.group(0),
                        "file": str(file_path),
                        "line": line_number,
                        "line_text": line.strip(),
                    }
                )

    hits.sort(key=lambda x: (str(x["match"]).lower(), str(x["file"]).lower(), int(x["line"])))
    return total_files, hits


def write_csv(csv_path: Path, hits: list[dict[str, object]]) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["match", "file", "line", "line_text"])
        writer.writeheader()
        writer.writerows(hits)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Source Color Finder")
        self.geometry("1200x700")

        self.root_path_var = tk.StringVar()
        self.csv_path_var = tk.StringVar(value="source_color_hits.csv")
        self.ignore_case_var = tk.BooleanVar(value=False)
        self.scan_all_files_var = tk.BooleanVar(value=False)
        self.write_csv_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls_frame, text="Root folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls_frame, textvariable=self.root_path_var, width=90).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(controls_frame, text="Browse...", command=self.browse_root_folder).grid(row=0, column=2, sticky="ew")

        ttk.Label(controls_frame, text="CSV output:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls_frame, textvariable=self.csv_path_var, width=90).grid(row=1, column=1, sticky="ew", padx=5, pady=(6, 0))
        ttk.Button(controls_frame, text="Browse...", command=self.browse_csv_file).grid(row=1, column=2, sticky="ew", pady=(6, 0))

        options_frame = ttk.Frame(controls_frame)
        options_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Checkbutton(options_frame, text="Ignore case", variable=self.ignore_case_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(options_frame, text="Scan all readable files", variable=self.scan_all_files_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(options_frame, text="Write CSV", variable=self.write_csv_var).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Button(options_frame, text="Scan", command=self.run_scan).pack(side=tk.LEFT, padx=(10, 0))

        controls_frame.columnconfigure(1, weight=1)

        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        self.summary_label = ttk.Label(summary_frame, text="No scan yet.")
        self.summary_label.pack(anchor="w")

        columns = ("match", "file", "line", "line_text")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        self.tree.heading("match", text="Match")
        self.tree.heading("file", text="File")
        self.tree.heading("line", text="Line")
        self.tree.heading("line_text", text="Line text")

        self.tree.column("match", width=220, anchor="w")
        self.tree.column("file", width=420, anchor="w")
        self.tree.column("line", width=70, anchor="center")
        self.tree.column("line_text", width=900, anchor="w")

        y_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        y_scroll.pack(fill=tk.Y, side=tk.RIGHT)
        x_scroll.pack(fill=tk.X, side=tk.BOTTOM)

        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w", relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def browse_root_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select root folder")
        if folder:
            self.root_path_var.set(folder)

    def browse_csv_file(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Select CSV output file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if file_path:
            self.csv_path_var.set(file_path)

    def clear_results(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def run_scan(self) -> None:
        root_text = self.root_path_var.get().strip()
        if not root_text:
            messagebox.showwarning("Missing folder", "Please select a root folder.")
            return

        root = Path(root_text)
        if not root.exists() or not root.is_dir():
            messagebox.showerror("Invalid folder", "The selected root folder does not exist or is not a directory.")
            return

        self.status_var.set("Scanning...")
        self.update_idletasks()

        try:
            total_files, hits = scan_source_colors(
                root=root,
                ignore_case=self.ignore_case_var.get(),
                scan_all_files=self.scan_all_files_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Scan failed", str(exc))
            self.status_var.set("Scan failed.")
            return

        self.clear_results()

        for hit in hits:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    hit["match"],
                    hit["file"],
                    hit["line"],
                    hit["line_text"],
                ),
            )

        self.summary_label.config(
            text=f"Scanned files: {total_files} | Found hits: {len(hits)}"
        )

        if self.write_csv_var.get():
            csv_text = self.csv_path_var.get().strip()
            if not csv_text:
                messagebox.showwarning("Missing CSV path", "CSV writing is enabled, but no CSV output path is set.")
            else:
                try:
                    write_csv(Path(csv_text), hits)
                except Exception as exc:
                    messagebox.showerror("CSV write failed", str(exc))
                    self.status_var.set("Scan completed, CSV write failed.")
                    return

        self.status_var.set("Scan completed.")


if __name__ == "__main__":
    app = App()
    app.mainloop()