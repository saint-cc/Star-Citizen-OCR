import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

from ctypes import windll

# ------------------------------
# GameLogWatcher
# ------------------------------

class GameLogWatcher:
    PREFIXES = [
        "<AttachmentReceived>",
        "<InventoryManagement>",
        "<InventoryManagementRequest>",
        "<QueryInventory>",
        "<RequestInventory>"
    ]

    HELMET_PORT_ON = "port[armor_helmet]"
    HELMET_PORT_OFF = "port[helmethook_attach]"

    SEAT_EXIT_PATTERN = "cleardriver: local client node"
    SEAT_ENTER_PATTERN = "failed to get starmap route data!"

    QT_REGEX = re.compile(r"Successfully calculated route to (\S+)")

    def __init__(self, player_name, log_path, callback, helmet_callback, seat_callback, qt_callback, exceptions=None):
        self.player_name = player_name.lower()
        self.log_path = log_path
        self.callback = callback
        self.helmet_callback = helmet_callback
        self.seat_callback = seat_callback
        self.qt_callback = qt_callback
        self.last_pos = 0
        self.helmet_state = "unknown"
        self.seat_state = "unknown"
        self.qt_state = "unknown"
        self.qt_target = None
        self.exceptions = exceptions if exceptions else []

    def check_updates(self):
        if not os.path.exists(self.log_path):
            return

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.last_pos)
                new_data = f.read()
                self.last_pos = f.tell()

            for line in new_data.splitlines():
                self.process_line(line)

        except Exception as e:
            self.callback(f"[ERROR] {e}", "red")

    def process_line(self, line):
        lower = line.lower()

        if any(ex.search(line) for ex in self.exceptions):
            return

        if "attachmentreceived" in lower and self.player_name in lower:
            if self.HELMET_PORT_ON in lower:
                self.helmet_state = "on"
                self.helmet_callback("on")
            elif any(p in lower for p in self.HELMET_PORT_OFF):
                self.helmet_state = "off"
                self.helmet_callback("off")

        if self.SEAT_EXIT_PATTERN in lower:
            self.seat_state = "not_in_seat"
            self.seat_callback("not_in_seat")
        elif self.SEAT_ENTER_PATTERN in lower:
            self.seat_state = "in_seat"
            self.seat_callback("in_seat")

        qt_match = self.QT_REGEX.search(line)
        if qt_match:
            self.qt_state = "has_target"
            self.qt_target = qt_match.group(1)
            self.qt_callback(self.qt_state, self.qt_target)

        color = "green"
        if self.player_name in lower:
            color = "white"
        if "[error]" in lower:
            color = "red"

        self.callback(line, color)

# ------------------------------
# GUI
# ------------------------------

