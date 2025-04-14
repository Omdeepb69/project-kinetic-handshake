# drone_simulation.py
# Updated implementation to integrate with main.py and gesture_detector.py

from ursina import *
import math
import time

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

    Handles model creation, visual components (propellers), movement logic,
    and state management based on external commands received via control methods.
    Inherits from ursina.Entity.
    """
    def __init__(self, position=(0, GROUND_LEVEL, 0), rotation=(0, 0, 0)):
        """
        Initializes the Drone entity with a custom 3D model built from primitives.

        Args:
            position (tuple, optional): Initial position (x, y, z). Defaults to (0, GROUND_LEVEL, 0).
            rotation (tuple, optional): Initial rotation (x, y, z). Defaults to (0, 0, 0).
        """
        super().__init__(
            position=position,
            rotation=rotation,
            scale=1.0
        )

        # --- State Variables ---
        self.state = STATE_LANDED
        self.target_altitude = GROUND_LEVEL
        self.move_direction = Vec3(0, 0, 0) # Normalized horizontal movement direction
        self.target_rotation_y = self.rotation_y # Target yaw for smooth turning
        self.vertical_direction = 0  # -1 for down, 0 for maintain, 1 for up

        # --- Create 3D Model ---
        self.create_drone_model()

    def create_drone_model(self):
        """Creates a detailed 3D drone model using Ursina primitives."""
        # Create the main body (center) of the drone
        self.body = Entity(
            parent=self,
            model='cube',
            color=color.dark_gray,
            scale=(0.5, 0.15, 0.5)
        )
        
        # Create the arms of the drone
        arm_length = 0.4
        arm_width = 0.05
        arm_positions = [
            (arm_length/2, 0, arm_length/2),  # Front-Right
            (arm_length/2, 0, -arm_length/2), # Back-Right
            (-arm_length/2, 0, arm_length/2), # Front-Left
            (-arm_length/2, 0, -arm_length/2) # Back-Left
        ]
        
        # Create the four arms
        self.arms = []
        for i, pos in enumerate(arm_positions):
            # Determine arm rotation angle
            arm_angle = i * 90
            
            # Create the arm
            arm = Entity(
                parent=self,
                model='cube',
                color=color.gray,
                position=pos,
                scale=(arm_width, 0.05, arm_length if i % 2 == 0 else arm_width),
                rotation_y=arm_angle if i % 2 else 0
            )
            self.arms.append(arm)
        
        # Create the propellers
        self.propellers = []
        propeller_positions = [
            (arm_length, 0, arm_length),    # Front-Right
            (arm_length, 0, -arm_length),   # Back-Right
            (-arm_length, 0, arm_length),   # Front-Left
            (-arm_length, 0, -arm_length)   # Back-Left
        ]
        
        for i, pos in enumerate(propeller_positions):
            # Alternate propeller colors for better visibility
            propeller_color = color.red if i % 2 == 0 else color.blue
            
            # Create propeller motor (the center cylinder)
            motor = Entity(
                parent=self,
                model='cylinder',
                color=color.dark_gray,
                position=pos,
                scale=(0.1, 0.05, 0.1),
                rotation_x=90
            )
            
            # Create propeller blades
            propeller = Entity(
                parent=motor,
                model='cube',
                color=propeller_color,
                position=(0, 0.05, 0),
                scale=(0.3, 0.01, 0.05)
            )
            
            # Add a perpendicular blade
            propeller2 = Entity(
                parent=motor,
                model='cube',
                color=propeller_color,
                position=(0, 0.05, 0),
                scale=(0.05, 0.01, 0.3)
            )
            
            self.propellers.append((motor, propeller, propeller2))
        
        # Add some details to the body
        self.camera = Entity(
            parent=self.body,
            model='sphere',
            color=color.black,
            scale=(0.2, 0.2, 0.2),
            position=(0, -0.1, 0.25)
        )
        
        # Add landing gear
        leg_height = 0.2
        for i in range(4):
            x = 0.2 if i < 2 else -0.2
            z = 0.2 if i % 2 == 0 else -0.2
            
            leg = Entity(
                parent=self,
                model='cube',
                color=color.dark_gray,
                position=(x, -leg_height/2, z),
                scale=(0.05, leg_height, 0.05)
            )
            
            foot = Entity(
                parent=leg,
                model='sphere',
                color=color.gray,
                position=(0, -leg_height/2, 0),
                scale=(0.08, 0.08, 0.08)
            )

    # --- Control Methods ---

    def take_off(self):
        """Commands the drone to take off and hover at the default altitude."""
        if self.state == STATE_LANDED:
            print("Drone command: Take Off")
            self.state = STATE_TAKING_OFF
            self.target_altitude = DEFAULT_HOVER_ALTITUDE

    def takeoff(self):
        """Alias for take_off() for API compatibility."""
        self.take_off()

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
            self.vertical_direction = 0  # Stop vertical movement

    def move(self, direction, speed=0.5):
        """
        Commands the drone to move in a specific direction.
        This version supports both Vec3 objects and string direction names.

        Args:
            direction: Either a Vec3 object or a string ('forward', 'backward', 'left', 'right', 'up', 'down')
            speed (float, optional): Movement speed factor. Defaults to 0.5.
        """
        if self.state not in [STATE_LANDED, STATE_LANDING, STATE_TAKING_OFF, STATE_ERROR]:
            # Handle string direction inputs (from main.py)
            if isinstance(direction, str):
                if direction.lower() == 'forward':
                    self.move_direction = Vec3(0, 0, 1).normalized() * speed
                    self.state = STATE_MOVING
                elif direction.lower() == 'backward':
                    self.move_direction = Vec3(0, 0, -1).normalized() * speed
                    self.state = STATE_MOVING
                elif direction.lower() == 'left':
                    self.move_direction = Vec3(-1, 0, 0).normalized() * speed
                    self.state = STATE_MOVING
                elif direction.lower() == 'right':
                    self.move_direction = Vec3(1, 0, 0).normalized() * speed
                    self.state = STATE_MOVING
                elif direction.lower() == 'up':
                    self.vertical_direction = 1
                    self.target_altitude += VERTICAL_SPEED * speed
                    self.target_altitude = max(GROUND_LEVEL, self.target_altitude)
                elif direction.lower() == 'down':
                    self.vertical_direction = -1
                    self.target_altitude -= VERTICAL_SPEED * speed
                    self.target_altitude = max(GROUND_LEVEL, self.target_altitude)
            # Handle Vec3 direction inputs (from original drone_simulation.py)
            elif isinstance(direction, Vec3):
                direction.y = 0  # Ensure horizontal movement only
                if direction.length_squared() > 0.001:  # Check if direction is non-zero
                    self.move_direction = direction.normalized() * speed
                    self.state = STATE_MOVING
                else:
                    # If direction is zero vector, transition to hover
                    self.hover()

    def rotate(self, direction, speed=1.0):
        """
        Commands the drone to rotate in place.

        Args:
            direction (str): Either 'cw' (clockwise) or 'ccw' (counter-clockwise).
            speed (float, optional): Rotation speed factor. Defaults to 1.0.
        """
        if self.state not in [STATE_LANDED, STATE_LANDING, STATE_TAKING_OFF, STATE_ERROR]:
            if direction.lower() == 'cw':
                self.target_rotation_y = (self.rotation_y - 45 * speed) % 360
            elif direction.lower() == 'ccw':
                self.target_rotation_y = (self.rotation_y + 45 * speed) % 360

    def set_target_altitude(self, altitude: float):
        """
        Sets the desired target altitude for the drone.
        The drone will smoothly move towards this altitude if flying.

        Args:
            altitude (float): The target height above the ground (y-coordinate).
        """
        if self.state not in [STATE_LANDED, STATE_LANDING, STATE_ERROR]:
            self.target_altitude = max(GROUND_LEVEL, altitude) # Prevent setting target below ground

    def update_drone(self):
        """Legacy method for compatibility with main.py - calls update()"""
        self.update()

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
            for motor, _, _ in self.propellers:
                motor.rotation_y += ROTATION_SPEED_PROPELLERS * speed_factor * dt

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
    from ursina import Ursina, Sky, EditorCamera, Grid, Text, dedent

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
            drone.move('forward') # Forward
        elif key == 's':
            drone.move('backward') # Backward
        elif key == 'a':
            drone.move('left') # Left
        elif key == 'd':
            drone.move('right') # Right
        elif key == 'r': # Increase altitude target
            drone.move('up')
        elif key == 'f': # Decrease altitude target
            drone.move('down')
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

    app.run()
