"""
API routes for client-side interactions
"""
from flask import request, jsonify
from . import bp
from app.utils import login_required, role_required
import numpy as np
import tensorflow as tf
import pickle
import os

# Load model and class names globally
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, '..', '..', 'landmark_model.tflite')
LANDMARK_FILE = os.path.join(CURRENT_DIR, '..', '..', 'hand_landmarks.pkl')

# FSL model paths
MODEL_PATH_FSL = os.path.join(CURRENT_DIR, '..', '..', 'landmark_model_fsl.tflite')
CLASS_MAPPING_FILE_FSL = os.path.join(CURRENT_DIR, '..', '..', 'class_mapping_fsl.pkl')

interpreter = None
input_details = None
output_details = None
CLASS_NAMES = []

# FSL model variables
interpreter_fsl = None
input_details_fsl = None
output_details_fsl = None
CLASS_NAMES_FSL = []

def initialize_model():
    """Initialize the TFLite model"""
    global interpreter, input_details, output_details, CLASS_NAMES
    
    if interpreter is not None:
        return True
    
    try:
        print(f"Loading TFLite model from: {MODEL_PATH}")
        interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        print(f"Loading class names from: {LANDMARK_FILE}")
        with open(LANDMARK_FILE, 'rb') as f:
            data = pickle.load(f)
        CLASS_NAMES = data['class_names']
        
        print(f"Model initialized successfully. {len(CLASS_NAMES)} classes loaded.")
        return True
    except Exception as e:
        print(f"Error initializing model: {e}")
        return False

@bp.route('/api/predict_landmarks', methods=['POST'])
@login_required
@role_required('Student')
def predict_landmarks():
    """
    Predict sign from normalized hand landmarks
    Expects JSON: {"landmarks": [42 floats]}
    Returns JSON: {"sign": "A", "confidence": 0.95}
    """
    try:
        # Initialize model if not already done
        if not initialize_model():
            return jsonify({
                'error': 'Model not initialized',
                'sign': 'Error',
                'confidence': 0.0
            }), 500
        
        # Get landmarks from request
        data = request.get_json()
        if not data or 'landmarks' not in data:
            return jsonify({
                'error': 'No landmarks provided',
                'sign': 'Error',
                'confidence': 0.0
            }), 400
        
        landmarks = data['landmarks']
        
        # Validate landmarks
        if len(landmarks) != 42:
            return jsonify({
                'error': f'Expected 42 landmarks, got {len(landmarks)}',
                'sign': 'Error',
                'confidence': 0.0
            }), 400
        
        # Prepare input for TFLite model
        landmark_input = np.array([landmarks], dtype=input_details[0]['dtype'])
        
        # Run inference
        interpreter.set_tensor(input_details[0]['index'], landmark_input)
        interpreter.invoke()
        prediction = interpreter.get_tensor(output_details[0]['index'])
        
        # Get predicted class
        predicted_class_index = np.argmax(prediction[0])
        confidence = float(np.max(prediction[0]))
        
        # Apply confidence threshold (90%)
        MIN_CONFIDENCE = 0.90
        
        if confidence < MIN_CONFIDENCE:
            # Low confidence - don't return a sign
            print(f"Low confidence: {confidence:.4f} (threshold: {MIN_CONFIDENCE})")
            return jsonify({
                'sign': 'Low Confidence',
                'confidence': confidence
            })
        
        if predicted_class_index < len(CLASS_NAMES):
            predicted_sign = CLASS_NAMES[predicted_class_index]
        else:
            predicted_sign = "Unknown"
        
        # Debug logging
        print(f"Prediction: {predicted_sign}, Confidence: {confidence:.4f}")
        
        return jsonify({
            'sign': predicted_sign,
            'confidence': confidence
        })
        
    except Exception as e:
        print(f"Error in predict_landmarks: {e}")
        return jsonify({
            'error': str(e),
            'sign': 'Error',
            'confidence': 0.0
        }), 500