class KillFeedGUI:
    def __init__(self, root):
        self.root = root
        root.overrideredirect(True)  # remove title bar
        root.attributes('-topmost', True)
        root.configure(bg="#0a0a0a")  # dark background
        root.geometry("800x400")
        
        self.root.update_idletasks()   # IMPORTANT for correct hwnd

        hwnd = windll.user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TOOLWINDOW   # remove TOOLWINDOW flag
        style = style | WS_EX_APPWINDOW     # add APPWINDOW flag
        windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # 🔥 Required to make Windows APPLY new style
        self.root.withdraw()
        self.root.after(10, self.root.deiconify)

        # ---------- Custom title bar ----------
        title_bar = tk.Frame(root, bg="#0a0a0a")
        title_bar.pack(fill=tk.X)

        title_label = tk.Label(title_bar, text="Log Reader", bg="#0a0a0a", fg="#00ff99")
        title_label.pack(side=tk.LEFT, padx=10)

        exit_button = tk.Button(title_bar, text="✖", bg="#0a0a0a", fg="#ff0000",
                                bd=0, highlightthickness=0, command=root.destroy)
        exit_button.pack(side=tk.RIGHT, padx=5)

        # Drag functionality
        def start_move(event):
            root.x = event.x
            root.y = event.y

        def do_move(event):
            x = event.x_root - root.x
            y = event.y_root - root.y
            root.geometry(f"+{x}+{y}")

        title_bar.bind("<Button-1>", start_move)
        title_bar.bind("<B1-Motion>", do_move)
        title_label.bind("<Button-1>", start_move)
        title_label.bind("<B1-Motion>", do_move)

        # ---------- Top frame inputs ----------
        top = tk.Frame(root, bg="#0a0a0a")
        top.pack(fill="x", padx=10, pady=5)

        tk.Label(top, text="Player Name:", bg="#0a0a0a", fg="#00ff99").grid(row=0, column=0, sticky="w")
        self.player_entry = tk.Entry(top, width=30, bg="#0a0a0a", fg="#00ff99", insertbackground="#00ff00")
        self.player_entry.grid(row=0, column=1, padx=5)

        tk.Label(top, text="Game.log Path:", bg="#0a0a0a", fg="#00ff99").grid(row=1, column=0, sticky="w")
        self.log_entry = tk.Entry(top, width=60, bg="#0a0a0a", fg="#00ff99", insertbackground="#00ff00")
        self.log_entry.grid(row=1, column=1, padx=5)

        tk.Button(top, text="Browse", bg="#0a0a0a", fg="#00ff99", command=self.browse_log).grid(row=1, column=2, padx=5)
        self.start_button = tk.Button(top, text="Start", bg="#003300", fg="#00ff00", command=self.start_watching)
        self.start_button.grid(row=0, column=3, padx=10)
        self.stop_button = tk.Button(top, text="Stop", bg="#330000", fg="#ff5555", command=self.stop_watching, state="disabled")
        self.stop_button.grid(row=1, column=3, padx=10)

        # Helmet, Seat, QT indicators
        self.helmet_label = tk.Label(top, text="Helmet: UNKNOWN", fg="gray", bg="#0a0a0a",font=("Consolas", 8))
        self.helmet_label.grid(row=0, column=4, padx=20)
        self.seat_label = tk.Label(top, text="Seat: UNKNOWN", fg="gray", bg="#0a0a0a",font=("Consolas", 8))
        self.seat_label.grid(row=1, column=4, padx=20)
        self.qt_label = tk.Label(top, text="QT: UNKNOWN", fg="gray", bg="#0a0a0a",font=("Consolas", 8) )
        self.qt_label.grid(row=2, column=4, padx=20)

        # Log display
        self.text_frame = tk.Frame(root, bg="#0a0a0a")
        self.text_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.text = tk.Text(self.text_frame, bg="black", fg="#00ff00", insertbackground="#00ff00",
                            font=("Consolas", 8), wrap="none", borderwidth=0, highlightthickness=0)
        self.text.pack(fill="both", expand=True)
        self.text.tag_config("white", foreground="white")
        self.text.tag_config("green", foreground="#00ff00")
        self.text.tag_config("red", foreground="red")
        self.text.tag_config("cyan", foreground="#00ffff")
        self.text.config(state="disabled")

        self.watcher = None
        self.running = False

    # ------------------------------
    # GUI methods
    # ------------------------------

    def browse_log(self):
        path = filedialog.askopenfilename(title="Select Game.log", filetypes=[("Log files", "*.log")])
        if path:
            self.log_entry.delete(0, "end")
            self.log_entry.insert(0, path)

    def start_watching(self):
        player_name = self.player_entry.get().strip()
        log_path = self.log_entry.get().strip()

        if not player_name or not log_path:
            messagebox.showerror("Error", "Please enter player name and log path.")
            return

        self.watcher = GameLogWatcher(
            player_name,
            log_path,
            self.add_event,
            self.update_helmet_display,
            self.update_seat_display,
            self.update_qt_display,
            exceptions=[]
        )

        self.running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.root_after_id = self.root.after(200, self.update_loop)

    def stop_watching(self):
        self.running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def update_loop(self):
        if self.running:
            self.watcher.check_updates()
            self.root.after(200, self.update_loop)

    # ------------------------------
    # Event display
    # ------------------------------

    def add_event(self, text, tag="white"):
        self.text.config(state="normal")
        self.text.insert("end", text + "\n", tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def update_helmet_display(self, state):
        if state == "on":
            self.helmet_label.config(text="Helmet: ON", fg="lime")
        elif state == "off":
            self.helmet_label.config(text="Helmet: OFF", fg="red")
        else:
            self.helmet_label.config(text="Helmet: UNKNOWN", fg="gray")

    def update_seat_display(self, state):
        if state == "in_seat":
            self.seat_label.config(text="Seat: IN SEAT", fg="lime")
        elif state == "not_in_seat":
            self.seat_label.config(text="Seat: NOT IN SEAT", fg="red")
        else:
            self.seat_label.config(text="Seat: UNKNOWN", fg="gray")

    def update_qt_display(self, state, target=None):
        if state == "has_target" and target:
            self.qt_label.config(text=f"QT: {target}", fg="#00ffff")
        else:
            self.qt_label.config(text="QT: UNKNOWN", fg="gray")

# ------------------------------
# Main
# ------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    KillFeedGUI(root)
    root.mainloop()
