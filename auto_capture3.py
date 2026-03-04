import time
import threading
import re
from ctypes import windll
import copy

import pytesseract
from PIL import Image, ImageTk
import mss
import win32gui
import tkinter as tk
from flask import Flask, jsonify

# ---------------- CONFIG ----------------
pytesseract.pytesseract.tesseract_cmd = r"Tesseract-OCR\tesseract.exe"

system_keywords = ["stanton", "pyro", "nyx"]
scale = 0.94
NORMALIZED_REGIONS =[
    {"name": "line_01", "topleftx": 0.80, "toplefty": 0.002*scale, "bottomrightx": 1.0, "bottomrighty": 0.017*scale},
    {"name": "line_02", "topleftx": 0.80, "toplefty": 0.018*scale, "bottomrightx": 1.0, "bottomrighty": 0.029*scale},
    {"name": "line_03", "topleftx": 0.80, "toplefty": 0.030*scale, "bottomrightx": 1.0, "bottomrighty": 0.040*scale},
    {"name": "line_04", "topleftx": 0.80, "toplefty": 0.041*scale, "bottomrightx": 1.0, "bottomrighty": 0.052*scale},
    {"name": "line_05", "topleftx": 0.80, "toplefty": 0.052*scale, "bottomrightx": 1.0, "bottomrighty": 0.064*scale},
    {"name": "line_06", "topleftx": 0.80, "toplefty": 0.064*scale, "bottomrightx": 1.0, "bottomrighty": 0.076*scale},
    {"name": "line_07", "topleftx": 0.80, "toplefty": 0.191*scale, "bottomrightx": 1.0, "bottomrighty": 0.205*scale},
    {"name": "line_08", "topleftx": 0.80, "toplefty": 0.205*scale, "bottomrightx": 1.0, "bottomrighty": 0.218*scale},
    {"name": "line_09", "topleftx": 0.80, "toplefty": 0.217*scale, "bottomrightx": 1.0, "bottomrighty": 0.229*scale},
    {"name": "line_10", "topleftx": 0.80, "toplefty": 0.229*scale, "bottomrightx": 1.0, "bottomrighty": 0.241*scale}
]

SYSTEM_KEYWORDS = ["stanton", "pyro", "nyx"]

ocr_running = True
current_interval = 1
data_lock = threading.Lock()
ocr_lines = []
preview_images = []

last_valid_data = {
    "timestamp": None,
    "position": {"x": 0, "y": 0, "z": 0},
    "local_pos": {"x": 0, "y": 0, "z": 0},
    "system": "",
    "subsystem": "",
    "camera": {"dir": [0, 0, 0], "fov": 0, "focal": 0, "fstop": 0},
}

# ---------------- WINDOW DETECTION ----------------
def get_window_rect(title_substring="Star Citizen"):
    result = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in title.lower():
                result.append(hwnd)

    win32gui.EnumWindows(enum_handler, None)

    if not result:
        return None

    hwnd = result[0]
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return hwnd, left, top, right, bottom

# ---------------- REGION BUILD ----------------
def build_pixel_regions(win_w, win_h):
    regions = []
    for r in NORMALIZED_REGIONS:
        regions.append({
            "name": r["name"],
            "left": int(win_w * r["topleftx"]),
            "top": int(win_h * r["toplefty"]),
            "width": int(win_w * (r["bottomrightx"] - r["topleftx"])),
            "height": int(win_h * (r["bottomrighty"] - r["toplefty"]))
        })
    return regions

# ---------------- OCR HELPERS ----------------

def normalize_ocr_issues(val):
    """Normalize common OCR mistakes (e.g., 'l' -> '1', 'B' -> '8')."""
    val = val.replace('/7', '7')
    val = val.replace('/', '')
    return ''.join({'l': '1', 'B': '8', ',': '.'}.get(c, c) for c in val)
    s
