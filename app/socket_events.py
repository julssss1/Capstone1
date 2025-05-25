import base64
import cv2
import numpy as np
from flask_socketio import emit
from . import socketio  # Import the socketio instance from __init__.py
from . import sign_logic # Import your sign_logic module

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'msg': 'Connected to sign recognition server.'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('process_frame')
def handle_process_frame(data):
    try:
        image_data_url = data.get('image_data_url')
        if not image_data_url:
            emit('prediction_error', {'error': 'No image data received.'})
            return

        # Extract base64 data
        header, encoded = image_data_url.split(',', 1)
        
        # Decode base64 string to bytes
        image_bytes = base64.b64decode(encoded)
        
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        
        # Decode image array to OpenCV format
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            emit('prediction_error', {'error': 'Could not decode image.'})
            print("Error: Could not decode image from base64 string.")
            return

        # Process the frame using your sign_logic
        # Assuming sign_logic has a function like `get_prediction_from_frame`
        # You might need to adjust this part based on your actual sign_logic.py structure
        
        # For now, let's assume process_frame_for_landmarks_and_prediction exists
        # and can take a raw cv2 image and return a prediction string.
        # This function might need to be adapted or created in sign_logic.py
        # to not rely on flask.current_app if it does.
        
        # Placeholder: direct call to a potentially modified sign_logic function
        # This part needs careful review of sign_logic.py
        # Use the new function from sign_logic
        prediction, confidence = sign_logic.get_prediction_for_frame(
            img, 
            sign_logic.hands, 
            sign_logic.model, 
                            sign_logic.CLASS_NAMES # Use CLASS_NAMES instead of undefined 'actions'
        )

        if prediction:
            emit('prediction_result', {'prediction': prediction, 'confidence': confidence})
        else:
            # This case might be covered by "No hand detected" or "Error" from get_prediction_for_frame
            emit('prediction_result', {'prediction': 'Processing failed or no hand', 'confidence': 0.0})

    except Exception as e:
        print(f"Error processing frame: {e}")
        emit('prediction_error', {'error': str(e)})
