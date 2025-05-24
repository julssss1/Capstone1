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
        if is_initialized and cap and cap.isOpened(): # Check if cap is also valid
            # If already initialized and camera is open, ensure stop event is clear for a new start
            if stop_camera_feed_event.is_set():
                print("Camera was stopped, re-clearing stop event for re-initialization.")
                stop_camera_feed_event.clear()
            return True
        
        # Clear the stop event at the beginning of a full initialization
        stop_camera_feed_event.clear()
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


            try:
                print("Attempting to initialize camera (device 0)...")
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    print("Warning: Could not open webcam. Camera-dependent features will be unavailable.")
                    
                else:
                    print("Camera initialized successfully.")
            except Exception as cam_exc:
                print(f"Warning: Camera initialization failed - {cam_exc}. Camera-dependent features will be unavailable.")
                cap = None # Ensure cap is None if it failed

            is_initialized = True # Mark as initialized if model and hands are loaded, even if camera fails.
            stable_prediction_display = "Ready..."
            print("Resource initialization (model, landmarks, hands) complete.")
            return True

        except FileNotFoundError as e:
            print(f"Error: File not found during initialization - {e}")
            stable_prediction_display = "Error: File Missing"
            # Ensure cleanup
            if 'cap' in locals() and cap and cap.isOpened(): cap.release()
            if 'hands' in locals() and hands: hands.close()
            model, cap, hands, is_initialized = None, None, None, False
            return False
        except Exception as e:
            print(f"Error during resource initialization: {e}")
            stable_prediction_display = "Error: Init Failed"
            # Ensure cleanup
            if 'cap' in locals() and cap and cap.isOpened(): cap.release()
            if 'hands' in locals() and hands: hands.close()
            model, cap, hands, is_initialized = None, None, None, False
            return False

# --- Frame Generation Function
def generate_frames():
    """Generates camera frames with sign prediction overlays for web streaming."""
    global stable_prediction_display, last_valid_prediction_timestamp, prediction_buffer, hands, cap, model, CLASS_NAMES, stop_camera_feed_event

    if not is_initialized:
        # Attempt to initialize
        if not initialize_resources():
            # If initialization fails even after attempt
            print("Initialization failed. Cannot generate frames.")
            # placeholder error image
            error_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera/Model Init Failed", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            _, buffer = cv2.imencode('.jpg', error_img)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            return 

    mp_drawing = mp.solutions.drawing_utils 
    mp_hands = mp.solutions.hands 

    print("Starting frame generation loop...")
    while not stop_camera_feed_event.is_set(): # Check the event at the start of each loop
        if not cap or not cap.isOpened():
             # Attempt to re-initialize if camera is lost and not explicitly stopped
             if not stop_camera_feed_event.is_set():
                print("Error: Camera not available. Attempting to re-initialize...")
                if not initialize_resources(): # Try to re-initialize
                    stable_prediction_display = "Error: Camera Lost"
                    # Yield an error frame if re-initialization fails
                    error_img = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(error_img, "Camera Connection Lost", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    _, buffer = cv2.imencode('.jpg', error_img)
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(1) # Wait before retrying or exiting
                    continue # Try the loop again
                else:
                    print("Camera re-initialized successfully.")
             else: # If stop_camera_feed_event is set, break the loop
                print("Camera feed stop requested, exiting generation loop.")
                break

             # Original error handling if camera is still not available
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

        # Check stop event again before processing frame
        if stop_camera_feed_event.is_set():
            print("Camera feed stop requested during frame processing, exiting.")
            break

        current_time = time.time()
        success, image = cap.read()
        if not success:
            time.sleep(0.01) # Shorter sleep for empty frames
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
                    
                    global last_processed_frame_confidence # Ensure we modify the global
                    if confidence >= MIN_PREDICTION_CONFIDENCE:
                        predicted_letter = CLASS_NAMES[predicted_class_index]
                        current_prediction_text = f"Detect: {predicted_letter} ({confidence*100:.2f}%)"
                        instantaneous_prediction = predicted_letter
                        last_processed_frame_confidence = confidence # Store confidence of this valid prediction
                    else:
                        # predicted_letter = "Low Confidence" # Not needed as instantaneous_prediction handles it
                        current_prediction_text = f"Detect: Low Confidence ({confidence*100:.2f}%)"
                        instantaneous_prediction = "Low Confidence" 
                        last_processed_frame_confidence = 0.0 # Reset if low confidence
                else:
                    current_prediction_text = "Detect: Landmark count error"
                    instantaneous_prediction = "Landmark count error"

            except Exception as e:
                current_prediction_text = f"Detect Error: {e}"
                instantaneous_prediction = "Detect Error"
                print(f"Detection Error: {e}") 

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
                        # global current_stable_sign_confidence # Not needed anymore here
                        if most_common_pred not in NON_VALID_SIGN_STATES:
                            if stable_prediction_display != most_common_pred:
                                stable_prediction_display = most_common_pred
                                # When stable_prediction_display is updated to a valid sign,
                                # last_processed_frame_confidence should hold the confidence of the
                                # instantaneous prediction that contributed to this stability.
                            last_valid_prediction_timestamp = current_time
                        else: # Non-valid state is stable
                            if stable_prediction_display not in NON_VALID_SIGN_STATES and stable_prediction_display != "Ready...":
                                stable_prediction_display = "Ready..."
                            # current_stable_sign_confidence = 0.0 # Not needed
                            last_valid_prediction_timestamp = None
                    else: # Not stable
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

        # --- Draw Text Overlays ---
        cv2.putText(image_bgr, current_prediction_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 120, 0), 2, cv2.LINE_AA)

        stable_color = (0, 255, 0) # Green 
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
            if stop_camera_feed_event.is_set(): # If stop is requested during error, break
                break
    
    print("Exited frame generation loop.")
    
    with initialization_lock: 
        # Access global variables directly
        if cap and cap.isOpened(): # cap here refers to the global cap
            print("Releasing camera from generate_frames exit (defensive).")
            cap.release()
        if hands: # hands here refers to the global hands
            print("Closing MediaPipe hands from generate_frames exit (defensive).")
            hands.close()

        print("Defensive cleanup in generate_frames exit done.")