def filterfunc(line_in):
    """
    OCR filter logic
    Parses CamDir, Zone, FPS, player location, and star/system names.
    """

    # Regex patterns
    pattern_CAM = r'CamDir:\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+FOV:\s*(\d+)\s+Focal:\s*([\d.]+)\s+Fstop:\s*([\d.]+)'
    pattern_Zone = r'Zone:\s*(.*?)\s+Pos:\s*(-?\d+\.\d+)(m|km)\s+(-?\d+\.\d+)(m|km)\s+(-?\d+\.\d+)(m|km)'
    pattern_FPS = r'\bFPS\b'

    # Matches
    match_CAM = re.search(pattern_CAM, line_in, re.IGNORECASE)
    match_Zone = re.search(pattern_Zone, line_in, re.IGNORECASE)
    match_FPS = re.search(pattern_FPS, line_in, re.IGNORECASE)

    # CamDir line
    if match_CAM:
        CamDirx, CamDiry, CamDirz, FOV, FOCAL, Fstop = match_CAM.groups()
        return (f"CamDir: {normalize_ocr_issues(CamDirx)} "
                f"{normalize_ocr_issues(CamDiry)} {normalize_ocr_issues(CamDirz)} "
                f"FOV: {FOV} Focal: {FOCAL} Fstop: {Fstop}")

    # Zone line
    if match_Zone:
        zone_name, x, unit1, y, unit2, z, unit3 = match_Zone.groups()
        x = normalize_ocr_issues(x)
        y = normalize_ocr_issues(y)
        z = normalize_ocr_issues(z)
        # normalize units to km if mixed
        if unit1 != unit2 or unit2 != unit3:
            if unit1 == 'm':
                x = str(float(x) / 1000)
            if unit2 == 'm':
                y = str(float(y) / 1000)
            if unit3 == 'm':
                z = str(float(z) / 1000)
            unit1 = unit2 = unit3 = 'km'
        return f"Zone: {zone_name.strip()} Pos: {x}{unit1} {y}{unit1} {z}{unit1}"

    # Skip FPS
    if match_FPS:
        return ""

    # Player location
    location_match = re.search(r'Current player location\s*:\s*([^(]+)', line_in, re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip()
        return f"Player Location: {location}"

    # Star/system detection
    if "Planet:" in line_in:
        for star in system_keywords:
            if star.lower() in line_in.lower():
                return f"Star Name: {star.capitalize()}"

    # fallback: return line as-is
    return line_in.strip()


def ocr_image(img):
    return pytesseract.image_to_string(
        img.convert("L"),
        config="--oem 3 --psm 7"
    ).strip()

# ---------------- CAPTURE ----------------
def capture_regions():
    info = get_window_rect()
    if not info:
        return []

    hwnd, wl, wt, wr, wb = info
    win_w = wr - wl
    win_h = wb - wt

    regions = build_pixel_regions(win_w, win_h)
    captured = []

    with mss.mss() as sct:
        for r in regions:
            monitor = {
                "left": wl + r["left"],
                "top": wt + r["top"],
                "width": r["width"],
                "height": r["height"]
            }
            grab = sct.grab(monitor)
            img = Image.frombytes("RGB", grab.size, grab.rgb)
            captured.append((r["name"], img))

    return captured

# ---------------- OCR LOOP ----------------
def run_ocr():
    global ocr_running, preview_images

    while True:
        if not ocr_running:
            time.sleep(0.1)
            continue

        results = []
        previews = []

        captures = capture_regions()

        for name, img in captures:
            previews.append((name, img))

            text = ocr_image(img)
            filtered = filterfunc(text)

            if not filtered:
                continue

            results.append(filtered)

            # --- Camera ---
            cam_match = re.search(
                r'CamDir:\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+FOV:\s*(\d+)\s+Focal:\s*([\d.]+)\s+Fstop:\s*([\d.]+)',
                filtered
            )
            if cam_match:
                x, y, z, fov, focal, fstop = cam_match.groups()
                last_valid_data['camera'] = {
                    'dir': [
                        int(normalize_ocr_issues(x)),
                        int(normalize_ocr_issues(y)),
                        int(normalize_ocr_issues(z))
                    ],
                    'fov': int(fov),
                    'focal': float(focal),
                    'fstop': float(fstop)
                }

            # --- Zone / position ---
            zone_match = re.search(
                r'Zone:\s*.*Pos:\s*(-?\d+\.?\d*)m?km?\s+(-?\d+\.?\d*)m?km?\s+(-?\d+\.?\d*)m?km?',
                filtered, re.I
            )
            if zone_match:
                x, y, z = map(float, zone_match.groups())
                pos = {'x': x, 'y': y, 'z': z}

                if 'Root Pos' in filtered:
                    last_valid_data['position'] = pos

            # --- System / Star ---
            sys_match = re.search(r'System:\s*(\w+)', filtered)
            if sys_match:
                last_valid_data['system'] = sys_match.group(1)

            star_match = re.search(r'Star Name:\s*(\w+)', filtered)
            if star_match:
                last_valid_data['system'] = star_match.group(1)

            # --- Player location ---
            loc_match = re.search(r'Player Location:\s*(.+)', filtered)
            if loc_match:
                last_valid_data['subsystem'] = loc_match.group(1)


        with data_lock:
            ocr_lines[:] = results
            preview_images[:] = previews
            last_valid_data["timestamp"] = time.time()

        time.sleep(current_interval)

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/position")
def position():
    with data_lock:
        return jsonify(last_valid_data)

def start_flask():
    app.run("127.0.0.1", 5005, debug=False, use_reloader=False)

# ---------------- GUI ----------------
def start_gui():
    global ocr_lines, preview_images

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#0a0a0a")

    # Taskbar presence
    hwnd = windll.user32.GetParent(root.winfo_id())
    GWL_EXSTYLE = -20
    WS_EX_APPWINDOW = 0x00040000
    style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_APPWINDOW)

    # Title bar
    bar = tk.Frame(root, bg="#0a0a0a")
    bar.pack(fill=tk.X)
    tk.Label(bar, text="Star Citizen OCR", fg="#00ff99", bg="#0a0a0a").pack(side=tk.LEFT, padx=10)
    close_btn = tk.Button(
        bar,
        text="✖",
        bg="#0a0a0a",
        fg="red",
        command=root.destroy,
        relief="flat",
        bd=0
    )
    close_btn.pack(side=tk.RIGHT, padx=10)
    # Drag
    def drag_start(e):
        root.x, root.y = e.x, e.y
    def drag(e):
        root.geometry(f"+{e.x_root - root.x}+{e.y_root - root.y}")
    bar.bind("<Button-1>", drag_start)
    bar.bind("<B1-Motion>", drag)

    # OCR Controls
    ctrl_frame = tk.Frame(root, bg="#0a0a0a")
    ctrl_frame.pack(pady=2)
    def stop_ocr(): global ocr_running; ocr_running=False; start_btn.config(state=tk.NORMAL); stop_btn.config(state=tk.DISABLED)
    def start_ocr(): global ocr_running; ocr_running=True; start_btn.config(state=tk.DISABLED); stop_btn.config(state=tk.NORMAL)

    start_btn = tk.Button(ctrl_frame, text="Start", bg="#003300", fg="#00ff00", width=10, command=start_ocr)
    start_btn.pack(side=tk.LEFT, padx=5)
    stop_btn = tk.Button(ctrl_frame, text="Stop", bg="#330000", fg="#ff5555", width=10, command=stop_ocr)
    stop_btn.pack(side=tk.LEFT, padx=5)
    start_btn.config(state=tk.DISABLED)

    # OCR Interval
    frame = tk.Frame(root, bg="#0a0a0a")
    frame.pack()
    tk.Label(frame, text="Interval:", fg="#00ff99", bg="#0a0a0a").pack(side=tk.LEFT)
    interval_var = tk.IntVar(value=current_interval)
    for val in (1,2,3):
        tk.Radiobutton(frame, text=str(val), variable=interval_var, value=val, command=lambda: set_interval(interval_var.get()),
                       bg="#0a0a0a", fg="#00ff99", selectcolor="#0a0a0a", activebackground="#0a0a0a", activeforeground="#00ff99",
                       highlightthickness=0).pack(side=tk.LEFT, padx=2)
    def set_interval(v): global current_interval; current_interval=v

    status_label = tk.Label(
        root,
        text="",
        fg="#00ffaa",
        bg="#0a0a0a",
        font=("Consolas", 8),
        justify="left",
        anchor="w"
    )
    status_label.pack(fill=tk.X, padx=10, pady=(4, 0))
    
    def format_status(data):
        cam = data["camera"]
        pos = data["position"]

        return (
            f"SYS: {data['system'] or '-'} | "
            f"LOC: {data['subsystem'] or '-'}\n"
            f"POS: x={pos['x']:.3f}  y={pos['y']:.3f}  z={pos['z']:.3f}\n"
            f"CAM: dir={cam['dir']}  FOV={cam['fov']}  "
            f"f={cam['focal']}  f/{cam['fstop']}"
        )
    def refresh_status():
        with data_lock:
            data = copy.deepcopy(last_valid_data)

        status_label.config(text=format_status(data))
        root.after(1000, refresh_status)
        
    refresh_status()
    
    # OCR Text
    text = tk.Text(root, width=130, height=11, bg="black", fg="#00ff00", font=("Consolas",8), bd=0)
    text.pack(padx=10,pady=5)
    def refresh_text():
        with data_lock:
            lines = list(ocr_lines)
        text.delete("1.0", tk.END)
        text.insert(tk.END, "\n".join(lines))
        root.after(1000, refresh_text)
    refresh_text()

    # Live Preview
    preview_frame = tk.Frame(root, bg="#0a0a0a")
    preview_frame.pack(fill=tk.BOTH, padx=0, pady=2)
    canvas = tk.Canvas(preview_frame, bg="#000000", height=280, highlightthickness=0)
    canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    preview_inner = tk.Frame(canvas, bg="#000000")
    canvas.create_window((0,0), window=preview_inner, anchor="nw")
    preview_tk_refs = []

    ZOOM_FACTOR = 0.8
    preview_widgets = {}
    
    def refresh_preview():
        with data_lock:
            imgs = list(preview_images)

        seen = set()

        for name, img in imgs:
            seen.add(name)

            new_w = int(img.width * ZOOM_FACTOR)
            new_h = int(img.height * ZOOM_FACTOR)
            img_small = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            if name not in preview_widgets:
                # --- create widgets once ---
                frame = tk.Frame(preview_inner, bg="#000000")
                frame.pack(side=tk.TOP, pady=2, fill=tk.X)

                tk.Label(
                    frame,
                    text=name,
                    fg="#00ff99",
                    bg="#000000",
                    font=("Consolas", 7),
                    anchor="w",
                    width=10
                ).pack(side=tk.LEFT, padx=(4, 8))

                tk_img = ImageTk.PhotoImage(img_small)
                img_label = tk.Label(frame, image=tk_img, bg="#000000")
                img_label.image = tk_img
                img_label.pack(side=tk.LEFT)

                preview_widgets[name] = (frame, img_label, tk_img)

            else:
                # --- update existing image ---
                frame, img_label, tk_img = preview_widgets[name]
                tk_img.paste(img_small)

        # --- remove stale widgets ---
        for name in list(preview_widgets.keys()):
            if name not in seen:
                frame, _, _ = preview_widgets.pop(name)
                frame.destroy()

        preview_inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        root.after(1000, refresh_preview)

    refresh_preview()

    root.mainloop()

# ---------------- MAIN ----------------
if __name__=="__main__":
    threading.Thread(target=run_ocr, daemon=True).start()
    threading.Thread(target=start_flask, daemon=True).start()
    start_gui()
