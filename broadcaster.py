"""
pytool_group_live_system_cbc.py
Standalone GUI tool to read local /position JSON and broadcast encrypted updates
to a websocket signal server (ws:// or wss://) using AES-CBC (PKCS7).
Saves/loads config to pos_sender_config.json
"""

import asyncio
import json
import threading
import time
import random
import hashlib
import base64
import os
from queue import Queue, Empty
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import aiohttp
import websockets
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from ctypes import windll

# ====== Configuration ======
POSITION_URL = "http://127.0.0.1:5005/position"  # local OCR/flask endpoint
CONFIG_FILE = "pos_sender_config.json"

# Defaults
DEFAULTS = {
    "signal_server": "ws://127.0.0.1:8765",
    "id": "Insaint",
    "group_name": "Fookarwi",
    "group_key_string": "this_is_32_byte_group_key_654321"
}

# ====== Helpers ======
def derive_group_id(group_name: str, key: str) -> str:
    return hashlib.sha256((group_name + key).encode("utf-8")).hexdigest()

def pad_pkcs7(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len] * pad_len)

def make_aes_key(key_string: str) -> bytes:
    """
    Ensure key is exactly 32 bytes for AES-256: pad with nulls or truncate.
    Accepts unicode input.
    """
    b = key_string.encode("utf-8")
    if len(b) < 32:
        b = b.ljust(32, b'\0')
    else:
        b = b[:32]
    return b

