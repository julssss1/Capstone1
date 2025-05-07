import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf
import pickle
from collections import deque 
import time
import threading 


# Configuration
MODEL_PATH = 'landmark_model.h5'
LANDMARK_FILE = 'hand_landmarks.pkl'

# Model & Resources 
model = None
CLASS_NAMES = []
hands = None
cap = None
is_initialized = False
initialization_lock = threading.Lock() # Prevent race conditions during init

# --- Prediction Smoothing Config ---
PREDICTION_BUFFER_SIZE = 10 # Number of frames to consider
SMOOTHING_THRESHOLD = 0.7 # % of buffer that must agree
STABLE_STATE_HOLD_DURATION = 1.5 # Seconds to hold a stable prediction
NON_VALID_SIGN_STATES = {"Unknown", "No hand detected", "Processing Error", "Landmark count error", "Detect Error", "...", "Stab. Error"} # Define invalid states

# Prediction State
prediction_buffer = deque(maxlen=PREDICTION_BUFFER_SIZE)
stable_prediction_display = "Initializing..." 
last_valid_prediction_timestamp = None
# --------------------------------

# --- Initialization Function ---
def initialize_resources():
    """Loads model, class names, initializes MediaPipe, and opens camera."""
    global model, CLASS_NAMES, hands, cap, is_initialized, stable_prediction_display

    with initialization_lock: # Ensure only one thread initializes
        if is_initialized:
            return True

        print("Initializing resources for sign logic...")
        try:
            # Load Model
            print(f"Loading model from: {MODEL_PATH}")
            model = tf.keras.models.load_model(MODEL_PATH)
            print("Model loaded successfully.")

            # Load Class Names
            print(f"Loading class names from: {LANDMARK_FILE}")
            with open(LANDMARK_FILE, 'rb') as f:
                data = pickle.load(f)
            CLASS_NAMES = data['class_names']
            print(f"Class names loaded: {len(CLASS_NAMES)} classes found.")

            # Initialize MediaPipe Hands
            print("Initializing MediaPipe Hands...")
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6)
            print("MediaPipe Hands initialized.")

            # Initialize Camera
            print("Initializing camera (device 0)...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Error: Could not open webcam.")
                stable_prediction_display = "Error: Camera"
             
                return False
            print("Camera initialized successfully.")

            is_initialized = True
            stable_prediction_display = "Ready..." 
            print("Initialization complete.")
            return True

        except FileNotFoundError as e:
            print(f"Error: File not found during initialization - {e}")
            stable_prediction_display = "Error: File Missing"
            return False
        except Exception as e:
            print(f"Error during resource initialization: {e}")
            stable_prediction_display = "Error: Init Failed"

            if cap and cap.isOpened():
                cap.release()
            if hands:
                hands.close()
            model = None
            cap = None
            hands = None
            is_initialized = False
            return False

