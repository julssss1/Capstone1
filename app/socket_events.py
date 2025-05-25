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
    print("[Socket Event] 'process_frame' received.")
    try:
        image_data_url = data.get('image_data_url')
        if not image_data_url:
            print("[Socket Event] No image_data_url in received data.")
            emit('prediction_error', {'error': 'No image data received.'})
            return
        
        print(f"[Socket Event] image_data_url received (first 50 chars): {image_data_url[:50]}")

        # Extract base64 data
        header, encoded = image_data_url.split(',', 1)
        print("[Socket Event] Image data split into header and encoded data.")
        
        # Decode base64 string to bytes
        image_bytes = base64.b64decode(encoded)
        print(f"[Socket Event] Decoded image_bytes length: {len(image_bytes)}")
        
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        print(f"[Socket Event] Converted to numpy array, shape: {nparr.shape}")
        
        # Decode image array to OpenCV format
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            print("[Socket Event] cv2.imdecode returned None. Image decoding failed.")
            emit('prediction_error', {'error': 'Could not decode image.'})
            return
        
        print(f"[Socket Event] Image decoded successfully, shape: {img.shape}")

        # Ensure sign_logic resources are initialized (idempotent check inside sign_logic)
        # This is important if the app worker restarted and lost the initialized state.
        if not sign_logic.is_initialized:
            print("[Socket Event] sign_logic not initialized. Attempting to initialize...")
            if not sign_logic.initialize_resources(): # This loads model, hands, etc.
                print("[Socket Event] CRITICAL: sign_logic.initialize_resources() failed.")
                emit('prediction_error', {'error': 'Server-side model/resource initialization failed.'})
                return
            print("[Socket Event] sign_logic.initialize_resources() successful.")
        else:
            print("[Socket Event] sign_logic already initialized.")

        print("[Socket Event] Calling sign_logic.get_prediction_for_frame...")
        prediction, confidence = sign_logic.get_prediction_for_frame(
            img, 
            sign_logic.hands, 
            sign_logic.model, 
            sign_logic.CLASS_NAMES
        )
        print(f"[Socket Event] Prediction from sign_logic: '{prediction}', Confidence: {confidence}")

        if prediction:
            print(f"[Socket Event] Emitting 'prediction_result': {{'prediction': '{prediction}', 'confidence': {confidence}}}")
            emit('prediction_result', {'prediction': prediction, 'confidence': confidence})
        else:
            # This case might be covered by "No hand detected" or "Error" from get_prediction_for_frame
            # but we log it explicitly if prediction is None or empty.
            print(f"[Socket Event] Prediction was empty or None. Emitting default error/status.")
            emit('prediction_result', {'prediction': 'Processing failed or no hand', 'confidence': 0.0})

    except Exception as e:
        print(f"[Socket Event] EXCEPTION in 'process_frame': {e}")
        emit('prediction_error', {'error': str(e)})
