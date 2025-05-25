import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf
import pickle
from collections import deque
import time
import threading
import os # Import os module

# Configuration
# Construct paths relative to the current file's directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, '..', 'landmark_model.h5')
LANDMARK_FILE = os.path.join(CURRENT_DIR, '..', 'hand_landmarks.pkl')

# Model & Resources
model = None
CLASS_NAMES = []
hands = None
cap = None
is_initialized = False
initialization_lock = threading.Lock()
stop_camera_feed_event = threading.Event() # Event to signal feed termination

# --- Prediction Smoothing Config ---
PREDICTION_BUFFER_SIZE = 10 # Number of frames to consider
SMOOTHING_THRESHOLD = 0.9 # % of buffer that must agree
STABLE_STATE_HOLD_DURATION = 1.5 # Seconds to hold a stable prediction
MIN_PREDICTION_CONFIDENCE = 0.80 # Minimum confidence for an individual frame's prediction to be considered valid
NON_VALID_SIGN_STATES = {"Unknown", "No hand detected", "Processing Error", "Landmark count error", "Detect Error", "...", "Stab. Error", "Low Confidence"} # Define invalid states

# Prediction State
prediction_buffer = deque(maxlen=PREDICTION_BUFFER_SIZE)
stable_prediction_display = "Initializing..."
last_processed_frame_confidence = 0.0 # Confidence of the last frame's valid instantaneous prediction
last_valid_prediction_timestamp = None
# --------------------------------

def initialize_resources():
    """Loads model, class names, initializes MediaPipe, and opens camera."""
    global model, CLASS_NAMES, hands, cap, is_initialized, stable_prediction_display, stop_camera_feed_event

    with initialization_lock:
        if is_initialized: # Simpler check: if fully initialized (including potentially camera), return
            if cap and cap.isOpened() and not stop_camera_feed_event.is_set(): # If camera was meant to be on and is
                 return True
            elif not os.getenv('NO_CAMERA') and (not cap or not cap.isOpened()) and not stop_camera_feed_event.is_set():
                 # If camera was expected, is not open, and not stopped, might need re-init
                 print("Camera was expected but not open, proceeding with potential re-initialization.")
            elif os.getenv('NO_CAMERA') and not stop_camera_feed_event.is_set(): # If no camera expected and not stopped
                 return True # Model and hands should be fine
            
            if stop_camera_feed_event.is_set():
                print("Resources were initialized, but camera feed was stopped. Re-clearing event for potential restart.")
                stop_camera_feed_event.clear()
                # Do not return True yet, proceed to re-evaluate camera status based on NO_CAMERA

        # Clear the stop event at the beginning of a full initialization or re-evaluation
        stop_camera_feed_event.clear()
        print("Initializing resources for sign logic...")
        try:
            # Load Model if not already loaded
            if model is None:
                print(f"Loading model from: {MODEL_PATH}")
                model = tf.keras.models.load_model(MODEL_PATH)
                print("Model loaded successfully.")

            # Load Class Names if not already loaded
            if not CLASS_NAMES:
                print(f"Loading class names from: {LANDMARK_FILE}")
                with open(LANDMARK_FILE, 'rb') as f:
                    data = pickle.load(f)
                CLASS_NAMES = data['class_names']
                print(f"Class names loaded: {len(CLASS_NAMES)} classes found.")

            # Debug print for NO_CAMERA environment variable
            no_camera_env_var = os.getenv('NO_CAMERA')
            print(f"DEBUG: Value of NO_CAMERA environment variable: '{no_camera_env_var}' (type: {type(no_camera_env_var)})")

            # Conditional Initialization for MediaPipe Hands and Camera
            if not no_camera_env_var:
                # Initialize MediaPipe Hands only if NO_CAMERA is not set
                if hands is None:
                    print("Initializing MediaPipe Hands (NO_CAMERA is not set)...")
                    mp_hands_sol = mp.solutions.hands
                    hands = mp_hands_sol.Hands(
                        static_image_mode=False,
                        max_num_hands=1,
                        min_detection_confidence=0.6,
                        min_tracking_confidence=0.6)
                    print("MediaPipe Hands initialized.")
                
                # Initialize Camera only if NO_CAMERA is not set
                try:
                    print("Attempting to initialize camera (device 0)...")
                    if cap and cap.isOpened(): # If cap exists and is open, release it first
                        print("Existing camera capture found open, releasing before re-initialization.")
                        cap.release()
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        print("Warning: Could not open webcam. Camera-dependent features will be unavailable.")
                        cap = None # Ensure cap is None if it failed
                    else:
                        print("Camera initialized successfully.")
                except Exception as cam_exc:
                    print(f"Warning: Camera initialization failed - {cam_exc}. Camera-dependent features will be unavailable.")
                    cap = None # Ensure cap is None if it failed
            else:
                print("NO_CAMERA environment variable set. Skipping MediaPipe Hands and camera initialization.")
                if hands: # If NO_CAMERA is set, but hands were somehow initialized before this check, close and None it.
                    print("NO_CAMERA is set, ensuring MediaPipe Hands is closed and set to None.")
                    hands.close()
                    hands = None
                if cap and cap.isOpened(): # If NO_CAMERA is set now, but cap was previously open
                    print("NO_CAMERA is set, releasing previously opened camera.")
                    cap.release()
                cap = None
                hands = None # Explicitly ensure hands is None if NO_CAMERA is set

            is_initialized = True # Mark as initialized if model and class_names are loaded. Camera and Hands are conditionally initialized.
            stable_prediction_display = "Ready..."
            print("Resource initialization (model, landmarks) complete. Hands and Camera conditionally initialized.")
            return True

        except FileNotFoundError as e:
            print(f"Error: File not found during initialization - {e}")
            stable_prediction_display = "Error: File Missing"
            if 'cap' in locals() and cap and cap.isOpened(): cap.release()
            if 'hands' in locals() and hands: hands.close()
            model, cap, hands, is_initialized = None, None, None, False
            return False
        except Exception as e:
            print(f"Error during resource initialization: {e}")
            stable_prediction_display = "Error: Init Failed"
            if 'cap' in locals() and cap and cap.isOpened(): cap.release()
            if 'hands' in locals() and hands: hands.close()
            model, cap, hands, is_initialized = None, None, None, False
            return False