def initialize_model_fsl():
    """Initialize the FSL TFLite model for two-hand recognition"""
    global interpreter_fsl, input_details_fsl, output_details_fsl, CLASS_NAMES_FSL
    
    if interpreter_fsl is not None:
        return True
    
    try:
        print(f"Loading FSL TFLite model from: {MODEL_PATH_FSL}")
        interpreter_fsl = tf.lite.Interpreter(model_path=MODEL_PATH_FSL)
        interpreter_fsl.allocate_tensors()
        input_details_fsl = interpreter_fsl.get_input_details()
        output_details_fsl = interpreter_fsl.get_output_details()
        
        print(f"Loading FSL class names from: {CLASS_MAPPING_FILE_FSL}")
        with open(CLASS_MAPPING_FILE_FSL, 'rb') as f:
            data = pickle.load(f)
        CLASS_NAMES_FSL = data['class_names'] if 'class_names' in data else data
        
        print(f"FSL Model initialized successfully. {len(CLASS_NAMES_FSL)} classes loaded.")
        return True
    except Exception as e:
        print(f"Error initializing FSL model: {e}")
        return False

@bp.route('/api/predict_landmarks_fsl', methods=['POST'])
@login_required
@role_required('Student')
def predict_landmarks_fsl():
    """
    Predict FSL sign from normalized hand landmarks (two hands)
    Expects JSON: {"landmarks": [84 floats]} (21 landmarks * 2 coords * 2 hands)
    Returns JSON: {"sign": "A", "confidence": 0.95}
    """
    try:
        # Initialize FSL model if not already done
        if not initialize_model_fsl():
            return jsonify({
                'error': 'FSL Model not initialized',
                'sign': 'Error',
                'confidence': 0.0
            }), 500
        
        # Get landmarks from request
        data = request.get_json()
        if not data or 'landmarks' not in data:
            return jsonify({
                'error': 'No landmarks provided',
                'sign': 'Error',
                'confidence': 0.0
            }), 400
        
        landmarks = data['landmarks']
        
        # Validate landmarks (84 for two hands: 21 landmarks * 2 coords * 2 hands)
        expected_length = 84
        if len(landmarks) != expected_length:
            return jsonify({
                'error': f'Expected {expected_length} landmarks for two hands, got {len(landmarks)}',
                'sign': 'Error',
                'confidence': 0.0
            }), 400
        
        # Prepare input for TFLite model
        landmark_input = np.array([landmarks], dtype=input_details_fsl[0]['dtype'])
        
        # Run inference
        interpreter_fsl.set_tensor(input_details_fsl[0]['index'], landmark_input)
        interpreter_fsl.invoke()
        prediction = interpreter_fsl.get_tensor(output_details_fsl[0]['index'])
        
        # Get predicted class
        predicted_class_index = np.argmax(prediction[0])
        confidence = float(np.max(prediction[0]))
        
        # Apply confidence threshold (90%)
        MIN_CONFIDENCE = 0.90
        
        if confidence < MIN_CONFIDENCE:
            # Low confidence - don't return a sign
            print(f"FSL Low confidence: {confidence:.4f} (threshold: {MIN_CONFIDENCE})")
            return jsonify({
                'sign': 'Low Confidence',
                'confidence': confidence
            })
        
        if predicted_class_index < len(CLASS_NAMES_FSL):
            predicted_sign = CLASS_NAMES_FSL[predicted_class_index]
        else:
            predicted_sign = "Unknown"
        
        # Debug logging
        print(f"FSL Prediction: {predicted_sign}, Confidence: {confidence:.4f}")
        
        return jsonify({
            'sign': predicted_sign,
            'confidence': confidence
        })
        
    except Exception as e:
        print(f"Error in predict_landmarks_fsl: {e}")
        return jsonify({
            'error': str(e),
            'sign': 'Error',
            'confidence': 0.0
        }), 500