# --- Frame Generation Function 
def generate_frames():
    """Generates camera frames with sign prediction overlays for web streaming."""
    global stable_prediction_display, last_valid_prediction_timestamp, prediction_buffer, hands, cap, model, CLASS_NAMES

    if not is_initialized:
        if not initialize_resources():
            # If initialization fails, yield an error frame or message
            print("Initialization failed. Cannot generate frames.")
            # Create a placeholder error image
            error_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera/Model Init Failed", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            _, buffer = cv2.imencode('.jpg', error_img)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            return # Stop the generator

    mp_drawing = mp.solutions.drawing_utils 
    mp_hands = mp.solutions.hands 

    print("Starting frame generation loop...")
    while True:
        if not cap or not cap.isOpened():
             print("Error: Camera not available or closed during frame generation.")
             stable_prediction_display = "Error: Camera Lost"
             # Yield an error frame
             error_img = np.zeros((480, 640, 3), dtype=np.uint8)
             cv2.putText(error_img, "Camera Connection Lost", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
             _, buffer = cv2.imencode('.jpg', error_img)
             frame_bytes = buffer.tobytes()
             yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
             time.sleep(1) 
             continue 


        current_time = time.time()
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            time.sleep(0.1)
            continue

        # --- Image Processing ---
        image_rgb = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False 
        results = hands.process(image_rgb)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR) 
        image_bgr.flags.writeable = True

        current_prediction_text = ""
        instantaneous_prediction = "No hand detected" # Default

        # --- Landmark Processing and Prediction ---
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            landmarks_normalized = []
            try:
                wrist = hand_landmarks.landmark[0]
                origin_x, origin_y = wrist.x, wrist.y
                mcp_middle = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                scale = np.sqrt((mcp_middle.x - origin_x)**2 + (mcp_middle.y - origin_y)**2)
                scale = max(scale, 1e-6) # Avoid division by zero

                for landmark in hand_landmarks.landmark:
                    norm_x = (landmark.x - origin_x) / scale
                    norm_y = (landmark.y - origin_y) / scale
                    landmarks_normalized.extend([norm_x, norm_y])

                if len(landmarks_normalized) == 42:
                    landmark_input = np.array([landmarks_normalized], dtype=np.float32)
                    prediction = model.predict(landmark_input, verbose=0)
                    predicted_class_index = np.argmax(prediction)
                    confidence = np.max(prediction)
                    predicted_letter = CLASS_NAMES[predicted_class_index]

                    # Update text and instantaneous prediction
                    if predicted_letter == 'J':
                        current_prediction_text = f"Detect: J (static) ({confidence*100:.2f}%)"
                    elif predicted_letter == 'Z':
                        current_prediction_text = f"Detect: Z (static) ({confidence*100:.2f}%)"
                    else:
                        current_prediction_text = f"Detect: {predicted_letter} ({confidence*100:.2f}%)"
                    instantaneous_prediction = predicted_letter

                else:
                    current_prediction_text = "Detect: Landmark count error"
                    instantaneous_prediction = "Landmark count error"

            except Exception as e:
                current_prediction_text = f"Detect Error: {e}"
                instantaneous_prediction = "Detect Error"
                print(f"Detection Error: {e}") # Log error

            prediction_buffer.append(instantaneous_prediction)

        else: # No hand detected
            current_prediction_text = "Detect: No hand detected"
            instantaneous_prediction = "No hand detected"
            prediction_buffer.append(instantaneous_prediction)

        # --- Update Stable Prediction ---
        if len(prediction_buffer) == PREDICTION_BUFFER_SIZE:
            try:
                counts = {pred: prediction_buffer.count(pred) for pred in set(prediction_buffer)}
                if counts:
                    most_common_pred = max(counts, key=counts.get)
                    most_common_count = counts[most_common_pred]
                    required_count = int(PREDICTION_BUFFER_SIZE * SMOOTHING_THRESHOLD)
                    is_stable_candidate = (most_common_count >= required_count)

                    if is_stable_candidate:
                        if most_common_pred not in NON_VALID_SIGN_STATES:
                            if stable_prediction_display != most_common_pred:
                                stable_prediction_display = most_common_pred
                            last_valid_prediction_timestamp = current_time
                        else: # Non-valid state is stable
                            if stable_prediction_display not in NON_VALID_SIGN_STATES and stable_prediction_display != "Ready...":
                                stable_prediction_display = "Ready..."
                            last_valid_prediction_timestamp = None
                    else: # Not stable
                        if last_valid_prediction_timestamp is not None and (current_time - last_valid_prediction_timestamp >= STABLE_STATE_HOLD_DURATION):
                            if stable_prediction_display != "Ready...":
                                stable_prediction_display = "Ready..."
                            last_valid_prediction_timestamp = None
                        elif last_valid_prediction_timestamp is None and stable_prediction_display not in ["Ready..."] and stable_prediction_display not in NON_VALID_SIGN_STATES:
                            stable_prediction_display = "Ready..."
                else: # Buffer empty case (shouldn't happen with deque append)
                     stable_prediction_display = "..." # Or some indicator
                     last_valid_prediction_timestamp = None


            except Exception as e:
                print(f"Error during stabilization: {e}")
                stable_prediction_display = "Stab. Error"
                last_valid_prediction_timestamp = None

        elif last_valid_prediction_timestamp is not None and (current_time - last_valid_prediction_timestamp >= STABLE_STATE_HOLD_DURATION):
            if stable_prediction_display != "Ready...":
                stable_prediction_display = "Ready..."
            last_valid_prediction_timestamp = None

        # --- Draw Text Overlays ---
        cv2.putText(image_bgr, current_prediction_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 120, 0), 2, cv2.LINE_AA)

        stable_color = (0, 255, 0) # Green default
        if stable_prediction_display in NON_VALID_SIGN_STATES or stable_prediction_display == "Ready..." or stable_prediction_display == "Initializing...":
            stable_color = (200, 200, 200) # Grey
        if "Error" in stable_prediction_display:
            stable_color = (0, 0, 255) # Red

        cv2.putText(image_bgr, f"Stable: {stable_prediction_display}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, stable_color, 2, cv2.LINE_AA)

        # --- Encode and Yield Frame ---
        try:
            ret, buffer = cv2.imencode('.jpg', image_bgr)
            if not ret:
                print("Error encoding frame to JPEG.")
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Error encoding or yielding frame: {e}")

# --- Functions for Routes ---
def get_stable_prediction():
    """Returns the current stable prediction."""
    global stable_prediction_display
    # Ensure initialization has happened or is attempted
    if not is_initialized:
        initialize_resources() # Attempt init if not done yet
    return stable_prediction_display

def get_available_signs():
    """Returns the list of class names loaded from the model/pickle file."""
    global CLASS_NAMES
    # Ensure initialization has happened or is attempted
    if not is_initialized:
        initialize_resources() # Attempt init if not done yet
    return CLASS_NAMES
