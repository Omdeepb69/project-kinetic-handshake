# main.py
# Project KINETIC HANDSHAKE - Main Application Entry Point

import sys
import cv2
import numpy as np
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController # For camera control if needed

# Attempt to import custom modules, provide guidance if they fail
try:
    from gesture_detector import GestureDetector
except ImportError:
    print("Error: Could not import GestureDetector from gesture_detector.py.")
    print("Please ensure 'gesture_detector.py' exists in the same directory and contains the GestureDetector class.")
    sys.exit(1)

try:
    from drone_simulation import Drone
except ImportError:
    print("Error: Could not import Drone from drone_simulation.py.")
    print("Please ensure 'drone_simulation.py' exists in the same directory and contains the Drone class.")
    sys.exit(1)

# --- Constants ---
WEBCAM_ID = 0
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
SIMULATION_VIEWPORT_WIDTH_RATIO = 0.6 # 60% for simulation
WEBCAM_VIEWPORT_WIDTH_RATIO = 1.0 - SIMULATION_VIEWPORT_WIDTH_RATIO # 40% for webcam

# --- Global Variables ---
app = None
webcam_texture = None
webcam_display = None
gesture_detector = None
drone = None
cap = None
last_gesture = None
gesture_repeat_count = 0
gesture_confirmation_threshold = 3 # Number of consecutive frames for confirmation

# --- Initialization Functions ---

def initialize_webcam():
    """Initializes the webcam capture."""
    global cap
    cap = cv2.VideoCapture(WEBCAM_ID)
    if not cap.isOpened():
        print(f"Error: Could not open webcam with ID {WEBCAM_ID}.")
        print("Please ensure a webcam is connected and the correct ID is used.")
        sys.exit(1)
    # Set desired frame width and height (optional, camera might override)
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("Webcam initialized successfully.")

def initialize_ursina():
    """Initializes the Ursina application and window."""
    global app
    app = Ursina(
        title='Project KINETIC HANDSHAKE',
        size=(WINDOW_WIDTH, WINDOW_HEIGHT),
        borderless=False,
        fullscreen=False,
        vsync=True
    )
    print("Ursina application initialized.")
    # Basic environment
    ground = Entity(model='plane', scale=(100, 1, 100), color=color.gray.darken(0.4), texture='white_cube', texture_scale=(10,10), collider='box')
    sky = Sky()
    # Optional: Add a simple camera controller for debugging/viewing
    # editor_camera = EditorCamera(enabled=True, ignore_paused=True)
    # Or a first person controller if you want to move around
    # player = FirstPersonController(position=(0, 1, -10)) # Adjust position as needed

def initialize_ui():
    """Sets up the split-screen UI."""
    global webcam_texture, webcam_display

    # Create a texture to hold the webcam feed
    # Get initial frame dimensions for texture aspect ratio
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to read initial frame from webcam.")
        # Use default dimensions if frame read fails
        frame_height, frame_width = 480, 640
    else:
        frame_height, frame_width, _ = frame.shape
        print(f"Webcam frame dimensions: {frame_width}x{frame_height}")

    webcam_texture = Texture(np.zeros((frame_height, frame_width, 3), dtype=np.uint8))

    # Calculate UI element dimensions and positions based on ratios
    webcam_panel_width = WINDOW_WIDTH * WEBCAM_VIEWPORT_WIDTH_RATIO
    webcam_panel_height = webcam_panel_width * (frame_height / frame_width) # Maintain aspect ratio

    # Ensure panel height doesn't exceed window height
    if webcam_panel_height > WINDOW_HEIGHT:
        webcam_panel_height = WINDOW_HEIGHT
        webcam_panel_width = webcam_panel_height * (frame_width / frame_height)

    # Convert pixel dimensions to Ursina's relative screen coordinates (-0.5 to 0.5)
    webcam_panel_width_norm = webcam_panel_width / WINDOW_WIDTH
    webcam_panel_height_norm = webcam_panel_height / WINDOW_HEIGHT

    # Position the webcam panel on the right side
    webcam_panel_x = 0.5 - (webcam_panel_width_norm / 2)
    webcam_panel_y = 0.5 - (webcam_panel_height_norm / 2) # Align top

    webcam_display = Panel(
        texture=webcam_texture,
        scale=(webcam_panel_width_norm, webcam_panel_height_norm),
        origin=(-0.5, 0.5), # Top-left origin
        position=(webcam_panel_x, webcam_panel_y) # Position top-right corner
    )

    # Adjust the main camera's viewport for the simulation (left side)
    # The viewport takes values from 0 to 1 for x, y, width, height
    window.main_camera.viewport_x = 0
    window.main_camera.viewport_y = 0
    window.main_camera.viewport_w = SIMULATION_VIEWPORT_WIDTH_RATIO
    window.main_camera.viewport_h = 1.0

    print("Split-screen UI initialized.")
    print(f"  Simulation Viewport: x=0, y=0, w={SIMULATION_VIEWPORT_WIDTH_RATIO:.2f}, h=1.0")
    print(f"  Webcam Panel: pos=({webcam_panel_x:.2f}, {webcam_panel_y:.2f}), scale=({webcam_panel_width_norm:.2f}, {webcam_panel_height_norm:.2f})")


