```python
# drone_simulation.py
# Defines the Ursina 3D drone entity for Project KINETIC HANDSHAKE.

from ursina import *
import sys
import os
import time # Required for time.dt

# --- Constants ---
GROUND_LEVEL = 0.1 # Minimum altitude the drone can reach safely
DEFAULT_HOVER_ALTITUDE = 2.0 # Altitude drone aims for after takeoff
TAKEOFF_SPEED = 1.5 # Units per second
LANDING_SPEED = 1.0 # Units per second
MOVEMENT_SPEED = 4.0 # Horizontal units per second
VERTICAL_SPEED = 2.0 # Vertical units per second when adjusting altitude
ROTATION_SPEED_PROPELLERS = 720.0 # Degrees per second for propellers visual rotation
ROTATION_SPEED_DRONE = 90.0 # Degrees per second for drone body yaw rotation
SMOOTHING_FACTOR = 5.0 # Higher value = smoother but slower interpolation for movement/rotation

# --- Drone States ---
STATE_LANDED = "landed"
STATE_TAKING_OFF = "taking_off"
STATE_HOVERING = "hovering"
STATE_MOVING = "moving"
STATE_LANDING = "landing"
STATE_ERROR = "error" # State if model loading fails

class Drone(Entity):
    """
    Represents the controllable drone in the Ursina simulation.

    Handles model loading, visual components (propellers), movement logic,
    and state management based on external commands received via control methods.
    Inherits from ursina.Entity.
    """
    def __init__(self, position=(0, GROUND_LEVEL, 0), rotation=(0, 0, 0), model_path='assets/drone_model.glb'):
        """
        Initializes the Drone entity.

        Args:
            position (tuple, optional): Initial position (x, y, z). Defaults to (0, GROUND_LEVEL, 0).
            rotation (tuple, optional): Initial rotation (x, y, z). Defaults to (0, 0, 0).
            model_path (str, optional): Relative path to the drone's 3D model file.
                                        Defaults to 'assets/drone_model.glb'.
        """
        super().__init__(
            position=position,
            rotation=rotation,
            scale=0.3 # Adjust scale based on the imported model size
        )

        # --- State Variables ---
        self.state = STATE_LANDED
        self.target_altitude = GROUND_LEVEL
        self.move_direction = Vec3(0, 0, 0) # Normalized horizontal movement direction
        self.target_rotation_y = self.rotation_y # Target yaw for smooth turning

        # --- Load Model ---
        # Construct absolute path relative to this script file
        script_dir = os.path.dirname(__file__)
        model_full_path = os.path.abspath(os.path.join(script_dir, model_path))

        self.body = None
        self.propellers = []

        try:
            if not os.path.exists(model_full_path):
                raise FileNotFoundError(f"Model file not found at {model_full_path}")

            # Load the main body model
            # Note: Ursina might load .glb differently depending on its structure.
            # If the model contains multiple meshes, they might load as children.
            # We assume a single primary mesh or handle it generically.
            self.body = Entity(
                model=model_full_path,
                # texture='white_cube', # Uncomment/change if model lacks textures/materials
                parent=self,
                # Collider choice: 'box' is faster, 'mesh' is more accurate but slower.
                # Use 'mesh' if precise interaction with the model shape is needed.
                collider='box'
            )
            print(f"Drone model loaded successfully from: {model_full_path}")

            # --- Setup Propellers ---
            # Attempt to find children named like 'propeller', otherwise create defaults.
            # This part is highly dependent on how the .glb file was exported.
            found_propellers = [child for child in self.body.children if 'propeller' in child.name.lower()]

            if found_propellers:
                 self.propellers = found_propellers
                 print(f"Found {len(self.propellers)} propeller parts in the model.")
            else:
                print("No named propeller parts found in model, creating default visual propellers.")
                # Create simple visual placeholders if no propellers are found in the model hierarchy
                # Adjust positions and scales based on your specific drone model structure
                prop_positions = [
                    Vec3(0.5, 0.1, 0.5), Vec3(-0.5, 0.1, 0.5), # Front right, front left
                    Vec3(0.5, 0.1, -0.5), Vec3(-0.5, 0.1, -0.5) # Rear right, rear left
                ]
                for pos in prop_positions:
                    prop = Entity(
                        model='cylinder', # Simple cylinder shape
                        color=color.dark_gray,
                        scale=(0.25, 0.02, 0.25), # Diameter 0.25, height 0.02
                        position=pos,
                        parent=self.body # Parent propellers to the body
                    )
                    self.propellers.append(prop)

        except FileNotFoundError as fnf_error:
            print(f"ERROR: {fnf_error}", file=sys.stderr)
            print("Ensure 'assets/drone_model.glb' exists relative to 'drone_simulation.py'.", file=sys.stderr)
            self._create_fallback_drone()
        except Exception as e:
            print(f"ERROR: Failed to load or process drone model: {e}", file=sys.stderr)
            print(f"Attempted path: {model_full_path}", file=sys.stderr)
            self._create_fallback_drone()

    def _create_fallback_drone(self):
        """Creates a simple cube as a fallback if model loading fails."""
        print("Creating fallback drone (blue cube).", file=sys.stderr)
        if self.body: # Remove partially loaded body if it exists
            destroy(self.body)
        self.body = Entity(model='cube', color=color.blue, parent=self, scale=1.0, collider='box')
        self.propellers = [] # No propellers for fallback
        self.state = STATE_ERROR


    # --- Control Methods ---

    def take_off(self):
        """Commands the drone to take off and hover at the default altitude."""
        if self.state == STATE_LANDED:
            print("Drone command: Take Off")
            self.state = STATE_TAKING_OFF
            self.target_altitude = DEFAULT_HOVER_ALTITUDE

    def land(self):
        """Commands the drone to land at its current horizontal position."""
        if self.state != STATE_LANDED and self.state != STATE_LANDING:
            print("Drone command: Land")
            self.state = STATE_LANDING
            self.target_altitude = GROUND_LEVEL
            self.move_direction = Vec3(0, 0, 0) # Stop horizontal movement

    def hover(self):
        """Commands the drone to stop horizontal movement and maintain altitude."""
        # Allow hovering from moving or even during takeoff/landing (will just maintain target alt)
        if self.state not in [STATE_LANDED, STATE_ERROR]:
             if self.state == STATE_MOVING:
                 print("Drone command: Hover")
             self.state = STATE_HOVERING
             self.move_direction = Vec3(0, 0, 0)

    def move(self, direction: Vec3):
        """
        Commands the drone to move in a specific horizontal direction.
        The drone will attempt to maintain its current target altitude.

        Args:
            direction (Vec3): A vector indicating the desired horizontal movement (x, 0, z).
                              Magnitude is ignored; only direction matters.
                              Y component is ignored.
        """
        if self.state not in [STATE_LANDED, STATE_LANDING, STATE_TAKING_OFF, STATE_ERROR]:
            # Normalize the horizontal direction vector to ensure consistent speed
            direction.y = 0
            if direction.length_squared() > 0.001: # Check if direction is non-zero
                self.move_direction = direction.normalized()
                self.state = STATE_MOVING
                # print(f"Drone command: Move towards {self.move_direction}") # Debug
            else:
                # If direction is zero vector, transition to hover
                self.hover()

    def set_target_altitude(self, altitude: float):
        """
        Sets the desired target altitude for the drone.
        The drone will smoothly move towards this altitude if flying.

        Args:
            altitude (float): The target height above the ground (y-coordinate).
        """
        if self.state not in [STATE_LANDED, STATE_LANDING, STATE_ERROR]:
            self.target_altitude = max(GROUND_LEVEL, altitude) # Prevent setting target below ground
            # print(f"Drone command: Set target altitude to {self.target_altitude:.2f}") # Debug


    # --- Update Method ---

    def update(self):
        """
        Called automatically by Ursina each frame.
        Handles drone physics simulation, movement interpolation, state transitions,
        and visual animations like propeller rotation.
        """
        if self.state == STATE_ERROR:
            return # Do nothing if the drone failed to initialize properly

        dt = time.dt # Get the time elapsed since the last frame

        # --- State Machine Logic ---

        # 1. Taking Off
        if self.state == STATE_TAKING_OFF:
            if self.y < self.target_altitude - 0.05:
                self.y = lerp(self.y, self.target_altitude, TAKEOFF_SPEED * SMOOTHING_FACTOR * dt / max(0.1, abs(self.target_altitude - self.y))) # Approach target altitude
            else:
                self.y = self.target_altitude
                self.state = STATE_HOVERING
                print("Drone reached hover altitude.")

        # 2. Landing
        elif self.state == STATE_LANDING:
            if self.y > GROUND_LEVEL + 0.05:
                 self.y = lerp(self.y, GROUND_LEVEL, LANDING_SPEED * SMOOTHING_FACTOR * dt / max(0.1, abs(GROUND_LEVEL - self.y))) # Approach ground
            else:
                self.y = GROUND_LEVEL
                self.state = STATE_LANDED
                self.move_direction = Vec3(0, 0, 0)
                print("Drone landed.")

        # 3. Moving Horizontally
        elif self.state == STATE_MOVING:
            # Calculate desired position change based on direction and speed
            move_delta = self.move_direction * MOVEMENT_SPEED * dt

            # Smoothly interpolate position horizontally
            target_x = self.x + move_delta.x
            target_z = self.z + move_delta.z
            self.x = lerp(self.x, target_x, SMOOTHING_FACTOR * dt)
            self.z = lerp(self.z, target_z, SMOOTHING_FACTOR * dt)

            # Smoothly interpolate altitude towards target altitude
            self.y = lerp(self.y, self.target_altitude, VERTICAL_SPEED * SMOOTHING_FACTOR * dt)

            # Update target yaw rotation to face movement direction
            if self.move_direction.length_squared() > 0.01:
                # Calculate angle relative to the Z-axis (forward)
                # atan2 gives the angle in radians, convert to degrees
                target_angle = -math.degrees(math.atan2(self.move_direction.x, self.move_direction.z))
                self.target_rotation_y = target_angle

        # 4. Hovering
        elif self.state == STATE_HOVERING:
            # Maintain target altitude smoothly
            self.y = lerp(self.y, self.target_altitude, VERTICAL_SPEED * SMOOTHING_FACTOR * dt)
            # Dampen any residual horizontal movement
            self.x = lerp(self.x, self.x, SMOOTHING_FACTOR * dt) # Lerp towards current position effectively stops motion
            self.z = lerp(self.z, self.z, SMOOTHING_FACTOR * dt)
            # Keep current rotation target
            self.target_rotation_y = self.rotation_y


        # --- Apply Smooth Rotation (Yaw) ---
        if self.state not in [STATE_LANDED, STATE_LANDING]:
             # Use shortest angle interpolation for yaw
             current_rot = self.rotation_y
             delta_rot = (self.target_rotation_y - current_rot + 180) % 360 - 180
             self.rotation_y = lerp(current_rot, current_rot + delta_rot, ROTATION_SPEED_DRONE * SMOOTHING_FACTOR * dt / max(1.0, abs(delta_rot)))


        # --- Propeller Animation ---
        if self.state != STATE_LANDED:
            # Rotate propellers faster if moving/taking off/landing, slower if hovering
            speed_factor = 1.5 if self.state in [STATE_MOVING, STATE_TAKING_OFF, STATE_LANDING] else 1.0
            for prop in self.propellers:
                prop.rotation_y += ROTATION_SPEED_PROPELLERS * speed_factor * dt

        # --- Ground Constraint ---
        # Ensure drone doesn't visually clip through the ground unexpectedly
        if self.y < GROUND_LEVEL and self.state != STATE_LANDING:
             self.y = GROUND_LEVEL
             # If somehow below ground while not landing, force landing state
             if self.state != STATE_LANDED:
                 print("WARN: Drone below ground level unexpectedly. Forcing landing.")
                 self.land()


# --- Example Usage (for testing this file directly) ---
if __name__ == '__main__':
    # This block allows testing the Drone class independently.
    # In the actual project, the Ursina app and drone instantiation
    # will happen in 'main.py'.
    from ursina import Ursina, Sky, EditorCamera, Grid, dedent

    app = Ursina(title='Drone Simulation Test')

    # Basic environment for testing
    ground = Entity(model='plane', scale=50, texture='grass', collider='box')
    sky = Sky()

    # Create drone instance using the class defined above
    # Place it slightly above ground level initially
    drone = Drone(position=(0, GROUND_LEVEL + 0.1, 0))

    # Simple keyboard controls for testing drone methods
    info_text = Text(origin=(-.5, .5), scale=1.0, color=color.black,
                     text=dedent("""
                        Controls:
                        Space: Take Off / Land
                        W/A/S/D: Move Horizontally
                        R: Increase Target Altitude (+1)
                        F: Decrease Target Altitude (-1)
                        Q: Stop Horizontal Movement (Hover)
                        Mouse Drag: Rotate Camera
                        Scroll Wheel: Zoom Camera
                     """).strip())

    def input(key):
        if drone.state == STATE_ERROR:
            print("Drone is in error state, controls disabled.")
            return

        if key == 'space':
            if drone.state == STATE_LANDED:
                drone.take_off()
            elif drone.state != STATE_LANDING: # Prevent landing command spam
                drone.land()
        elif key == 'w':
            drone.move(Vec3(0, 0, 1)) # Forward
        elif key == 's':
            drone.move(Vec3(0, 0, -1)) # Backward
        elif key == 'a':
            drone.move(Vec3(-1, 0, 0)) # Left
        elif key == 'd':
            drone.move(Vec3(1, 0, 0)) # Right
        elif key == 'r': # Increase altitude target
            drone.set_target_altitude(drone.target_altitude + 1)
        elif key == 'f': # Decrease altitude target
            drone.set_target_altitude(drone.target_altitude - 1)
        elif key == 'q': # Explicit hover command
            drone.hover()

    # In a real application, gesture input would call drone.move(), drone.hover(), etc.
    # This basic key release check simulates stopping movement.
    def update():
         # Check if any movement key is NOT held down while the drone is moving
         if drone.state == STATE_MOVING and not any(held_keys[k] for k in ['w', 'a', 's', 'd']):
             drone.hover() # Command hover if no movement keys are pressed

    # Use EditorCamera for easy navigation during testing
    editor_camera = EditorCamera(
        rotation=(30, -45, 0), # Initial camera angle
        distance=15,            # Initial distance from origin
        target=drone           # Make camera focus on the drone
    )
    # Allow camera to follow the drone