# --- Functions for Routes ---

def release_resources():
    """Releases camera, MediaPipe hands, and resets initialization state."""
    global cap, hands, model, is_initialized, stable_prediction_display, stop_camera_feed_event, initialization_lock

    print("Attempting to release resources...")
    stop_camera_feed_event.set() # Signal the generate_frames loop to stop

    with initialization_lock:
        if cap:
            if cap.isOpened():
                print("Releasing camera capture...")
                cap.release()
            cap = None
            print("Camera capture released.")
        else:
            print("Camera capture was not initialized or already released.")

        if hands:
            print("Closing MediaPipe Hands...")
            hands.close()
            hands = None
            print("MediaPipe Hands closed.")
        else:
            print("MediaPipe Hands were not initialized or already closed.")

        is_initialized = False
        stable_prediction_display = "Offline" 
        
        print("Resources released and state reset.")

def get_stable_prediction():
    """Returns the current stable prediction and the confidence of the last valid processed frame."""
    global stable_prediction_display, last_processed_frame_confidence, is_initialized, stop_camera_feed_event
    import json

    if not is_initialized and not stop_camera_feed_event.is_set():
        print("get_stable_prediction: resources not initialized and feed not stopped, attempting to initialize.")
        initialize_resources()
    
    # If the stable display is a non-sign state, report confidence as 0
    current_confidence = 0.0
    if stable_prediction_display not in NON_VALID_SIGN_STATES and \
       stable_prediction_display != "Ready..." and \
       stable_prediction_display != "Initializing..." and \
       stable_prediction_display != "...":
        current_confidence = float(last_processed_frame_confidence) # Ensure it's a standard Python float
    else:
        current_confidence = 0.0 # Ensure it's a float even for non-sign states

    return json.dumps({"sign": str(stable_prediction_display), "confidence": float(current_confidence)}) # Ensure both are standard types

def get_available_signs():
    """Returns the list of class names loaded from the model/pickle file."""
    global CLASS_NAMES
    if not is_initialized:
        initialize_resources() 
    return CLASS_NAMES
