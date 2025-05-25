document.addEventListener('DOMContentLoaded', function () {
    const predictionTextElement = document.getElementById('prediction_text');
    const confidenceTextElement = document.getElementById('confidence_text');
    const submissionNotesTextarea = document.getElementById('submission-notes');
    const stabilityTimerTextElement = document.getElementById('stability_timer_text');
    const startCameraButton = document.getElementById('start_camera_assignment_btn');
    const cameraPlaceholderDiv = document.getElementById('video_feed_placeholder_text');
    const videoPlayer = document.getElementById('webcam-video-assignment'); // New video element
    const canvasElement = document.getElementById('webcam-canvas-assignment'); // New canvas element
    const socketStatusElement = document.getElementById('socket-status-assignment');

    let recordedSignAttempts = [];
    let lastPrediction = "";
    let stableCounter = 0;
    const STABILITY_THRESHOLD = 15; // Approx 3 seconds if interval is 200ms (15 * 200ms = 3000ms)
    let frameSenderInterval = null;
    let localStream = null;

    // --- Socket.IO Setup ---
    const socket = io();

    socket.on('connect', () => {
        console.log('Assignment: Connected to WebSocket server.');
        if (socketStatusElement) socketStatusElement.textContent = 'Socket: Connected';
    });

    socket.on('disconnect', () => {
        console.log('Assignment: Disconnected from WebSocket server.');
        if (socketStatusElement) socketStatusElement.textContent = 'Socket: Disconnected. Please refresh.';
        stopFrameSending();
    });

    socket.on('status', (data) => {
        console.log('Assignment: Server status:', data.msg);
        if (socketStatusElement) socketStatusElement.textContent = `Socket: ${data.msg}`;
    });

    socket.on('prediction_result', (data) => {
        const sign = data.prediction;
        const confidence = data.confidence;

        if (predictionTextElement) predictionTextElement.textContent = `Prediction: ${sign}`;
        if (confidenceTextElement) confidenceTextElement.textContent = `Confidence: ${confidence ? confidence.toFixed(2) : 'N/A'}`;

        if (sign && sign.trim() !== "") {
            if (sign === lastPrediction) {
                stableCounter++;
                const lowerSignCompare = sign.toLowerCase().trim();
                
                const nonStableStates = ["ready", "ready...", "no prediction", "low confidence", "no hand detected", "processing error", "system error", "unknown", "detect error", "landmark count error", "error:", "initializing..."];

                if (!nonStableStates.some(s => lowerSignCompare.includes(s.toLowerCase())) && stableCounter > 0 && stableCounter < STABILITY_THRESHOLD) {
                    if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = `Holding: ${stableCounter}/${STABILITY_THRESHOLD}`;
                } else {
                    if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
                }

                if (stableCounter === STABILITY_THRESHOLD) {
                    if (!nonStableStates.some(s => lowerSignCompare.includes(s.toLowerCase()))) {
                        const currentNotes = submissionNotesTextarea.value;
                        const separator = currentNotes.length > 0 ? " " : "";
                        
                        submissionNotesTextarea.value += separator + sign; 
                        recordedSignAttempts.push({ sign: sign, confidence: confidence });
                        console.log("Recorded attempt:", { sign: sign, confidence: confidence });
                        
                        if(predictionTextElement) predictionTextElement.style.color = '#28a745'; // Green
                        setTimeout(() => {
                            if(predictionTextElement) predictionTextElement.style.color = ''; // Reset color
                        }, 500);
                        if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Added to notes!";
                        setTimeout(() => { 
                            if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
                        }, 3000);
                    } else {
                        if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
                    }
                    stableCounter = 0; 
                }
            } else {
                lastPrediction = sign; 
                stableCounter = 0;
                if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
            }
        } else {
            if(predictionTextElement) predictionTextElement.textContent = "Prediction: ...";
            lastPrediction = ""; 
            stableCounter = 0;
            if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
        }
    });

    socket.on('prediction_error', (data) => {
        console.error('Assignment: Prediction error from server:', data.error);
        if (predictionTextElement) predictionTextElement.textContent = `Prediction Error: ${data.error}`;
        if (confidenceTextElement) confidenceTextElement.textContent = `Confidence: N/A`;
    });
    // --- End Socket.IO Setup ---

    async function startCameraAndPractice() {
        console.log("Start Camera & Practice button clicked.");
        if (!videoPlayer || !canvasElement) {
            console.error("Video player or canvas element not found for assignment!");
            if (cameraPlaceholderDiv) cameraPlaceholderDiv.textContent = "Camera elements missing.";
            return;
        }

        try {
            localStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            videoPlayer.srcObject = localStream;
            videoPlayer.style.display = 'block';
            if (cameraPlaceholderDiv) cameraPlaceholderDiv.style.display = 'none';
            if (startCameraButton) {
                startCameraButton.disabled = true;
                startCameraButton.textContent = "Camera Active";
            }

            videoPlayer.onloadedmetadata = () => {
                canvasElement.width = videoPlayer.videoWidth;
                canvasElement.height = videoPlayer.videoHeight;
                startFrameSending();
                console.log("Assignment: Camera started and frame sending initiated.");
            };
        } catch (err) {
            console.error("Error accessing webcam for assignment:", err);
            if (cameraPlaceholderDiv) cameraPlaceholderDiv.textContent = "Could not access webcam. Check permissions.";
            if (startCameraButton) {
                startCameraButton.disabled = false;
                startCameraButton.textContent = "Start Camera & Practice";
            }
        }
    }

    function stopCamera() {
        stopFrameSending();
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
            console.log("Assignment: Camera stream stopped.");
        }
        if (videoPlayer) {
            videoPlayer.srcObject = null;
            videoPlayer.style.display = 'none';
        }
        if (cameraPlaceholderDiv) cameraPlaceholderDiv.style.display = 'block';
        if (startCameraButton) {
            startCameraButton.disabled = false;
            startCameraButton.textContent = "Start Camera & Practice";
        }
        if (predictionTextElement) predictionTextElement.textContent = "Prediction: ...";
        if (confidenceTextElement) confidenceTextElement.textContent = "Confidence: ...";
        if (stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
    }

    function startFrameSending() {
        if (frameSenderInterval) clearInterval(frameSenderInterval);
        if (!socket.connected) {
            console.warn("Assignment: Socket not connected. Cannot send frames.");
            if (socketStatusElement) socketStatusElement.textContent = 'Socket: Not connected. Retrying...';
            return;
        }

        frameSenderInterval = setInterval(() => {
            if (videoPlayer.readyState >= videoPlayer.HAVE_CURRENT_DATA && canvasElement && socket.connected) {
                const context = canvasElement.getContext('2d');
                context.drawImage(videoPlayer, 0, 0, canvasElement.width, canvasElement.height);
                const dataURL = canvasElement.toDataURL('image/jpeg', 0.8);
                socket.emit('process_frame', { image_data_url: dataURL });
            }
        }, 200); // Send frame every 200ms (5 FPS)
    }

    function stopFrameSending() {
        if (frameSenderInterval) {
            clearInterval(frameSenderInterval);
            frameSenderInterval = null;
            console.log("Assignment: Frame sending stopped.");
        }
    }

    if (startCameraButton) {
        startCameraButton.addEventListener('click', startCameraAndPractice);
    }
    
    const form = document.querySelector('form[action*="/submit_assignment_work"]');
    if (form) {
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'sign_attempts_json';
        form.appendChild(hiddenInput);

        form.addEventListener('submit', function() {
            hiddenInput.value = JSON.stringify(recordedSignAttempts);
        });
    }

    window.addEventListener('pagehide', function() {
        stopCamera();
        if (socket && socket.connected) {
            socket.disconnect();
        }
    });

    if (submissionNotesTextarea) {
        submissionNotesTextarea.addEventListener('keydown', function(event) {
            if (event.key === 'Backspace' || 
                event.key === 'Delete' || 
                event.key.startsWith('Arrow') ||
                event.key === 'Home' || 
                event.key === 'End' ||
                (event.ctrlKey && event.key.toLowerCase() === 'a')) {
                return; 
            }
            if (event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey) {
                event.preventDefault();
            }
        });
    }

    // Initial UI states
    if(predictionTextElement) predictionTextElement.textContent = "Prediction: ...";
    if(confidenceTextElement) confidenceTextElement.textContent = "Confidence: ...";
    if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = "Stability: ...";
    if(socketStatusElement) socketStatusElement.textContent = "Socket: Initializing...";

});
