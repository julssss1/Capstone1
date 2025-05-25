document.addEventListener('DOMContentLoaded', function() {
    const startCameraButton = document.getElementById('start-camera-btn');
    const videoPlayer = document.getElementById('webcam-video'); // Changed from videoFeedElement
    const canvasElement = document.getElementById('webcam-canvas');
    const videoPlaceholderText = document.getElementById('video-placeholder-text');
    const feedbackElement = document.getElementById('feedback');
    const detectedSignDisplay = document.getElementById('detected-sign-display'); // For debug
    // const debugInfo = document.getElementById('debug-info'); // For debug
    const instructionText = document.getElementById('instruction-text');
    const targetImage = document.getElementById('target-image');
    const imagePlaceholderText = document.getElementById('image-placeholder-text');
    const signButtonsContainer = document.getElementById('sign-buttons');
    const signTipsArea = document.getElementById('sign-tips-area');
    const tipSignLetter = document.getElementById('tip-sign-letter');
    const tipText = document.getElementById('tip-text');

    const socketStatusElement = document.getElementById('socket-status');
    const predictionResultDisplayElement = document.getElementById('prediction-result-display');

    let frameSenderInterval = null;
    let currentPracticeSign = null;
    let successStartTime = null;
    const SUCCESS_HOLD_TIME = 1500; // ms
    let localStream = null; // To store the MediaStream object

    // const staticBaseUrl is expected to be set by inline script in the HTML template

    const signTips = {
        'A': "Make a fist, thumb alongside index finger.", 'B': "Flat hand, fingers together, thumb across palm.",
        'C': "Curve hand like 'C'.", 'D': "Index up, others form circle with thumb.",
        'E': "Fingers curl tightly, thumb tucked.", 'F': "'OK' sign, other fingers up.",
        'G': "Index points sideways, thumb up, others curled.", 'H': "Index/middle fingers point sideways, thumb tucked.",
        'I': "Pinky up, others curled, thumb across.", 'J': "Like 'I', draw 'J'.",
        'K': "Index/middle up like 'V', thumb between.", 'L': "Index up, thumb sideways ('L').",
        'M': "Thumb under index/middle/ring fingers pointing down.", 'N': "Thumb under index/middle fingers pointing down.",
        'O': "Form 'O' shape.", 'P': "Like 'K', pointing down.",
        'Q': "Like 'G', pointing down.", 'R': "Cross index/middle fingers.",
        'S': "Fist, thumb over fingers.", 'T': "Thumb under index finger.",
        'U': "Index/middle fingers up together.", 'V': "Like 'U', fingers spread.",
        'W': "Index/middle/ring fingers up, spread.", 'X': "Index finger hooked.",
        'Y': "Thumb and pinky out.", 'Z': "Draw 'Z' with index finger.",
        'Hello': "Wave hand from forehead outwards.", 'Thank You': "Flat hand chin to forward.",
        'I Love You': "Extend thumb, index, pinky.",
    };

    // --- Socket.IO Setup ---
    const socket = io();

    socket.on('connect', () => {
        console.log('Connected to WebSocket server.');
        if (socketStatusElement) socketStatusElement.textContent = 'Socket: Connected';
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket server.');
        if (socketStatusElement) socketStatusElement.textContent = 'Socket: Disconnected. Please refresh.';
        stopFrameSending();
    });

    socket.on('status', (data) => {
        console.log('Server status:', data.msg);
        if (socketStatusElement) socketStatusElement.textContent = `Socket: ${data.msg}`;
    });

    socket.on('prediction_result', (data) => {
        if (predictionResultDisplayElement) {
            predictionResultDisplayElement.textContent = `Prediction: ${data.prediction} (Conf: ${data.confidence ? data.confidence.toFixed(2) : 'N/A'})`;
        }
        if (detectedSignDisplay) { // For debug display if still used
            detectedSignDisplay.textContent = `Sign: ${data.prediction}, Conf: ${data.confidence ? data.confidence.toFixed(2) : 'N/A'}`;
        }
        updateFeedback(data.prediction); // Update main feedback logic
    });

    socket.on('prediction_error', (data) => {
        console.error('Prediction error from server:', data.error);
        if (predictionResultDisplayElement) predictionResultDisplayElement.textContent = `Prediction Error: ${data.error}`;
    });
    // --- End Socket.IO Setup ---

    if (startCameraButton) {
        startCameraButton.addEventListener('click', startCameraOnClick);
    }

    if (signButtonsContainer) {
        signButtonsContainer.addEventListener('click', function(event) {
            if (event.target.classList.contains('sign-btn')) {
                const sign = event.target.textContent;
                startPractice(sign);
                document.querySelectorAll('.sign-btn.active').forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
            }
        });
    }

    window.addEventListener('pagehide', function() {
        stopCamera(); // Stop camera and frame sending
        if (socket && socket.connected) {
            socket.disconnect();
        }
    });

    async function startCameraOnClick() {
        console.log("Start Camera button clicked on Dashboard.");
        if (!videoPlayer || !canvasElement) {
            console.error("Video player or canvas element not found!");
            if (videoPlaceholderText) videoPlaceholderText.textContent = "Camera elements missing.";
            return;
        }

        try {
            localStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            videoPlayer.srcObject = localStream;
            videoPlayer.style.display = 'block';
            if (videoPlaceholderText) videoPlaceholderText.style.display = 'none';
            if (startCameraButton) startCameraButton.classList.add('hidden'); // Hide start button

            // Wait for video to be ready to get correct dimensions
            videoPlayer.onloadedmetadata = () => {
                canvasElement.width = videoPlayer.videoWidth;
                canvasElement.height = videoPlayer.videoHeight;
                startFrameSending();
                console.log("Camera started and frame sending initiated.");
            };
        } catch (err) {
            console.error("Error accessing webcam:", err);
            if (videoPlaceholderText) videoPlaceholderText.textContent = "Could not access webcam. Check permissions.";
            if (startCameraButton) startCameraButton.classList.remove('hidden');
        }
    }

    function stopCamera() {
        stopFrameSending();
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
            console.log("Camera stream stopped.");
        }
        if (videoPlayer) {
            videoPlayer.srcObject = null;
            videoPlayer.style.display = 'none';
        }
        if (videoPlaceholderText) videoPlaceholderText.style.display = 'block';
        if (startCameraButton) startCameraButton.classList.remove('hidden');
        if (predictionResultDisplayElement) predictionResultDisplayElement.textContent = "Prediction: ...";
    }

    function startFrameSending() {
        if (frameSenderInterval) clearInterval(frameSenderInterval);
        if (!socket.connected) {
            console.warn("Socket not connected. Cannot send frames.");
            if (socketStatusElement) socketStatusElement.textContent = 'Socket: Not connected. Retrying...';
            // Optionally, try to reconnect or alert user
            return;
        }

        frameSenderInterval = setInterval(() => {
            if (videoPlayer.readyState >= videoPlayer.HAVE_CURRENT_DATA && canvasElement && socket.connected) {
                const context = canvasElement.getContext('2d');
                context.drawImage(videoPlayer, 0, 0, canvasElement.width, canvasElement.height);
                const dataURL = canvasElement.toDataURL('image/jpeg', 0.8); // Send JPEG at 80% quality
                socket.emit('process_frame', { image_data_url: dataURL });
            }
        }, 200); // Send frame every 200ms (5 FPS) - adjust as needed
    }

    function stopFrameSending() {
        if (frameSenderInterval) {
            clearInterval(frameSenderInterval);
            frameSenderInterval = null;
            console.log("Frame sending stopped.");
        }
    }

    function startPractice(sign) {
        console.log(`Starting practice for sign: ${sign}`);
        currentPracticeSign = sign;

        if(instructionText) instructionText.textContent = `Now, try to sign "${sign}"`;
        if(feedbackElement) {
            feedbackElement.textContent = 'Waiting for your sign...';
            feedbackElement.className = 'status-waiting';
        }
        successStartTime = null;

        const filename = sign.toUpperCase() + '.PNG'; // Ensure uppercase for filename consistency
        const imageUrl = `${staticBaseUrl}Images/${filename}`; // staticBaseUrl from HTML
        
        if(targetImage) {
            targetImage.src = imageUrl;
            targetImage.alt = `Sign language gesture for ${sign}`;
            targetImage.style.display = 'block';
        }
        if (imagePlaceholderText) imagePlaceholderText.style.display = 'none';

        if (signTips[sign] && tipSignLetter && tipText && signTipsArea) {
            tipSignLetter.textContent = sign;
            tipText.textContent = signTips[sign];
            signTipsArea.style.display = 'block';
        } else {
            if(signTipsArea) signTipsArea.style.display = 'none';
        }

        if (!localStream) { // If camera is not already started
             if(instructionText) instructionText.textContent = `Click 'Start Camera' first, then try signing "${sign}"`;
             if(feedbackElement) {
                feedbackElement.textContent = 'Camera not active';
                feedbackElement.className = 'status-waiting';
             }
        } else if (!frameSenderInterval && socket.connected) {
            // If camera is on but frames aren't sending (e.g., after a socket reconnect)
            startFrameSending();
        }
    }

    function updateFeedback(prediction) {
        if (!currentPracticeSign || !feedbackElement) return;

        const isCorrect = prediction && prediction.toLowerCase() === currentPracticeSign.toLowerCase();

        if (isCorrect) {
            if (!successStartTime) {
                successStartTime = Date.now();
                feedbackElement.textContent = `Correct! Hold for ${(SUCCESS_HOLD_TIME / 1000).toFixed(1)}s...`;
                feedbackElement.className = 'status-holding';
            } else {
                const timeHeld = Date.now() - successStartTime;
                if (timeHeld >= SUCCESS_HOLD_TIME) {
                    feedbackElement.textContent = `Great! You signed "${currentPracticeSign}"!`;
                    feedbackElement.className = 'status-success';
                    // Optionally stop practice or move to next sign here
                } else {
                     const timeLeft = Math.max(0, SUCCESS_HOLD_TIME - timeHeld);
                     feedbackElement.textContent = `Correct! Hold for ${(timeLeft / 1000).toFixed(1)}s...`;
                     feedbackElement.className = 'status-holding';
                }
            }
        } else {
            successStartTime = null; // Reset timer if prediction changes or is incorrect
            if (!prediction || prediction === "Ready..." || prediction === "..." || prediction === "No hand detected" || prediction === "Initializing...") {
                feedbackElement.textContent = "Place your hand clearly in the frame.";
                feedbackElement.className = 'status-waiting';
            } else if (prediction.includes("Error") || prediction === "Unknown" || prediction === "Low Confidence") {
                feedbackElement.textContent = `Status: ${prediction}. Try adjusting hand position.`;
                feedbackElement.className = 'status-incorrect';
            } else {
                feedbackElement.textContent = `Not quite "${currentPracticeSign}". You signed "${prediction}". Keep trying!`;
                feedbackElement.className = 'status-incorrect';
            }
        }
    }
});
