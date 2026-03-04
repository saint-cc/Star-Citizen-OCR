

# Star-Citizen-OCR

Star-Citizen-OCR is a collection of Python tools for extracting in-game telemetry from **Star Citizen** and sharing it with external tools.

Attempt to read display info and forward to web starmap
## What this project does

- Captures selected HUD/debug text regions from the Star Citizen game window.
- Uses OCR (Tesseract) to parse values such as camera direction, position, and system/location context.
- Exposes the latest parsed state through a local Flask endpoint (`/position`).
- Broadcasts position/system updates to a websocket signal server, with AES-CBC encrypted payloads.
- Includes a separate Flask control app for macro playback and basic input automation workflows.

## Main scripts

- `auto_capture3.py` – OCR capture loop + local `/position` API + compact desktop UI preview.
- `broadcaster.py` – GUI broadcaster that polls `/position` and forwards encrypted updates over websocket.
- `ctrl.py` – macro/control Flask app with dashboard routes and key playback endpoints.

## Notes

- This project is primarily Windows-oriented (window focus/input capture dependencies).
- You need local runtime dependencies installed (for example: Tesseract OCR, Flask, tkinter, websocket/aiohttp stack, and related Python packages used by each script).
- The existing YouTube reference/demo:
  - https://www.youtube.com/watch?v=Zb2eGtDlaPQ
- The StarMapdemo:
  - https://starmap.cyberchaos.nl
