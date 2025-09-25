document.addEventListener('DOMContentLoaded', async function () {
    // --- DOM Elements ---
    const predictionTextElement = document.getElementById('prediction_text');
    const submissionNotesTextarea = document.getElementById('submission-notes');
    const stabilityTimerTextElement = document.getElementById('stability_timer_text');
    const startCameraButton = document.getElementById('start_camera_assignment_btn');
    const videoElement = document.getElementById('webcam');
    const canvasElement = document.getElementById('output_canvas');
    const canvasCtx = canvasElement.getContext('2d');
    const placeholderText = document.getElementById('video_feed_placeholder_text');

    // --- App State ---
    let handLandmarker = null;
    let tfModel = null;
    let classNames = [];
    let lastVideoTime = -1;
    let isCameraActive = false;

    // --- Prediction Smoothing Config ---
    const PREDICTION_BUFFER_SIZE = 10;
    const SMOOTHING_THRESHOLD = 0.9;
    const MIN_PREDICTION_CONFIDENCE = 0.90;
    const STABILITY_THRESHOLD = 25; // Frames to hold for a stable prediction
    const NON_VALID_SIGN_STATES = ["Unknown", "No hand detected", "...", "Low Confidence"];

    // --- Prediction State ---
    let prediction_buffer = [];
    let stableCounter = 0;
    let lastPrediction = "";

    // --- Paths to Model Files ---
    const TFLITE_MODEL_PATH = '/static/model/landmark_model.tflite';
    const CLASS_NAMES_PATH = '/static/model/class_names.json';
    const MEDIAPIPE_WASM_PATH = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm";


    // --- Initialization ---
    const initializeModels = async () => {
        try {
            // 1. Initialize MediaPipe Hand Landmarker
            const vision = await window.vision.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_PATH);
            handLandmarker = await window.vision.HandLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`,
                    delegate: "GPU"
                },
                runningMode: "VIDEO",
                numHands: 1
            });
            console.log("Hand Landmarker model loaded.");

            // 2. Load TensorFlow.js Model
            tfModel = await tflite.loadTFLiteModel(TFLITE_MODEL_PATH);
            console.log("TFLite model loaded.");
            
            // 3. Load Class Names
            const response = await fetch(CLASS_NAMES_PATH);
            classNames = await response.json();
            console.log("Class names loaded:", classNames);

            predictionTextElement.textContent = "Models loaded. Ready to start camera.";
            startCameraButton.disabled = false;

        } catch (error) {
            console.error("Error loading models:", error);
            predictionTextElement.textContent = "Error loading models. Please refresh.";
            startCameraButton.disabled = true;
        }
    };

    // --- Main Prediction Loop ---
    const predictWebcam = async () => {
        if (!isCameraActive) return;

        const video = videoElement;
        if (video.currentTime !== lastVideoTime) {
            lastVideoTime = video.currentTime;

            // Set canvas size
            canvasElement.width = video.videoWidth;
            canvasElement.height = video.videoHeight;

            const handLandmarkerResult = handLandmarker.detectForVideo(video, performance.now());
            
            canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

            if (handLandmarkerResult.landmarks.length > 0) {
                const landmarks = handLandmarkerResult.landmarks[0];
                
                // Draw landmarks on canvas
                for (const landmark of landmarks) {
                    const x = landmark.x * canvasElement.width;
                    const y = landmark.y * canvasElement.height;
                    canvasCtx.beginPath();
                    canvasCtx.arc(x, y, 5, 0, 2 * Math.PI);
                    canvasCtx.fillStyle = 'aqua';
                    canvasCtx.fill();
                }

                // --- Process landmarks for prediction ---
                try {
                    const wrist = landmarks[0];
                    const origin_x = wrist.x;
                    const origin_y = wrist.y;
                    
                    const mcp_middle = landmarks[9]; // MIDDLE_FINGER_MCP
                    let scale = Math.sqrt(Math.pow(mcp_middle.x - origin_x, 2) + Math.pow(mcp_middle.y - origin_y, 2));
                    scale = Math.max(scale, 1e-6);

                    const landmarks_normalized = [];
                    for (const landmark of landmarks) {
                        landmarks_normalized.push((landmark.x - origin_x) / scale);
                        landmarks_normalized.push((landmark.y - origin_y) / scale);
                    }

                    if (landmarks_normalized.length === 42) {
                        const inputTensor = tf.tensor2d([landmarks_normalized]);
                        const prediction = tfModel.predict(inputTensor);
                        const predictionData = await prediction.data();
                        
                        const predicted_class_index = predictionData.indexOf(Math.max(...predictionData));
                        const confidence = Math.max(...predictionData);

                        let instantaneous_prediction;
                        if (confidence >= MIN_PREDICTION_CONFIDENCE) {
                            instantaneous_prediction = classNames[predicted_class_index];
                        } else {
                            instantaneous_prediction = "Low Confidence";
                        }
                        predictionTextElement.textContent = `Detect: ${instantaneous_prediction} (${(confidence * 100).toFixed(2)}%)`;
                        processPrediction(instantaneous_prediction);

                    }
                } catch (error) {
                    console.error("Error during landmark processing or prediction:", error);
                    processPrediction("Error");
                }

            } else {
                predictionTextElement.textContent = "No hand detected";
                processPrediction("No hand detected");
            }
        }

        // Call this function again to keep predicting when the browser is ready.
        window.requestAnimationFrame(predictWebcam);
    };

    // --- Prediction Smoothing and Submission Logic ---
    function processPrediction(prediction) {
        if (prediction === lastPrediction) {
            stableCounter++;
        } else {
            lastPrediction = prediction;
            stableCounter = 0;
        }

        // Update stability timer text
        if (stableCounter > 0 && stableCounter < STABILITY_THRESHOLD && !NON_VALID_SIGN_STATES.includes(prediction)) {
            stabilityTimerTextElement.textContent = `Holding: ${stableCounter}/${STABILITY_THRESHOLD}`;
        } else {
            stabilityTimerTextElement.textContent = "";
        }

        // If prediction is stable, add to notes
        if (stableCounter === STABILITY_THRESHOLD && !NON_VALID_SIGN_STATES.includes(prediction)) {
            const currentNotes = submissionNotesTextarea.value;
            const separator = currentNotes.length > 0 ? " " : "";
            submissionNotesTextarea.value += separator + prediction;
            
            // Visual feedback
            predictionTextElement.style.color = '#28a745';
            setTimeout(() => { predictionTextElement.style.color = '#007bff'; }, 500);
            stabilityTimerTextElement.textContent = "Added to notes!";
            setTimeout(() => { stabilityTimerTextElement.textContent = ""; }, 2000);
            
            stableCounter = 0; // Reset after adding
        }
    }


    // --- Event Listeners ---
    startCameraButton.addEventListener('click', async () => {
        if (isCameraActive) {
            // Stop the camera
            isCameraActive = false;
            let stream = videoElement.srcObject;
            let tracks = stream.getTracks();
            tracks.forEach(track => track.stop());
            videoElement.srcObject = null;
            
            videoElement.style.display = 'none';
            canvasElement.style.display = 'none';
            placeholderText.style.display = 'block';
            startCameraButton.textContent = "Start Camera & Practice";
            predictionTextElement.textContent = "Camera off. Press Start to begin.";

        } else {
            // Start the camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                videoElement.srcObject = stream;
                videoElement.style.display = 'block';
                canvasElement.style.display = 'block';
                placeholderText.style.display = 'none';
                isCameraActive = true;
                startCameraButton.textContent = "Stop Camera";
                startCameraButton.disabled = true; // Disable while it's starting

                videoElement.onloadedmetadata = () => {
                    startCameraButton.disabled = false;
                    predictWebcam(); // Start the prediction loop
                };

            } catch (error) {
                console.error("Error accessing webcam:", error);
                predictionTextElement.textContent = "Could not access webcam. Please check permissions.";
            }
        }
    });

    // --- Final Setup ---
    startCameraButton.disabled = true; // Disable until models are loaded
    initializeModels();
});
