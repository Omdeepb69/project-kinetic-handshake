# gesture_detector.py

import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque

class GestureDetector:
    """
    Handles processing webcam feed using OpenCV and MediaPipe to detect
    hand landmarks and interpret them into predefined gesture commands.
    Includes rudimentary adaptation logic (gesture debouncing).
    """

    def __init__(self, detection_confidence=0.7, tracking_confidence=0.7, debounce_frames=3):
        """
        Initializes the GestureDetector.

        Args:
            detection_confidence (float): Minimum confidence value ([0.0, 1.0]) for hand detection.
            tracking_confidence (float): Minimum confidence value ([0.0, 1.0]) for hand tracking.
            debounce_frames (int): Number of consecutive frames a gesture must be detected
                                   before it's considered stable.
        """
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence
        self.debounce_frames = debounce_frames
        self.mp_hands = mp.solutions.hands
        self.hands = None # Initialize in initialize_mediapipe
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Debouncing state
        self.gesture_buffer = deque(maxlen=self.debounce_frames)
        self.current_stable_gesture = 'none'
        self.last_gesture_time = time.time()

        # Landmark indices
        self.landmark_indices = {
            'WRIST': 0,
            'THUMB_CMC': 1, 'THUMB_MCP': 2, 'THUMB_IP': 3, 'THUMB_TIP': 4,
            'INDEX_MCP': 5, 'INDEX_PIP': 6, 'INDEX_DIP': 7, 'INDEX_TIP': 8,
            'MIDDLE_MCP': 9, 'MIDDLE_PIP': 10, 'MIDDLE_DIP': 11, 'MIDDLE_TIP': 12,
            'RING_MCP': 13, 'RING_PIP': 14, 'RING_DIP': 15, 'RING_TIP': 16,
            'PINKY_MCP': 17, 'PINKY_PIP': 18, 'PINKY_DIP': 19, 'PINKY_TIP': 20
        }
        
        self.initialize_mediapipe()

    def initialize_mediapipe(self):
        """Initializes the MediaPipe Hands solution."""
        try:
            self.hands = self.mp_hands.Hands(
                model_complexity=0, # 0 for faster performance, 1 for higher accuracy
                min_detection_confidence=self.detection_confidence,
                min_tracking_confidence=self.tracking_confidence,
                max_num_hands=1 # Process only one hand for drone control
            )
            print("MediaPipe Hands initialized successfully.")
        except Exception as e:
            print(f"Error initializing MediaPipe Hands: {e}")
            self.hands = None # Ensure hands is None if initialization fails

    def detect_gesture(self, frame):
        """
        Detects hand landmarks in a frame and classifies the gesture.

        Args:
            frame (np.ndarray): The input image frame (BGR format from OpenCV).

        Returns:
            tuple: (str, np.ndarray)
                - The detected stable gesture command ('none', 'hover', 'land', 'move_forward', etc.).
                - The processed frame with landmarks drawn (or original frame if no hand detected).
        """
        if self.hands is None:
            print("Error: MediaPipe Hands not initialized.")
            return self.current_stable_gesture, frame # Return last known stable gesture

        # Flip the frame horizontally for a later selfie-view display
        # and convert the BGR image to RGB.
        frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)

        # To improve performance, optionally mark the image as not writeable to
        # pass by reference.
        frame_rgb.flags.writeable = False
        results = self.hands.process(frame_rgb)

        # Prepare frame for drawing (convert back if needed and make writeable)
        frame_rgb.flags.writeable = True
        processed_frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR) # Back to BGR for drawing

        detected_gesture = 'none' # Default gesture if no hand or no specific gesture

        if results.multi_hand_landmarks:
            # Use only the first detected hand
            hand_landmarks = results.multi_hand_landmarks[0]

            # Draw the hand annotations on the image.
            self.mp_drawing.draw_landmarks(
                processed_frame,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style())

            # Classify the gesture based on landmarks
            detected_gesture = self._classify_gesture(hand_landmarks.landmark)

        # --- Gesture Debouncing Logic ---
        self.gesture_buffer.append(detected_gesture)

        # Check if the buffer is full and all elements are the same
        if len(self.gesture_buffer) == self.debounce_frames and len(set(self.gesture_buffer)) == 1:
            new_stable_gesture = self.gesture_buffer[0]
            if new_stable_gesture != self.current_stable_gesture:
                self.current_stable_gesture = new_stable_gesture
                self.last_gesture_time = time.time()
                # print(f"Stable Gesture Detected: {self.current_stable_gesture}") # Debugging
        # Optional: Add a timeout to revert to 'none' or 'hover' if no gesture detected for a while
        # elif time.time() - self.last_gesture_time > 2.0: # e.g., 2 seconds timeout
        #     self.current_stable_gesture = 'hover' # Or 'none'

        # Add gesture text to the frame
        cv2.putText(processed_frame, f"Gesture: {self.current_stable_gesture}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

        return self.current_stable_gesture, processed_frame


    def _classify_gesture(self, landmarks):
        """
        Classifies the hand gesture based on landmark positions.

        Args:
            landmarks (list): A list of landmark objects from MediaPipe.

        Returns:
            str: The name of the classified gesture.
        """
        try:
            # --- Finger Extension Check ---
            # Check if fingers are extended or curled based on y-coordinates
            # (lower y-coordinate means higher up in the image frame)
            # Tip landmark index: 8, 12, 16, 20
            # PIP landmark index: 6, 10, 14, 18
            # MCP landmark index: 5, 9, 13, 17
            
            fingers_extended = {
                'INDEX': landmarks[self.landmark_indices['INDEX_TIP']].y < landmarks[self.landmark_indices['INDEX_PIP']].y,
                'MIDDLE': landmarks[self.landmark_indices['MIDDLE_TIP']].y < landmarks[self.landmark_indices['MIDDLE_PIP']].y,
                'RING': landmarks[self.landmark_indices['RING_TIP']].y < landmarks[self.landmark_indices['RING_PIP']].y,
                'PINKY': landmarks[self.landmark_indices['PINKY_TIP']].y < landmarks[self.landmark_indices['PINKY_PIP']].y
            }
            
            fingers_curled = {
                'INDEX': landmarks[self.landmark_indices['INDEX_TIP']].y > landmarks[self.landmark_indices['INDEX_PIP']].y,
                'MIDDLE': landmarks[self.landmark_indices['MIDDLE_TIP']].y > landmarks[self.landmark_indices['MIDDLE_PIP']].y,
                'RING': landmarks[self.landmark_indices['RING_TIP']].y > landmarks[self.landmark_indices['RING_PIP']].y,
                'PINKY': landmarks[self.landmark_indices['PINKY_TIP']].y > landmarks[self.landmark_indices['PINKY_PIP']].y
            }

            # Thumb check (relative to MCP or IP)
            thumb_tip = landmarks[self.landmark_indices['THUMB_TIP']]
            thumb_ip = landmarks[self.landmark_indices['THUMB_IP']]
            thumb_mcp = landmarks[self.landmark_indices['THUMB_MCP']]
            index_mcp = landmarks[self.landmark_indices['INDEX_MCP']]
            
            is_thumb_up = thumb_tip.y < thumb_ip.y < thumb_mcp.y
            is_thumb_down = thumb_tip.y > thumb_ip.y # Simple check
            is_thumb_extended_horizontally = abs(thumb_tip.y - thumb_mcp.y) < abs(thumb_tip.x - thumb_mcp.x) * 0.8 # Heuristic

            # --- Gesture Rules ---

            # LAND: Fist (all fingers curled)
            if all(fingers_curled.values()):
                 # Check thumb position for rotation
                if is_thumb_extended_horizontally:
                    if thumb_tip.x < index_mcp.x: # Thumb points left (relative to palm)
                         return 'rotate_left'
                    else: # Thumb points right
                         return 'rotate_right'
                else:
                    return 'land' # Basic fist

            # HOVER: Open Palm (all fingers extended)
            if all(fingers_extended.values()) and not is_thumb_up and not is_thumb_down:
                 # Add a check to ensure thumb isn't pointing straight up/down strongly
                 if abs(thumb_tip.y - thumb_mcp.y) > abs(thumb_tip.x - thumb_mcp.x) * 0.5: # Thumb not strongly horizontal
                    return 'hover'

            # MOVE FORWARD: Pointing Index Finger Up
            if fingers_extended['INDEX'] and all(fingers_curled[f] for f in ['MIDDLE', 'RING', 'PINKY']):
                # Check direction of index finger
                index_tip = landmarks[self.landmark_indices['INDEX_TIP']]
                index_pip = landmarks[self.landmark_indices['INDEX_PIP']]
                index_mcp = landmarks[self.landmark_indices['INDEX_MCP']]
                
                # Vertical check (pointing up)
                if index_tip.y < index_pip.y < index_mcp.y:
                    # Horizontal check (roughly centered or slightly angled is ok for forward)
                    if abs(index_tip.x - index_mcp.x) < abs(index_tip.y - index_mcp.y) * 0.7: # More vertical than horizontal
                        return 'move_forward'
                    elif index_tip.x < index_mcp.x: # Pointing left-ish
                        return 'move_left'
                    else: # Pointing right-ish
                        return 'move_right'
                # Check if pointing down (for backward) - less reliable maybe
                elif index_tip.y > index_pip.y: # > index_mcp.y: # Pointing somewhat down
                     # Ensure it's relatively straight down, not just curled
                     dist_index_mcp_tip = np.sqrt((index_tip.x - index_mcp.x)**2 + (index_tip.y - index_mcp.y)**2)
                     dist_index_mcp_pip = np.sqrt((index_pip.x - index_mcp.x)**2 + (index_pip.y - index_mcp.y)**2)
                     if dist_index_mcp_tip > dist_index_mcp_pip * 1.2: # Check if tip is further than pip
                        return 'move_backward'


            # ASCEND: Thumbs Up (other fingers curled)
            if is_thumb_up and all(fingers_curled.values()):
                return 'ascend'

            # DESCEND: Thumbs Down (other fingers curled) - Be careful with orientation
            # Let's use a simpler check: thumb tip below thumb IP and MCP, other fingers curled
            if thumb_tip.y > thumb_ip.y and thumb_tip.y > thumb_mcp.y and all(fingers_curled.values()):
                 return 'descend'


            # If none of the specific gestures match
            return 'none'

        except Exception as e:
            # print(f"Error during gesture classification: {e}") # Optional logging
            # traceback.print_exc() # More detailed error
            return 'none' # Return default on error

    def release(self):
        """Releases the MediaPipe Hands resources."""
        if self.hands:
            self.hands.close()
            print("MediaPipe Hands resources released.")

# Example Usage (for testing purposes)
if __name__ == '__main__':
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        exit()

    detector = GestureDetector(debounce_frames=5) # Use slightly longer debounce for testing

    while True:
        success, frame = cap.read()
        if not success:
            print("Error: Failed to capture frame.")
            break

        gesture, processed_frame = detector.detect_gesture(frame)

        # Display the processed frame
        cv2.imshow('Gesture Detection Test', processed_frame)

        # print(f"Detected Gesture: {gesture}") # Continuous print for debugging

        if cv2.waitKey(5) & 0xFF == 27: # Press ESC to exit
            break

    detector.release()
    cap.release()
    cv2.destroyAllWindows()