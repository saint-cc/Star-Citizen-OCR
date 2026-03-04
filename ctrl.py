from flask import Flask, render_template, request, jsonify
import json
import os
import threading
import time
import math
import pydirectinput
import pygetwindow as gw
import keyboard
from pynput import mouse

app = Flask(__name__)

# Target window
Target = "Star Citizen"

# Initialize variables
last_input_time = time.time()
mouse_data = []
key_data = []
keys_down = set()  # A set to store currently pressed keys
last_display_data = {"mouse": None, "keys": None}  # Store the last displayed data for comparison

# Helper function to calculate the distance between two points
def calculate_distance(point1, point2):
    return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2)

# Helper function to calculate the angle between two points in degrees
def calculate_angle(point1, point2):
    delta_x = point2[0] - point1[0]
    delta_y = point2[1] - point1[1]
    return math.degrees(math.atan2(delta_y, delta_x))

# Callback function to update last input time and record key events
def on_press(key_event):
    global last_input_time, key_data
    windows = gw.getWindowsWithTitle(Target)
    if windows:
        window = windows[0]
        if window.isActive:
            last_input_time = time.time()
            key_data.append({
                'event': 'key_down',
                'key': key_event.name,  # Use key_event.name instead of str(key)
                'timestamp': last_input_time
            })

# Callback function to update last input time and record mouse events
def on_move(x, y):
    global last_input_time, mouse_data
    windows = gw.getWindowsWithTitle(Target)
    if windows:
        window = windows[0]
        if window.isActive:
            current_time = time.time()
            if mouse_data:
                last_position = mouse_data[-1]['position']
                last_time = mouse_data[-1]['timestamp']

                # Calculate distance and time difference
                distance = calculate_distance(last_position, (x, y))
                time_difference = current_time - last_time

                # Calculate speed (pixels per second)
                speed = distance / time_difference if time_difference > 0 else 0

                # Calculate angle (degrees)
                angle = calculate_angle(last_position, (x, y))
            else:
                speed = 0
                angle = 0

            mouse_data.append({
                'event': 'move',
                'position': (x, y),
                'timestamp': current_time,
                'speed': speed,
                'angle': angle
            })
            last_input_time = current_time

def on_click(x, y, button, pressed):
    global last_input_time, mouse_data
    windows = gw.getWindowsWithTitle(Target)
    if windows:
        window = windows[0]
        if window.isActive:
            last_input_time = time.time()
            event_type = 'mouse_down' if pressed else 'mouse_up'
            mouse_data.append({
                'event': event_type,
                'position': (x, y),
                'button': str(button),
                'timestamp': last_input_time
            })

# Function to display current mouse position, keys down, speed, and angle
def display_data():
    if mouse_data:
        current_mouse_data = mouse_data[-1]
        current_mouse_pos = current_mouse_data['position']
        speed = current_mouse_data.get('speed', 0)
        angle = current_mouse_data.get('angle', 0)
    else:
        current_mouse_pos = (None, None)  # If no mouse data, set to None
        speed = 0
        angle = 0

    # A mapping from shift-modified characters to their base forms
    shift_key_map = {
        '@': '2', '#': '3', '$': '4', '%': '5', '^': '6',
        '&': '7', '*': '8', '(': '9', ')': '0',
        '_': '-', '+': '='  # Add any other mappings as needed
    }

    # Get currently pressed keys using keyboard library
    pressed_keys = []
    for key in keyboard._pressed_events.values():
        key_name = str(key.name)
        
        # If the key is alphabetic, convert it to lowercase
        if key_name.isalpha():
            key_name = key_name.lower()
        # Check if Shift is pressed and the key is in the shift_key_map
        elif keyboard.is_pressed('shift') and key_name in shift_key_map:
            key_name = shift_key_map[key_name]
        
        pressed_keys.append(key_name)

    # Print the updated state
    os.system('cls')
    print(f"[ mouse_xy: {current_mouse_pos[0]} , {current_mouse_pos[1]}, keys down: {pressed_keys}, speed: {speed:.2f} px/s, angle: {angle:.2f}° ]")

