import tkinter as tk
from tkinter import ttk
import asyncio, threading, json, random, os, base64, hashlib
from Crypto.Cipher import AES
import websockets

# ---------------- Crypto / protocol logic ----------------

def derive_group_id(group_name: str, key: str) -> str:
    return hashlib.sha256((group_name + key).encode()).hexdigest()

def encrypt_cbc_for_cryptojs(plaintext_bytes, key_bytes):
    iv = os.urandom(16)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    pad_len = 16 - (len(plaintext_bytes) % 16)
    padded = plaintext_bytes + bytes([pad_len] * pad_len)
    ciphertext = cipher.encrypt(padded)
    return base64.b64encode(iv + ciphertext).decode("utf-8")

# ---------------- Async sender ----------------

class Sender:
    def __init__(self):
        self.running = False
        self.loop = None
        self.thread = None

    async def send_loop(self, cfg):
        while self.running:
            try:
                async with websockets.connect(
                    cfg['server'], ping_interval=10, ping_timeout=5
                ) as ws:
                    await ws.send(json.dumps({
                        "type": "register",
                        "id": cfg['player'],
                        "group": cfg['group']
                    }))

                    while self.running:
                        payload_json = json.dumps({
                            "position": cfg['position'],
                            "system": cfg['system']
                        }).encode("utf-8")

                        payload = encrypt_cbc_for_cryptojs(payload_json, cfg['key'])
                        await ws.send(json.dumps({
                            "type": "pos_update",
                            "id": cfg['player'],
                            "group": cfg['group'],
                            "data": payload
                        }))
                        await asyncio.sleep(3 + random.random())
            except Exception:
                await asyncio.sleep(5)

    def start(self, cfg):
        if self.running:
            return
        self.running = True
        self.loop = asyncio.new_event_loop()

        def runner():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.send_loop(cfg))

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

# ---------------- GUI ----------------

BG = "#0a0a0a"
FG_LABEL = "#00ff99"
FG_IO = "#00ff00"
TOP_BG = "#0a0a0a"

taskbar_root = tk.Tk()
taskbar_root.withdraw()
taskbar_root.title("Dummy Player")
taskbar_root.geometry("1x1+0+0")

root = tk.Toplevel(taskbar_root)
root.geometry("390x260")
root.configure(bg=BG)
root.overrideredirect(True)

sender = Sender()

# ---------------- Top bar ----------------

top_bar = tk.Frame(root, bg=TOP_BG, height=28)
top_bar.pack(side="top", fill="x")

title_lbl = tk.Label(
    top_bar,
    text="Waypoint",
    bg=TOP_BG,
    fg=FG_LABEL,
    font=("Consolas", 10, "bold")
)
title_lbl.pack(side="left", padx=8)

def close():
    sender.stop()
    root.destroy()

exit_btn = tk.Button(
    top_bar,
    text="✖",
    bg=TOP_BG,
    fg="red",
    command=close,
    relief="flat",
    bd=0,
    highlightthickness=0
)
exit_btn.pack(side="right", padx=8)

# ---- window dragging via top bar ----

def start_move(e):
    root._drag_x = e.x_root
    root._drag_y = e.y_root

def stop_move(e):
    root._drag_x = None
    root._drag_y = None

def do_move(e):
    dx = e.x_root - root._drag_x
    dy = e.y_root - root._drag_y
    root.geometry(f"+{root.winfo_x() + dx}+{root.winfo_y() + dy}")
    root._drag_x = e.x_root
    root._drag_y = e.y_root

for w in (top_bar, title_lbl):
    w.bind("<ButtonPress-1>", start_move)
    w.bind("<ButtonRelease-1>", stop_move)
    w.bind("<B1-Motion>", do_move)

# ---------------- Main layout ----------------

content = tk.Frame(root, bg=BG)
content.pack(fill="both", expand=True)

left = tk.Frame(content, bg=BG)
right = tk.Frame(content, bg=BG)
left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

def label(parent, text):
    return tk.Label(parent, text=text, bg=BG, fg=FG_LABEL, anchor="w")

def entry(parent, width=28):
    return tk.Entry(parent, width=width, bg="#000000", fg=FG_IO, insertbackground=FG_IO)

# ---------------- Left inputs ----------------

label(left, "WebSocket URL").pack(anchor="w")
ws_entry = entry(left)
ws_entry.insert(0, "ws://172.16.3.35:8765")
ws_entry.pack(pady=(0, 8))

label(left, "Player ID").pack(anchor="w")
player_entry = entry(left)
player_entry.insert(0, "cpt BloodBeard")
player_entry.pack(pady=(0, 8))

label(left, "Group name").pack(anchor="w")
group_entry = entry(left)
group_entry.insert(0, "Fookarwi")
group_entry.pack(pady=(0, 8))

label(left, "Group key (32 bytes)").pack(anchor="w")
key_entry = entry(left)
key_entry.insert(0, "this_is_32_byte_group_key_654321")
key_entry.pack(pady=(0, 8))

# ---------------- Right inputs ----------------

label(right, "System").pack(anchor="w", pady=(1, 0))
system_var = tk.StringVar(value="pyro")
system_menu = ttk.Combobox(
    right,
    textvariable=system_var,
    values=["stanton", "pyro", "nyx"],
    state="readonly",
    width=20
)
system_menu.pack(anchor="w")

coord_frame = tk.Frame(right, bg=BG)
coord_frame.pack(anchor="nw")

coords = {}
for axis in ("x", "y", "z"):
    f = tk.Frame(coord_frame, bg=BG)
    f.pack(anchor="w", pady=5)
    label(f, axis.upper()).pack(side="left", padx=(0, 8))
    e = entry(f, width=20)
    e.insert(0, "0.0")
    e.pack(side="left")
    coords[axis] = e

# ---------------- Control buttons ----------------

btn_frame = tk.Frame(left, bg=BG)
btn_frame.pack(side="bottom", fill="x", anchor="w", pady=(10, 0))


def start():
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")

    key_string = key_entry.get()
    key = key_string.encode("utf-8").ljust(32, b"\0")[:32]

    cfg = {
        "server": ws_entry.get(),
        "player": player_entry.get(),
        "group": derive_group_id(group_entry.get(), key_string),
        "key": key,
        "system": system_var.get(),
        "position": {
            "x": float(coords['x'].get()),
            "y": float(coords['y'].get()),
            "z": float(coords['z'].get())
        }
    }
    sender.start(cfg)

def stop():
    sender.stop()
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")

start_btn = tk.Button(
    btn_frame,
    text="Start",
    bg="#003300",
    fg="#00ff00",
    width=10,
    command=start
)
stop_btn = tk.Button(
    btn_frame,
    text="Stop",
    bg="#330000",
    fg="#ff5555",
    width=10,
    command=stop,
    state="disabled"
)

start_btn.pack(side="left", padx=(0, 6))
stop_btn.pack(side="left")

# ---------------- Main loop ----------------

root.mainloop()