def encrypt_pos(pos_dict: dict, key_bytes: bytes) -> str:
    """
    Encrypt JSON payload using AES-CBC with PKCS7 padding.
    Returns base64(iv + ciphertext) as string.
    """
    data = json.dumps(pos_dict, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    data_padded = pad_pkcs7(data)
    iv = get_random_bytes(16)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(data_padded)
    return base64.b64encode(iv + ciphertext).decode("utf-8")

# ====== Networking Task (async) ======
async def fetch_position(session: aiohttp.ClientSession, log: Queue):
    try:
        async with session.get(POSITION_URL, timeout=5) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                log.put_nowait(f"{now()} [WARN] /position returned status {resp.status}")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.put_nowait(f"{now()} [ERR] fetching position: {e}")
    # Fallback empty
    return {"position": {"x":0,"y":0,"z":0}, "system": ""}

async def ws_worker(signal_server: str, ID: str, GROUP_name: str, GROUP_KEY_STRING: str, stop_event: threading.Event, log: Queue):
    """
    Main async worker: connects to the websocket server, registers, then sends
    encrypted pos updates in a loop. Reconnects on error with backoff.
    This coroutine returns when stop_event is set.
    """
    group_key = make_aes_key(GROUP_KEY_STRING)
    GROUP = derive_group_id(GROUP_name, GROUP_KEY_STRING)

    async with aiohttp.ClientSession() as session:
        backoff = 1
        while not stop_event.is_set():
            try:
                log.put_nowait(f"{now()} [INFO] Attempting connection to {signal_server}")
                # websockets.connect will handle ws:// and wss://
                async with websockets.connect(signal_server, ping_interval=10, ping_timeout=5) as ws:
                    log.put_nowait(f"{now()} [OK] Connected to signal server")
                    # send register
                    register_payload = {"type":"register","id": ID, "group": GROUP}
                    await ws.send(json.dumps(register_payload))
                    log.put_nowait(f"{now()} [SENT] register -> id={ID} group={GROUP_name}")
                    backoff = 1  # reset backoff on success

                    # loop sending position updates until disconnect or stop
                    while not stop_event.is_set():
                        try:
                            pos = await fetch_position(session, log)
                            to_send = {
                                "position": pos.get("position", {"x":0,"y":0,"z":0}),
                                "system": pos.get("system", "")
                            }
                            enc = encrypt_pos(to_send, group_key)
                            message = {"type":"pos_update","id": ID, "group": GROUP, "data": enc}
                            await ws.send(json.dumps(message))
                            log.put_nowait(f"{now()} [SENT] pos_update -> {short_pos_str(to_send)}")
                            # small jitter to desync multiple clients
                            await asyncio.sleep(3 + random.random())
                        except websockets.ConnectionClosed:
                            log.put_nowait(f"{now()} [WARN] Connection closed by server.")
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            log.put_nowait(f"{now()} [ERR] during send loop: {e}")
                            await asyncio.sleep(1)
            except asyncio.CancelledError:
                log.put_nowait(f"{now()} [INFO] Task cancelled")
                break
            except Exception as e:
                log.put_nowait(f"{now()} [ERR] Connection attempt failed: {e}")
                # Exponential-ish backoff with cap
                if stop_event.wait(min(backoff, 30)):
                    break
                backoff = min(backoff * 2, 30)
                log.put_nowait(f"{now()} [INFO] Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
        log.put_nowait(f"{now()} [INFO] ws_worker exiting")

def now():
    return datetime.now().strftime("%H:%M:%S")

def short_pos_str(pos):
    p = pos.get("position", pos)
    return f"({p.get('x')},{p.get('y')},{p.get('z')}) sys={pos.get('system','')}"

# ====== Thread wrapper to run asyncio event loop ======
def start_async_thread(signal_server, ID, GROUP_name, GROUP_KEY_STRING, stop_event: threading.Event, log: Queue):
    """
    Starts an asyncio event loop in a separate thread and runs ws_worker until stop_event is set.
    Returns the thread object.
    """
    def thread_target():
        # Create a fresh event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ws_worker(signal_server, ID, GROUP_name, GROUP_KEY_STRING, stop_event, log))
        finally:
            # ensure loop closed
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            log.put_nowait(f"{now()} [INFO] Async thread terminated")

    t = threading.Thread(target=thread_target, daemon=True)
    t.start()
    return t

class SenderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Position Broadcaster (AES-CBC)")
        self.logq = Queue()
        self.worker_thread = None
        self.stop_event = None

        # Remove native window decorations
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        self.root.attributes('-topmost', True)

        self.root.update_idletasks()   # IMPORTANT for correct hwnd

        hwnd = windll.user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TOOLWINDOW   # remove TOOLWINDOW flag
        style = style | WS_EX_APPWINDOW     # add APPWINDOW flag
        windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # Required to make Windows APPLY new style
        self.root.withdraw()
        self.root.after(10, self.root.deiconify)

        # Load config safely
        self.config = self.load_config()
        
        # Top bar with exit button
        top_bar = tk.Frame(root, bg="#0a0a0a", relief="raised", bd=0)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        
        # Inside __init__, after creating top_bar:
        top_bar.bind("<ButtonPress-1>", self.start_move)
        top_bar.bind("<ButtonRelease-1>", self.stop_move)
        top_bar.bind("<B1-Motion>", self.do_move)
        
        tk.Label(top_bar, text="Position Broadcaster", bg="#0a0a0a", fg="#00ff99", font=("Consolas", 10, "bold")).pack(side=tk.LEFT, padx=8)
        exit_btn = tk.Button(top_bar, text="✖", bg="#0a0a0a", fg="red", command=self.on_close, relief="flat", bd=0)
        exit_btn.pack(side=tk.RIGHT, padx=8)

        # Main frame
        frm = tk.Frame(root, bg="black", padx=8, pady=8)
        frm.pack(fill=tk.BOTH, expand=True)

        # Server / Identity frame
        left = tk.Frame(frm, bg="#0a0a0a")
        left.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        tk.Label(left, text="Signal server (ws:// or wss://):", bg="#0a0a0a", fg="#00ff99").pack(anchor="w")
        self.server_var = tk.StringVar(value=self.config.get("signal_server"))
        tk.Entry(left, textvariable=self.server_var, bg="black", fg="#00ff99", insertbackground="#00ff99").pack(fill=tk.X, pady=2)

        tk.Label(left, text="ID:", bg="#0a0a0a", fg="#00ff99").pack(anchor="w")
        self.id_var = tk.StringVar(value=self.config.get("id"))
        tk.Entry(left, textvariable=self.id_var, bg="black", fg="#00ff99", insertbackground="#00ff99").pack(fill=tk.X, pady=2)

        tk.Label(left, text="Group name:", bg="#0a0a0a", fg="#00ff99").pack(anchor="w")
        self.group_var = tk.StringVar(value=self.config.get("group_name"))
        tk.Entry(left, textvariable=self.group_var, bg="black", fg="#00ff99", insertbackground="#00ff99").pack(fill=tk.X, pady=2)

        tk.Label(left, text="Group key (32 chars recommended):", bg="#0a0a0a", fg="#00ff99").pack(anchor="w")
        self.key_var = tk.StringVar(value=self.config.get("group_key_string"))
        tk.Entry(left, textvariable=self.key_var, show="*", bg="black", fg="#00ff99", insertbackground="#00ff99").pack(fill=tk.X, pady=2)

        # Buttons
        btn_frame = tk.Frame(left, bg="black")
        btn_frame.pack(fill=tk.X, pady=6)
        self.start_btn = tk.Button(btn_frame, text="Start", command=self.start, bg="#003300", fg="#00ff00")
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.stop_btn = tk.Button(btn_frame, text="Stop", command=self.stop, state=tk.DISABLED, bg="#330000", fg="#ff5555")
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6,0))
        self.save_btn = tk.Button(btn_frame, text="Save Config", command=self.save_config, bg="black", fg="#00ff00")
        self.save_btn.pack(side=tk.LEFT, padx=(6,0))

        # Status & log
        right = tk.Frame(frm, bg="#0a0a0a")
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="Status:", bg="#0a0a0a", fg="#00ff00").pack(anchor="w")
        self.status_var = tk.StringVar(value="Stopped")
        tk.Label(right, textvariable=self.status_var, bg="#0a0a0a", fg="lime").pack(anchor="w", pady=(0,6))
        tk.Label(right, text="Connection Log:", bg="#0a0a0a", fg="#00ff00").pack(anchor="w")

        self.log_widget = tk.Text(right, bg="black", fg="#00ff00", insertbackground="#00ff00",
                                  font=("Consolas", 8), height=10)
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.config(state=tk.DISABLED)
        self.log_widget.configure(highlightthickness=0, bd=0)  # hide border
        self.log_widget.configure(wrap="none")  # optional: no wrapping

        # Make columns expand
        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)

        # Start draining the log queue periodically
        self.root.after(200, self.drain_log_queue)
        
        def clamp():
            self.root.update_idletasks()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x, y = self.root.winfo_x(), self.root.winfo_y()
            if x < 0 or y < 0 or x > sw - 50 or y > sh - 50:
                self.root.geometry("+100+100")

        self.root.after(200, clamp)

    # ---- Config handling ----
    def load_config(self):
        cfg = DEFAULTS.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        cfg.update(loaded)
            except Exception as e:
                print(f"Failed to load config, using defaults: {e}")
        return cfg

    def save_config(self):
        cfg = {
            "signal_server": self.server_var.get().strip(),
            "id": self.id_var.get().strip(),
            "group_name": self.group_var.get().strip(),
            "group_key_string": self.key_var.get()
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            self.log(f"{now()} [INFO] Config saved to {CONFIG_FILE}")
            messagebox.showinfo("Saved", "Configuration saved.")
        except Exception as e:
            messagebox.showerror("Save error", f"Failed to save config: {e}")

    # ---- Logging ----
    def log(self, msg: str):
        self.logq.put_nowait(msg)

    def drain_log_queue(self):
        try:
            while True:
                msg = self.logq.get_nowait()
                self.append_log(msg)
        except Empty:
            pass
        self.root.after(200, self.drain_log_queue)

    def append_log(self, text: str):
        self.log_widget.config(state=tk.NORMAL)
        self.log_widget.insert(tk.END, text + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state=tk.DISABLED)

    # ---- Worker ----
    def validate_fields(self):
        if not self.server_var.get().strip():
            messagebox.showerror("Validation error", "Signal server cannot be empty.")
            return False
        if not self.id_var.get().strip():
            messagebox.showerror("Validation error", "ID cannot be empty.")
            return False
        if not self.group_var.get().strip():
            messagebox.showerror("Validation error", "Group name cannot be empty.")
            return False
        if not self.key_var.get():
            messagebox.showerror("Validation error", "Group key cannot be empty.")
            return False
        return True

    def start(self):
        if not self.validate_fields():
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Info", "Worker already running.")
            return
        self.save_config()
        self.stop_event = threading.Event()
        self.set_status("Starting...")
        self.log(f"{now()} [INFO] Starting worker thread")
        self.worker_thread = start_async_thread(
            self.server_var.get().strip(),
            self.id_var.get().strip(),
            self.group_var.get().strip(),
            self.key_var.get(),
            self.stop_event,
            self.logq
        )
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.set_status("Running")

    def stop(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.log(f"{now()} [INFO] Worker not running")
            self.set_status("Stopped")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            return
        self.log(f"{now()} [INFO] Stopping worker...")
        self.set_status("Stopping")
        if self.stop_event:
            self.stop_event.set()

        def wait_and_cleanup():
            if self.worker_thread:
                self.worker_thread.join(timeout=5)
            self.set_status("Stopped")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.log(f"{now()} [INFO] Worker stopped")

        threading.Thread(target=wait_and_cleanup, daemon=True).start()

    def set_status(self, s: str):
        self.status_var.set(s)

    # ---- Close ----
    def on_close(self):
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno("Quit", "A worker is running. Stop and quit?"):
                return
            self.stop()
            time.sleep(0.2)
        self.root.destroy()
        
    def start_move(self, event):
        self.x_offset = event.x
        self.y_offset = event.y

    def stop_move(self, event):
        self.x_offset = None
        self.y_offset = None

    def do_move(self, event):
        x = event.x_root - self.x_offset
        y = event.y_root - self.y_offset
        self.root.geometry(f"+{x}+{y}")

# ====== Entry point ======
def main():
    root = tk.Tk()
    gui = SenderGUI(root)
    root.geometry("800x250")
    root.mainloop()

if __name__ == "__main__":
    main()
