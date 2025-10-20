import numpy as np
import tensorflow as tf
import pickle
import os

# Configuration for FSL (Filipino Sign Language) two-hand model
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, '..', 'landmark_model_fsl.tflite')
CLASS_MAPPING_FILE = os.path.join(CURRENT_DIR, '..', 'class_mapping_fsl.pkl')

# Model & Resources
interpreter_fsl = None
input_details_fsl = None
output_details_fsl = None
CLASS_NAMES_FSL = []
is_initialized_fsl = False
MIN_PREDICTION_CONFIDENCE_FSL = 0.90

def initialize_resources_fsl():
    """Loads FSL TFLite model and class names for two-hand recognition."""
    global interpreter_fsl, input_details_fsl, output_details_fsl, CLASS_NAMES_FSL, is_initialized_fsl

    if is_initialized_fsl:
        return True

    print("Initializing resources for FSL sign logic (two-hand model)...")
    try:
        # Load TFLite Model
        if interpreter_fsl is None:
            print(f"Loading FSL TFLite model from: {MODEL_PATH}")
            interpreter_fsl = tf.lite.Interpreter(model_path=MODEL_PATH)
            interpreter_fsl.allocate_tensors()
            input_details_fsl = interpreter_fsl.get_input_details()
            output_details_fsl = interpreter_fsl.get_output_details()
            print("FSL TFLite model loaded successfully.")

        # Load Class Names
        if not CLASS_NAMES_FSL:
            print(f"Loading FSL class names from: {CLASS_MAPPING_FILE}")
            with open(CLASS_MAPPING_FILE, 'rb') as f:
                data = pickle.load(f)
            CLASS_NAMES_FSL = data['class_names'] if 'class_names' in data else data
            print(f"FSL Class names loaded: {len(CLASS_NAMES_FSL)} classes found.")

        is_initialized_fsl = True
        print("FSL resource initialization complete.")
        return True

    except FileNotFoundError as e:
        print(f"Error: File not found during FSL initialization - {e}")
        interpreter_fsl, is_initialized_fsl = None, False
        return False
    except Exception as e:
        print(f"Error during FSL resource initialization: {e}")
        interpreter_fsl, is_initialized_fsl = None, False
        return False

def predict_landmarks_fsl(landmarks_data):
    """
    Predict FSL sign from normalized landmark data (two hands).
    
    Args:
        landmarks_data: List of 84 normalized landmark values (21 landmarks * 2 coordinates * 2 hands)
    
    Returns:
        dict: {"sign": predicted_letter, "confidence": confidence_value}
    """
    global interpreter_fsl, input_details_fsl, output_details_fsl, CLASS_NAMES_FSL, is_initialized_fsl

    if not is_initialized_fsl:
        initialize_resources_fsl()

    if not is_initialized_fsl:
        return {"sign": "Initialization Error", "confidence": 0.0}

    try:
        # Expecting 84 values for two hands (21 landmarks * 2 coordinates * 2 hands)
        expected_length = 84
        if len(landmarks_data) != expected_length:
            print(f"Error: Expected {expected_length} landmarks, got {len(landmarks_data)}")
            return {"sign": "Invalid landmark count", "confidence": 0.0}

        # Prepare input for TFLite model
        landmark_input = np.array([landmarks_data], dtype=input_details_fsl[0]['dtype'])
        
        # Check input shape
        if landmark_input.shape[1:] != tuple(input_details_fsl[0]['shape'][1:]):
            print(f"Error: Input shape {landmark_input.shape[1:]} doesn't match expected {input_details_fsl[0]['shape'][1:]}")
            return {"sign": "Shape Error", "confidence": 0.0}

        # Run prediction
        interpreter_fsl.set_tensor(input_details_fsl[0]['index'], landmark_input)
        interpreter_fsl.invoke()
        prediction = interpreter_fsl.get_tensor(output_details_fsl[0]['index'])
        
        predicted_class_index = np.argmax(prediction[0])
        confidence = float(np.max(prediction[0]))

        if confidence >= MIN_PREDICTION_CONFIDENCE_FSL:
            predicted_letter = CLASS_NAMES_FSL[predicted_class_index]
            return {"sign": predicted_letter, "confidence": confidence}
        else:
            return {"sign": "Low Confidence", "confidence": confidence}

    except Exception as e:
        print(f"Error during FSL prediction: {e}")
        return {"sign": "Prediction Error", "confidence": 0.0}

def get_available_signs_fsl():
    """Returns the list of FSL class names."""
    global CLASS_NAMES_FSL, is_initialized_fsl
    
    if not is_initialized_fsl:
        initialize_resources_fsl()
    
    return CLASS_NAMES_FSL
