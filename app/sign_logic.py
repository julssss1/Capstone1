import numpy as np
import tensorflow as tf
import pickle
import os
import json

# Configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, '..', 'landmark_model.tflite')
LANDMARK_FILE = os.path.join(CURRENT_DIR, '..', 'hand_landmarks.pkl')

# Model & Resources
interpreter = None
input_details = None
output_details = None
CLASS_NAMES = []
is_initialized = False
MIN_PREDICTION_CONFIDENCE = 0.90

def initialize_resources():
    """Loads TFLite model and class names."""
    global interpreter, input_details, output_details, CLASS_NAMES, is_initialized

    if is_initialized:
        return True

    print("Initializing resources for sign logic...")
    try:
        # Load TFLite Model
        if interpreter is None:
            print(f"Loading TFLite model from: {MODEL_PATH}")
            interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
            interpreter.allocate_tensors()
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            print("TFLite model loaded successfully.")

        # Load Class Names
        if not CLASS_NAMES:
            print(f"Loading class names from: {LANDMARK_FILE}")
            with open(LANDMARK_FILE, 'rb') as f:
                data = pickle.load(f)
            CLASS_NAMES = data['class_names']
            print(f"Class names loaded: {len(CLASS_NAMES)} classes found.")

        is_initialized = True
        print("Resource initialization complete.")
        return True

    except FileNotFoundError as e:
        print(f"Error: File not found during initialization - {e}")
        interpreter, is_initialized = None, False
        return False
    except Exception as e:
        print(f"Error during resource initialization: {e}")
        interpreter, is_initialized = None, False
        return False


def predict_landmarks(landmarks_data):
    """
    Predict sign from normalized landmark data.
    
    Args:
        landmarks_data: List of 42 normalized landmark values (21 landmarks * 2 coordinates)
    
    Returns:
        dict: {"sign": predicted_letter, "confidence": confidence_value}
    """
    global interpreter, input_details, output_details, CLASS_NAMES, is_initialized

    if not is_initialized:
        initialize_resources()

    if not is_initialized:
        return {"sign": "Initialization Error", "confidence": 0.0}

    try:
        if len(landmarks_data) != 42:
            return {"sign": "Invalid landmark count", "confidence": 0.0}

        # Prepare input for TFLite model
        landmark_input = np.array([landmarks_data], dtype=input_details[0]['dtype'])
        
        # Check input shape
        if landmark_input.shape[1:] != tuple(input_details[0]['shape'][1:]):
            print(f"Error: Input shape {landmark_input.shape[1:]} doesn't match expected {input_details[0]['shape'][1:]}")
            return {"sign": "Shape Error", "confidence": 0.0}

        # Run prediction
        interpreter.set_tensor(input_details[0]['index'], landmark_input)
        interpreter.invoke()
        prediction = interpreter.get_tensor(output_details[0]['index'])
        
        predicted_class_index = np.argmax(prediction[0])
        confidence = float(np.max(prediction[0]))

        if confidence >= MIN_PREDICTION_CONFIDENCE:
            predicted_letter = CLASS_NAMES[predicted_class_index]
            return {"sign": predicted_letter, "confidence": confidence}
        else:
            return {"sign": "Low Confidence", "confidence": confidence}

    except Exception as e:
        print(f"Error during prediction: {e}")
        return {"sign": "Prediction Error", "confidence": 0.0}


def get_available_signs():
    """Returns the list of class names (A-Z)."""
    global CLASS_NAMES, is_initialized
    
    if not is_initialized:
        initialize_resources()
    
    return CLASS_NAMES
