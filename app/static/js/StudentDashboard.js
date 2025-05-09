document.addEventListener('DOMContentLoaded', function() {
    const startCameraButton = document.getElementById('start-camera-btn');
    const videoFeedElement = document.getElementById('video-feed');
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

    let predictionInterval = null;
    let currentPracticeSign = null;
    let lastStablePrediction = null;
    let successStartTime = null;
    const SUCCESS_HOLD_TIME = 1500;

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

    if (startCameraButton) {
        startCameraButton.addEventListener('click', startCamera);
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
    window.addEventListener('beforeunload', stopPredictionPolling);

    async function startCamera() {
        console.log("Start Camera button clicked. Requesting permission...");
        if (!videoFeedElement) {
            console.error("Video feed element (#video-feed) not found!");
            return;
        }

        startCameraButton.classList.add('hidden');
        if (videoPlaceholderText) {
            videoPlaceholderText.textContent = "Requesting camera permission...";
            videoPlaceholderText.style.display = 'block';
        }
        videoFeedElement.style.display = 'none';

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });

            console.log("Camera permission granted.");

            stream.getTracks().forEach(track => track.stop());
            console.log("Local stream stopped, proceeding to load backend stream.");

            if (videoPlaceholderText) videoPlaceholderText.style.display = 'none';
            videoFeedElement.style.display = 'block';
            videoFeedElement.src = videoFeedUrl + "?t=" + new Date().getTime();
            console.log("Video feed source set to:", videoFeedElement.src);

            videoFeedElement.onerror = handleStreamError;
            videoFeedElement.onload = handleStreamLoad;

        } catch (error) {
            console.error("Error caught in startCamera function:", error);
            if (error instanceof TypeError) {
                console.error("TypeError Details:", error.message, error.stack);
            }

            videoFeedElement.style.display = 'none';
            startCameraButton.classList.remove('hidden');

            let errorMessage = "Could not access camera.";
            if (error instanceof DOMException) {
                if (error.name === "NotAllowedError") {
                    errorMessage = "Camera permission denied. Please allow access in browser settings (and ensure you are using HTTPS if not on localhost).";
                } else if (error.name === "NotFoundError") {
                    errorMessage = "No camera found. Please ensure a camera is connected and enabled.";
                } else if (error.name === "NotReadableError") {
                    errorMessage = "Camera is busy or hardware error occurred. Try closing other apps using the camera.";
                } else if (error.name === "AbortError") {
                    errorMessage = "Camera request aborted.";
                } else if (error.name === "SecurityError") {
                     errorMessage = "Camera access denied due to browser security settings (likely requires HTTPS).";
                } else {
                    errorMessage = `Camera Error: ${error.name}. Check browser console for details.`;
                }
            } else if (error instanceof TypeError) {
                errorMessage = `Error starting camera: TypeError - ${error.message || 'Unexpected issue'}. Check browser console.`;
            } else {
                 errorMessage = `Error starting camera: An unexpected error occurred. Check browser console.`;
            }

            instructionText.textContent = errorMessage;
            feedbackElement.textContent = 'Camera Access Failed';
            feedbackElement.className = 'status-incorrect';
            if (videoPlaceholderText) {
                videoPlaceholderText.textContent = errorMessage;
                videoPlaceholderText.style.display = 'block';
            }
            stopPredictionPolling();
        }
    }

    function handleStreamError() {
        console.error("Error loading video feed stream from backend. Check Flask server and endpoint URL:", videoFeedUrl);
        instructionText.textContent = "Error loading video stream from server.";
        feedbackElement.textContent = 'Stream Error';
        feedbackElement.className = 'status-incorrect';
        if (videoPlaceholderText) {
            videoPlaceholderText.textContent = "Could not load video stream. Check server logs.";
            videoPlaceholderText.style.display = 'block';
        }
        videoFeedElement.style.display = 'none';
        videoFeedElement.src = "";
        startCameraButton.classList.remove('hidden');
        stopPredictionPolling();
    }

    function handleStreamLoad() {
        console.log("Backend video feed stream connection established.");
        startPredictionPolling();
        if (debugInfo) debugInfo.style.display = 'block';
    }


    function startPractice(sign) {
        console.log(`Starting practice for sign: ${sign}`);
        currentPracticeSign = sign;

        instructionText.textContent = `Now, try to sign "${sign}"`;
        feedbackElement.textContent = 'Waiting for your sign...';
        feedbackElement.className = 'status-waiting';
        lastStablePrediction = null;
        successStartTime = null;

        let filename;
        const upperSign = sign.toUpperCase();

        if (upperSign === 'A') filename = 'A.png';
        else if (upperSign === 'B') filename = 'b.png';
        else if (upperSign === 'C') filename = 'c.png';
        else if (upperSign === 'D') filename = 'D.PNG';
        else if (upperSign === 'E') filename = 'E.png';
        else if (upperSign === 'F') filename = 'F.png';
        else filename = upperSign + '.png';

        const imageUrl = `${staticBaseUrl}Images/${filename}`;
        console.log(`Setting target image URL to: ${imageUrl}`);
        targetImage.src = imageUrl;
        targetImage.alt = `Sign language gesture for ${sign}`;
        targetImage.style.display = 'block';
        if (imagePlaceholderText) imagePlaceholderText.style.display = 'none';

        if (signTips[sign]) {
            tipSignLetter.textContent = sign;
            tipText.textContent = signTips[sign];
            signTipsArea.style.display = 'block';
        } else {
            console.warn(`No tips found for sign: ${sign}`);
            signTipsArea.style.display = 'none';
        }

        if (videoFeedElement.style.display === 'block' && !predictionInterval) {
            startPredictionPolling();
        } else if (videoFeedElement.style.display !== 'block') {
             instructionText.textContent = `Click 'Start Camera' first, then try signing "${sign}"`;
             feedbackElement.textContent = 'Camera not active';
             feedbackElement.className = 'status-waiting';
        }
    }

    function startPredictionPolling() {
        if (predictionInterval) { clearInterval(predictionInterval); }
        predictionInterval = setInterval(fetchPrediction, 500);
        console.log("Prediction polling started.");
    }

    function stopPredictionPolling() {
         if (predictionInterval) {
            clearInterval(predictionInterval);
            predictionInterval = null;
            console.log("Prediction polling stopped.");
        }
    }

    async function fetchPrediction() {
        if (!currentPracticeSign || videoFeedElement.style.display !== 'block') {
            return;
        }

        try {
            const response = await fetch(predictionUrl + "?t=" + new Date().getTime());
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const predictionText = await response.text();

            if (detectedSignDisplay) {
                 detectedSignDisplay.textContent = predictionText || "...";
            }

            const currentPrediction = predictionText || "...";

            const isCorrectPracticeSign = currentPracticeSign && currentPrediction.toLowerCase() === currentPracticeSign.toLowerCase();

            if (currentPrediction !== lastStablePrediction || isCorrectPracticeSign) {
                 updateFeedback(currentPrediction);
            }

            lastStablePrediction = currentPrediction;

        } catch (error) {
            console.error("Error fetching prediction:", error);
        }
    }

    function updateFeedback(prediction) {
        if (!currentPracticeSign) return;

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
                    console.log(`Sign "${currentPracticeSign}" successfully recognized and held.`);
                } else {
                     const timeLeft = Math.max(0, SUCCESS_HOLD_TIME - timeHeld);
                     feedbackElement.textContent = `Correct! Hold for ${(timeLeft / 1000).toFixed(1)}s...`;
                     feedbackElement.className = 'status-holding';
                }
            }
        } else {
            successStartTime = null;

            if (prediction === "Ready..." || prediction === "..." || prediction === "No hand detected") {
                feedbackElement.textContent = "Place your hand clearly in the frame.";
                feedbackElement.className = 'status-waiting';
            } else if (prediction === "Processing Error" || prediction === "System Error" || prediction === "Unknown" || prediction.startsWith("System Error")) {
                feedbackElement.textContent = `Status: ${prediction}. Try adjusting hand position or reloading.`;
                feedbackElement.className = 'status-incorrect';
            } else {
                feedbackElement.textContent = `Not quite "${currentPracticeSign}". You signed "${prediction}". Keep trying!`;
                feedbackElement.className = 'status-incorrect';
            }
        }
    }

});