# --- Frame Generation Function
def generate_frames():
    """Generates camera frames with sign prediction overlays for web streaming."""
    global stable_prediction_display, last_valid_prediction_timestamp, prediction_buffer, hands, cap, model, CLASS_NAMES, stop_camera_feed_event

    if os.getenv('NO_CAMERA'):
        print("NO_CAMERA set. Frame generation (camera feed) is disabled.")
        # Yield a static image indicating camera is disabled
        disabled_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(disabled_img, "Camera Disabled by Server Config", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        while not stop_camera_feed_event.is_set():
            _, buffer = cv2.imencode('.jpg', disabled_img)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1) # Keep yielding the static image
        print("Exited disabled frame generation loop.")
        return

    if not is_initialized:
        if not initialize_resources():
            print("Initialization failed. Cannot generate frames.")
            error_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera/Model Init Failed", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            _, buffer = cv2.imencode('.jpg', error_img)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            return

    mp_drawing = mp.solutions.drawing_utils
    mp_hands_sol = mp.solutions.hands # Use the same name as in initialize_resources for consistency

    print("Starting frame generation loop...")
    while not stop_camera_feed_event.is_set():
        if not cap or not cap.isOpened():
             if not stop_camera_feed_event.is_set():
                print("Error: Camera not available. Attempting to re-initialize...")
                if not initialize_resources():
                    stable_prediction_display = "Error: Camera Lost"
                    error_img = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(error_img, "Camera Connection Lost", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    _, buffer = cv2.imencode('.jpg', error_img)
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(1)
                    continue
                else:
                    print("Camera re-initialized successfully.")
                    if not cap or not cap.isOpened(): # Check again after re-init
                        print("Camera still not available after re-initialization attempt.")
                        # Yield error and continue
                        stable_prediction_display = "Error: Camera Init Loop"
                        error_img = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(error_img, "Camera Init Loop", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        _, buffer = cv2.imencode('.jpg', error_img)
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                        time.sleep(1)
                        continue
             else:
                print("Camera feed stop requested, exiting generation loop.")
                break

        if stop_camera_feed_event.is_set():
            print("Camera feed stop requested during frame processing, exiting.")
            break

        current_time = time.time()
        success, image = cap.read()
        if not success:
            time.sleep(0.01)
            continue

        image_rgb = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = hands.process(image_rgb)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        image_bgr.flags.writeable = True

        current_prediction_text = ""
        instantaneous_prediction = "No hand detected"

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                image_bgr, hand_landmarks, mp_hands_sol.HAND_CONNECTIONS)

            landmarks_normalized = []
            try:
                wrist = hand_landmarks.landmark[0]
                origin_x, origin_y = wrist.x, wrist.y
                mcp_middle = hand_landmarks.landmark[mp_hands_sol.HandLandmark.MIDDLE_FINGER_MCP]
                scale = np.sqrt((mcp_middle.x - origin_x)**2 + (mcp_middle.y - origin_y)**2)
                scale = max(scale, 1e-6)

                for landmark in hand_landmarks.landmark:
                    norm_x = (landmark.x - origin_x) / scale
                    norm_y = (landmark.y - origin_y) / scale
                    landmarks_normalized.extend([norm_x, norm_y])

                if len(landmarks_normalized) == 42:
                    landmark_input = np.array([landmarks_normalized], dtype=np.float32)
                    prediction = model.predict(landmark_input, verbose=0)
                    predicted_class_index = np.argmax(prediction)
                    confidence = np.max(prediction)

                    global last_processed_frame_confidence
                    if confidence >= MIN_PREDICTION_CONFIDENCE:
                        predicted_letter = CLASS_NAMES[predicted_class_index]
                        current_prediction_text = f"Detect: {predicted_letter} ({confidence*100:.2f}%)"
                        instantaneous_prediction = predicted_letter
                        last_processed_frame_confidence = confidence
                    else:
                        current_prediction_text = f"Detect: Low Confidence ({confidence*100:.2f}%)"
                        instantaneous_prediction = "Low Confidence"
                        last_processed_frame_confidence = 0.0
                else:
                    current_prediction_text = "Detect: Landmark count error"
                    instantaneous_prediction = "Landmark count error"

            except Exception as e:
                current_prediction_text = f"Detect Error: {e}"
                instantaneous_prediction = "Detect Error"
                print(f"Detection Error: {e}")

            prediction_buffer.append(instantaneous_prediction)

        else:
            current_prediction_text = "Detect: No hand detected"
            instantaneous_prediction = "No hand detected"
            prediction_buffer.append(instantaneous_prediction)

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
                        else:
                            if stable_prediction_display not in NON_VALID_SIGN_STATES and stable_prediction_display != "Ready...":
                                stable_prediction_display = "Ready..."
                            last_valid_prediction_timestamp = None
                    else:
                        if last_valid_prediction_timestamp is not None and (current_time - last_valid_prediction_timestamp >= STABLE_STATE_HOLD_DURATION):
                            if stable_prediction_display != "Ready...":
                                stable_prediction_display = "Ready..."
                            last_valid_prediction_timestamp = None
                        elif last_valid_prediction_timestamp is None and stable_prediction_display not in ["Ready..."] and stable_prediction_display not in NON_VALID_SIGN_STATES:
                            stable_prediction_display = "Ready..."
                else:
                     stable_prediction_display = "..."
                     last_valid_prediction_timestamp = None

            except Exception as e:
                print(f"Error during stabilization: {e}")
                stable_prediction_display = "Stab. Error"
                last_valid_prediction_timestamp = None

        elif last_valid_prediction_timestamp is not None and (current_time - last_valid_prediction_timestamp >= STABLE_STATE_HOLD_DURATION):
            if stable_prediction_display != "Ready...":
                stable_prediction_display = "Ready..."
            last_valid_prediction_timestamp = None

        cv2.putText(image_bgr, current_prediction_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 120, 0), 2, cv2.LINE_AA)

        stable_color = (0, 255, 0)
        if stable_prediction_display in NON_VALID_SIGN_STATES or stable_prediction_display == "Ready..." or stable_prediction_display == "Initializing...":
            stable_color = (200, 200, 200)
        if "Error" in stable_prediction_display:
            stable_color = (0, 0, 255)

        cv2.putText(image_bgr, f"Stable: {stable_prediction_display}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, stable_color, 2, cv2.LINE_AA)

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
            if stop_camera_feed_event.is_set():
                break

    print("Exited frame generation loop.")

    with initialization_lock:
        if cap and cap.isOpened():
            print("Releasing camera from generate_frames exit (defensive).")
            cap.release()
        # hands are closed globally in release_resources or if re-initialized
        # No need to close hands here specifically as it might be needed by other calls
        # if hands:
        # print("Closing MediaPipe hands from generate_frames exit (defensive).")
        # hands.close() # This might be too aggressive if other parts still expect hands to be open

        print("Defensive cleanup in generate_frames exit done.")

# --- Functions for Routes ---

def release_resources():
    """Releases camera, MediaPipe hands, and resets initialization state."""
    global cap, hands, model, is_initialized, stable_prediction_display, stop_camera_feed_event, initialization_lock

    print("Attempting to release resources...")
    stop_camera_feed_event.set()

  
    time.sleep(0.25)

    with initialization_lock: # Ensure thread-safe access
        if cap:
            if cap.isOpened():
                print("Releasing camera capture...")
                cap.release()
            cap = None # Set to None after release
            print("Camera capture released.")
        else:
            print("Camera capture was not initialized or already released.")

        if hands:
            print("Closing MediaPipe Hands...")
            hands.close()
            hands = None # Set to None after close
            print("MediaPipe Hands closed.")
        else:
            print("MediaPipe Hands were not initialized or already closed.")
        
        # Optionally reset model and CLASS_NAMES if they should be reloaded from scratch next time
        # model = None
        # CLASS_NAMES = []

        is_initialized = False # Mark as not initialized
        stable_prediction_display = "Offline"

        print("Resources released and state reset.")


def get_stable_prediction():
    """Returns the current stable prediction and the confidence of the last valid processed frame."""
    global stable_prediction_display, last_processed_frame_confidence, is_initialized, stop_camera_feed_event
    import json

    # If NO_CAMERA is set, camera-dependent predictions are not relevant.
    # The stable_prediction_display might be "Camera Disabled..." or similar.
    if os.getenv('NO_CAMERA'):
        # You might want to return a specific state or the current stable_prediction_display
        # which would reflect that the camera is off.
        return json.dumps({"sign": str(stable_prediction_display), "confidence": 0.0})

    if not is_initialized and not stop_camera_feed_event.is_set():
        print("get_stable_prediction: resources not initialized and feed not stopped, attempting to initialize.")
        initialize_resources()

    current_confidence = 0.0
    if stable_prediction_display not in NON_VALID_SIGN_STATES and \
       stable_prediction_display != "Ready..." and \
       stable_prediction_display != "Initializing..." and \
       stable_prediction_display != "..." and \
       "Error" not in stable_prediction_display: # Added check for error states
        current_confidence = float(last_processed_frame_confidence)
    else:
        current_confidence = 0.0

    return json.dumps({"sign": str(stable_prediction_display), "confidence": float(current_confidence)})

def get_available_signs():
    """Returns the list of class names loaded from the model/pickle file."""
    global CLASS_NAMES, is_initialized # Ensure is_initialized is global here
    if not is_initialized: # Check if basic resources (model, class names) are loaded
        print("get_available_signs: resources not fully initialized, attempting to initialize model and class names.")
        initialize_resources() # This will load model and class names even if camera fails or is disabled
    return CLASS_NAMES