# --- Main Update Function ---

def update():
    """Main update loop called every frame by Ursina."""
    global webcam_texture, gesture_detector, drone, cap, last_gesture, gesture_repeat_count

    # 1. Read Webcam Frame
    ret, frame = cap.read()
    if not ret:
        print("Warning: Failed to read frame from webcam.")
        return

    # Flip the frame horizontally for a more intuitive mirror effect
    frame = cv2.flip(frame, 1)

    # 2. Detect Gestures
    processed_frame, current_gesture, hand_landmarks = gesture_detector.detect(frame)

    # 3. Update Webcam Display in UI
    # Convert BGR (OpenCV default) to RGB for Ursina Texture
    frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
    # Update the texture data - must match original texture dimensions
    if frame_rgb.shape[0] != webcam_texture.height or frame_rgb.shape[1] != webcam_texture.width:
         # Resize if necessary (though ideally webcam resolution is stable)
         frame_rgb = cv2.resize(frame_rgb, (webcam_texture.width, webcam_texture.height))

    webcam_texture.set_pixels(frame_rgb.tobytes()) # Update texture content

    # 4. Rudimentary Gesture Adaptation/Confirmation
    if current_gesture == last_gesture and current_gesture != 'NO_HAND':
        gesture_repeat_count += 1
    else:
        last_gesture = current_gesture
        gesture_repeat_count = 0

    confirmed_gesture = 'UNKNOWN' # Default command if no gesture is confirmed
    if gesture_repeat_count >= gesture_confirmation_threshold:
        confirmed_gesture = current_gesture
        # Optional: Add visual feedback for confirmed gesture (e.g., print, change UI element color)
        # print(f"Confirmed Gesture: {confirmed_gesture}")


    # 5. Gesture-to-Command Mapping and Drone Control
    if drone:
        # Default action is usually hover if a hand is present but no specific command gesture
        if confirmed_gesture == 'UNKNOWN' and current_gesture != 'NO_HAND':
             drone.hover() # Or maintain current state? Hover seems safer.

        elif confirmed_gesture == 'HOVER': # e.g., Open Palm
            drone.hover()
        elif confirmed_gesture == 'LAND': # e.g., Fist
            drone.land()
        elif confirmed_gesture == 'TAKEOFF': # e.g., Thumbs Up (add to GestureDetector)
             drone.takeoff()
        elif confirmed_gesture == 'MOVE_FORWARD': # e.g., Pointing Forward
            drone.move('forward', 0.5) # Adjust speed as needed
        elif confirmed_gesture == 'MOVE_BACKWARD': # e.g., Pointing Backward (define gesture)
            drone.move('backward', 0.5)
        elif confirmed_gesture == 'MOVE_LEFT': # e.g., Pointing Left
            drone.move('left', 0.5)
        elif confirmed_gesture == 'MOVE_RIGHT': # e.g., Pointing Right
            drone.move('right', 0.5)
        elif confirmed_gesture == 'MOVE_UP': # e.g., Palm Up (define gesture)
            drone.move('up', 0.3)
        elif confirmed_gesture == 'MOVE_DOWN': # e.g., Palm Down (define gesture)
            drone.move('down', 0.3)
        elif confirmed_gesture == 'ROTATE_CW': # e.g., Clockwise circle (define gesture)
            drone.rotate('cw', 1.0) # Adjust speed
        elif confirmed_gesture == 'ROTATE_CCW': # e.g., Counter-Clockwise circle (define gesture)
            drone.rotate('ccw', 1.0) # Adjust speed

        # Let the drone update its physics/animation
        drone.update_drone()

    # Optional: Print detected/confirmed gesture for debugging
    # print(f"Detected: {current_gesture}, Confirmed: {confirmed_gesture}, Count: {gesture_repeat_count}")


# --- Application Execution ---

if __name__ == '__main__':
    try:
        # Initialization sequence
        initialize_webcam()
        gesture_detector = GestureDetector() # Initialize after webcam
        initialize_ursina() # Initialize Ursina before creating Ursina entities
        drone = Drone(position=(0, 5, 10)) # Create the drone instance
        initialize_ui() # Initialize UI after webcam and Ursina

        # Set the main update function
        app.update = update

        # Run the Ursina application loop
        print("Starting Project KINETIC HANDSHAKE...")
        app.run()

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if cap and cap.isOpened():
            cap.release()
            print("Webcam released.")
        cv2.destroyAllWindows()
        print("OpenCV windows destroyed.")
        print("Exiting application.")