# Periodic check for data changes
def check_for_data_change():
    global last_display_data
    while True:
        current_data = {
            "mouse": mouse_data[-1] if mouse_data else None,
            "keys": [str(key.name) for key in keyboard._pressed_events.values()]
        }
        # Compare the current data with the last displayed data
        if current_data != last_display_data:
            display_data()  # Call display_data if the data has changed
            last_display_data = current_data  # Update the last displayed data
        time.sleep(0.025)  # Wait for 0.1 seconds before checking again

# Register event handlers for key press
keyboard.on_press(on_press)

# Start the listener for mouse events
mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
mouse_listener.start()

# Start the data change checker in a separate thread
threading.Thread(target=check_for_data_change, daemon=True).start()

# Function to check and switch to Star Citizen
def focus_star_citizen():
    windows = gw.getWindowsWithTitle(Target)
    print("Checking for window...")  # Debug output
    if windows:
        window = windows[0]
        print(f"Found window: {window.title}")  # Debug output
        if not window.isActive:
            print("Window is not active, activating...")  # Debug output
            window.minimize()
            time.sleep(0.2)
            window.restore()
            time.sleep(0.2)
            window.activate()
            time.sleep(0.5)  # Give some time for the window to activate
            if window.isActive:
                print("Window activated successfully.")  # Debug output
            else:
                print("Failed to activate the window.")  # Debug output
        else:
            print("Window is already active.")  # Debug output
        return True
    else:
        print("Window not found.")  # Debug output
    return False

# Function to check for inactivity and send a space if needed
def check_inactivity():
    global last_input_time
    while True:
        current_time = time.time()
        if current_time - last_input_time >= 180:  # 3 minutes
            if focus_star_citizen():
                print("Sending space key due to inactivity.")  # Debug output
                pydirectinput.press(' ')  # jump
                last_input_time = current_time  # Update last input time after sending space
        time.sleep(300)  # Check every 5 minutes

# Start the inactivity check in a separate thread
threading.Thread(target=check_inactivity, daemon=True).start()

class VKey:
    def __init__(self, key, duration=0, modifiers=None):
        self.key = key
        self.duration = duration
        self.modifiers = modifiers if modifiers else []

    def __repr__(self):
        return f"VKey(key={self.key}, duration={self.duration}, modifiers={self.modifiers})"

def hold_key(vkey):
    # Press modifiers
    for mod in vkey.modifiers:
        pydirectinput.keyDown(mod)  # Use pydirectinput to press the modifier keys

    # Press the main key
    if vkey.duration > 0:
        pydirectinput.keyDown(vkey.key)
        time.sleep(vkey.duration)
        pydirectinput.keyUp(vkey.key)
    else:
        pydirectinput.press(vkey.key)

    # Release modifiers
    for mod in vkey.modifiers:
        pydirectinput.keyUp(mod)  # Use pydirectinput to release the modifier keys

@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/submit_keys', methods=['POST'])
def submit_keys():
    key_list = request.json.get('keys', [])
    print("Received key list:")

    for key in key_list:
        print(key)

    return jsonify({"status": "success", "message": "Keys received and printed on server console"})

@app.route('/play_macro', methods=['POST'])
def play_macro():
    macro = request.json.get('keylist', [])
    time.sleep(0.2)
    try:
        if focus_star_citizen():
            print("Window focus successful")
        else:
            print("Failed to focus window")
            return jsonify({"status": "error", "message": "Could not focus window"})

        for key_data in macro:
            vkey = VKey(key_data['key'], key_data.get('duration', 0), key_data.get('modifiers', []))
            print(f"Processing VKey: {vkey}")
            hold_key(vkey)

        print("Macro executed successfully")
        return jsonify({"status": "success", "message": "Macro executed successfully"})
    except Exception as e:
        print(f"Error during macro execution: {e}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=88)