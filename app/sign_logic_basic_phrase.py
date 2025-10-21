import numpy as np
import tensorflow as tf
import pickle
import os

# Configuration for Basic Phrase model
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, '..', 'fsl_model.tflite')
LABELS_FILE = os.path.join(CURRENT_DIR, '..', 'labels.pkl')
MODEL_METADATA_FILE = os.path.join(CURRENT_DIR, '..', 'model_metadata.pkl')

# Model & Resources
interpreter_basic_phrase = None
input_details_basic_phrase = None
output_details_basic_phrase = None
CLASS_NAMES_BASIC_PHRASE = []
is_initialized_basic_phrase = False
MIN_PREDICTION_CONFIDENCE_BASIC_PHRASE = 0.90

def initialize_resources_basic_phrase():
    """Loads Basic Phrase TFLite model and class names."""
    global interpreter_basic_phrase, input_details_basic_phrase, output_details_basic_phrase
    global CLASS_NAMES_BASIC_PHRASE, is_initialized_basic_phrase

    if is_initialized_basic_phrase:
        return True

    print("Initializing resources for Basic Phrase sign logic...")
    try:
        # Load TFLite Model
        if interpreter_basic_phrase is None:
            print(f"Loading Basic Phrase TFLite model from: {MODEL_PATH}")
            interpreter_basic_phrase = tf.lite.Interpreter(model_path=MODEL_PATH)
            interpreter_basic_phrase.allocate_tensors()
            input_details_basic_phrase = interpreter_basic_phrase.get_input_details()
            output_details_basic_phrase = interpreter_basic_phrase.get_output_details()
            print("Basic Phrase TFLite model loaded successfully.")

        # Load Class Names from labels.pkl
        if not CLASS_NAMES_BASIC_PHRASE:
            print(f"Loading Basic Phrase class names from: {LABELS_FILE}")
            with open(LABELS_FILE, 'rb') as f:
                labels_data = pickle.load(f)
            # Handle different possible formats
            if isinstance(labels_data, dict):
                CLASS_NAMES_BASIC_PHRASE = labels_data.get('class_names', labels_data.get('labels', []))
            elif isinstance(labels_data, list):
                CLASS_NAMES_BASIC_PHRASE = labels_data
            else:
                CLASS_NAMES_BASIC_PHRASE = list(labels_data)
            
            print(f"Basic Phrase class names loaded: {len(CLASS_NAMES_BASIC_PHRASE)} classes found.")
            
            # Load metadata if available
            if os.path.exists(MODEL_METADATA_FILE):
                print(f"Loading model metadata from: {MODEL_METADATA_FILE}")
                with open(MODEL_METADATA_FILE, 'rb') as f:
                    metadata = pickle.load(f)
                print(f"Model metadata: {metadata}")

        is_initialized_basic_phrase = True
        print("Basic Phrase resource initialization complete.")
        return True

    except FileNotFoundError as e:
        print(f"Error: File not found during Basic Phrase initialization - {e}")
        interpreter_basic_phrase, is_initialized_basic_phrase = None, False
        return False
    except Exception as e:
        print(f"Error during Basic Phrase resource initialization: {e}")
        interpreter_basic_phrase, is_initialized_basic_phrase = None, False
        return False

def predict_landmarks_basic_phrase(landmarks_data):
    """
    Predict Basic Phrase sign from normalized landmark data.
    
    Args:
        landmarks_data: List of normalized landmark values
    
    Returns:
        dict: {"sign": predicted_phrase, "confidence": confidence_value}
    """
    global interpreter_basic_phrase, input_details_basic_phrase, output_details_basic_phrase
    global CLASS_NAMES_BASIC_PHRASE, is_initialized_basic_phrase

    if not is_initialized_basic_phrase:
        initialize_resources_basic_phrase()

    if not is_initialized_basic_phrase:
        return {"sign": "Initialization Error", "confidence": 0.0}

    try:
        # Prepare input for TFLite model
        landmark_input = np.array([landmarks_data], dtype=input_details_basic_phrase[0]['dtype'])
        
        # Check input shape
        expected_shape = tuple(input_details_basic_phrase[0]['shape'][1:])
        if landmark_input.shape[1:] != expected_shape:
            print(f"Error: Input shape {landmark_input.shape[1:]} doesn't match expected {expected_shape}")
            return {"sign": "Shape Error", "confidence": 0.0}

        # Run prediction
        interpreter_basic_phrase.set_tensor(input_details_basic_phrase[0]['index'], landmark_input)
        interpreter_basic_phrase.invoke()
        prediction = interpreter_basic_phrase.get_tensor(output_details_basic_phrase[0]['index'])
        
        predicted_class_index = np.argmax(prediction[0])
        confidence = float(np.max(prediction[0]))

        if confidence >= MIN_PREDICTION_CONFIDENCE_BASIC_PHRASE:
            predicted_phrase = CLASS_NAMES_BASIC_PHRASE[predicted_class_index]
            return {"sign": predicted_phrase, "confidence": confidence}
        else:
            return {"sign": "Low Confidence", "confidence": confidence}

    except Exception as e:
        print(f"Error during Basic Phrase prediction: {e}")
        return {"sign": "Prediction Error", "confidence": 0.0}

def get_available_signs_basic_phrase():
    """Returns the list of Basic Phrase class names."""
    global CLASS_NAMES_BASIC_PHRASE, is_initialized_basic_phrase
    
    if not is_initialized_basic_phrase:
        initialize_resources_basic_phrase()
    
    return CLASS_NAMES_BASIC_PHRASE
