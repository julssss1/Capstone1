document.addEventListener('DOMContentLoaded', function() {
    const startCameraButton = document.getElementById('start-camera-btn');
    const videoElement = document.getElementById('camera-video');
    const canvasElement = document.getElementById('camera-canvas');
    const videoPlaceholderText = document.getElementById('video-placeholder-text');
    const feedbackElement = document.getElementById('feedback');
    const detectedSignDisplay = document.getElementById('detected-sign-display');
    const debugInfo = document.getElementById('debug-info');
    const instructionText = document.getElementById('instruction-text');
    const targetImage = document.getElementById('target-image');
    const imagePlaceholderText = document.getElementById('image-placeholder-text');
    const signButtonsContainer = document.getElementById('sign-buttons');
    const signTipsArea = document.getElementById('sign-tips-area');
    const tipSignLetter = document.getElementById('tip-sign-letter');
    const tipText = document.getElementById('tip-text');

    let recognitionClient = null;
    let currentPracticeSign = null;
    let lastStablePrediction = null;
    let successStartTime = null;
    const SUCCESS_HOLD_TIME = 1500; // ms
    let predictionCheckInterval = null;

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

    // Initialize the recognition client
    recognitionClient = new SignRecognitionClient();
    
    // Set up prediction update callback
    recognitionClient.onPredictionUpdate = (prediction) => {
        updateDetectedSign(prediction);
    };

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
        stopCamera();
    });

    async function startCameraOnClick() {
        console.log("Start Camera button clicked on Dashboard (Client-Side).");
        
        if (!videoElement || !canvasElement) {
            console.error("Video or canvas element not found!");
            if (videoPlaceholderText) videoPlaceholderText.textContent = "Camera configuration error.";
            return;
        }

        try {
            // Disable button and show loading state
            if (startCameraButton) {
                startCameraButton.disabled = true;
                startCameraButton.textContent = "Initializing...";
            }

            // Initialize the recognition system
            await recognitionClient.initialize();
            
            // Hide placeholder
            if (videoPlaceholderText) videoPlaceholderText.style.display = 'none';
            
            // Start camera
            await recognitionClient.startCamera('camera-video', 'camera-canvas');
            
            // Update UI
            if (startCameraButton) {
                startCameraButton.textContent = "Stop Camera";
                startCameraButton.disabled = false;
                startCameraButton.removeEventListener('click', startCameraOnClick);
                startCameraButton.addEventListener('click', stopCamera);
            }

            if (debugInfo) debugInfo.style.display = 'block';
            
            // Start checking predictions
            startPredictionChecking();
            
            console.log("Camera started successfully (Client-Side).");
        } catch (error) {
            console.error("Error starting camera:", error);
            handleCameraError(error);
        }
    }

    function stopCamera() {
        console.log("Stopping camera (Client-Side)...");
        
        if (recognitionClient) {
            recognitionClient.stop();
        }

        stopPredictionChecking();

        if (startCameraButton) {
            startCameraButton.textContent = "Start Camera";
            startCameraButton.disabled = false;
            startCameraButton.removeEventListener('click', stopCamera);
            startCameraButton.addEventListener('click', startCameraOnClick);
        }

        if (videoPlaceholderText) {
            videoPlaceholderText.textContent = "Click 'Start Camera' to begin.";
            videoPlaceholderText.style.display = 'block';
        }

        if (debugInfo) debugInfo.style.display = 'none';
    }

    function handleCameraError(error) {
        console.error("Camera error:", error);
        
        if (instructionText) instructionText.textContent = "Error starting camera.";
        if (feedbackElement) {
            feedbackElement.textContent = 'Camera Error';
            feedbackElement.className = 'status-incorrect';
        }
        if (videoPlaceholderText) {
            videoPlaceholderText.textContent = "Could not access camera. Please grant camera permissions.";
            videoPlaceholderText.style.display = 'block';
        }
        if (startCameraButton) {
            startCameraButton.textContent = "Start Camera";
            startCameraButton.disabled = false;
        }
    }

    function startPractice(sign) {
        console.log(`Starting practice for sign: ${sign}`);
        currentPracticeSign = sign;

        if (instructionText) instructionText.textContent = `Now, try to sign "${sign}"`;
        if (feedbackElement) {
            feedbackElement.textContent = 'Waiting for your sign...';
            feedbackElement.className = 'status-waiting';
        }
        lastStablePrediction = null;
        successStartTime = null;

        const filename = sign.toUpperCase() + '.png';
        const imageUrl = `${staticBaseUrl}Images/${filename}`;
        console.log(`Setting target image URL to: ${imageUrl}`);
        
        if (targetImage) {
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
            if (signTipsArea) signTipsArea.style.display = 'none';
        }

        if (!recognitionClient || !recognitionClient.isRunning) {
            if (instructionText) instructionText.textContent = `Click 'Start Camera' first, then try signing "${sign}"`;
            if (feedbackElement) {
                feedbackElement.textContent = 'Camera not active';
                feedbackElement.className = 'status-waiting';
            }
        }
    }

    function startPredictionChecking() {
        if (predictionCheckInterval) clearInterval(predictionCheckInterval);
        predictionCheckInterval = setInterval(checkPrediction, 100); // Check every 100ms
        console.log("Prediction checking started.");
    }

    function stopPredictionChecking() {
        if (predictionCheckInterval) {
            clearInterval(predictionCheckInterval);
            predictionCheckInterval = null;
            console.log("Prediction checking stopped.");
        }
    }

    function checkPrediction() {
        if (!currentPracticeSign || !recognitionClient) return;

        const prediction = recognitionClient.getStablePrediction();
        updateFeedback(prediction);
    }

    function updateDetectedSign(prediction) {
        if (detectedSignDisplay) {
            detectedSignDisplay.textContent = `Sign: ${prediction}`;
        }
    }

    function updateFeedback(prediction) {
        if (!currentPracticeSign || !feedbackElement) return;

        const isCorrect = prediction.toLowerCase() === currentPracticeSign.toLowerCase();

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
                } else {
                    const timeLeft = Math.max(0, SUCCESS_HOLD_TIME - timeHeld);
                    feedbackElement.textContent = `Correct! Hold for ${(timeLeft / 1000).toFixed(1)}s...`;
                    feedbackElement.className = 'status-holding';
                }
            }
        } else {
            successStartTime = null;
            if (prediction === "Ready..." || prediction === "..." || prediction === "No hand detected" || 
                prediction === "Initializing...") {
                feedbackElement.textContent = "Place your hand clearly in the frame.";
                feedbackElement.className = 'status-waiting';
            } else if (prediction.includes("Error") || prediction === "Unknown") {
                feedbackElement.textContent = `Status: ${prediction}. Try adjusting hand position.`;
                feedbackElement.className = 'status-incorrect';
            } else {
                feedbackElement.textContent = `Not quite "${currentPracticeSign}". You signed "${prediction}". Keep trying!`;
                feedbackElement.className = 'status-incorrect';
            }
        }
    }
});
