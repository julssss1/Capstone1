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
    const SUCCESS_HOLD_TIME = 1500; // ms

    // These are expected to be set by inline script in the HTML template
    // const predictionUrl = "{{ url_for('student.get_prediction') }}";
    // const videoFeedUrl = "{{ url_for('student.video_feed') }}";
    // const staticBaseUrl = "{{ url_for('static', filename='') }}"; 

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
        stopPredictionPolling(); 
        if (videoFeedElement && videoFeedElement.src !== "") {
            videoFeedElement.src = ""; 
            console.log("Cleared video feed source on page hide (StudentDashboard).");
            if (videoPlaceholderText) videoPlaceholderText.style.display = 'block';
            if (startCameraButton) startCameraButton.classList.remove('hidden'); // Show start button again
            videoFeedElement.style.display = 'none';
        }
    });

    function startCameraOnClick() {
        console.log("Start Camera button clicked on Dashboard.");
        if (!videoFeedElement || !videoFeedUrl) {
            console.error("Video feed element or URL not found/configured!");
            if (videoPlaceholderText) videoPlaceholderText.textContent = "Camera configuration error.";
            return;
        }

        if (startCameraButton) startCameraButton.classList.add('hidden');
        if (videoPlaceholderText) videoPlaceholderText.style.display = 'none'; // Hide placeholder
        
        videoFeedElement.style.display = 'block';
        videoFeedElement.src = videoFeedUrl + "?t=" + new Date().getTime(); // Start the stream
        console.log("Video feed source set to:", videoFeedElement.src);

        videoFeedElement.onerror = handleStreamError;
        videoFeedElement.onload = handleStreamLoad;
    }

    function handleStreamError() {
        console.error("Error loading video feed stream from backend. Check Flask server and endpoint URL:", videoFeedUrl);
        if(instructionText) instructionText.textContent = "Error loading video stream from server.";
        if(feedbackElement) {
            feedbackElement.textContent = 'Stream Error';
            feedbackElement.className = 'status-incorrect';
        }
        if (videoPlaceholderText) {
            videoPlaceholderText.textContent = "Could not load video stream. Check server logs.";
            videoPlaceholderText.style.display = 'block';
        }
        if(videoFeedElement) {
            videoFeedElement.style.display = 'none';
            videoFeedElement.src = ""; // Clear src on error
        }
        if(startCameraButton) startCameraButton.classList.remove('hidden'); // Show start button again
        stopPredictionPolling();
    }

    function handleStreamLoad() {
        console.log("Backend video feed stream connection established on Dashboard.");
        startPredictionPolling();
        if (debugInfo) debugInfo.style.display = 'block';
    }

    function startPractice(sign) {
        console.log(`Starting practice for sign: ${sign}`);
        currentPracticeSign = sign;

        if(instructionText) instructionText.textContent = `Now, try to sign "${sign}"`;
        if(feedbackElement) {
            feedbackElement.textContent = 'Waiting for your sign...';
            feedbackElement.className = 'status-waiting';
        }
        lastStablePrediction = null;
        successStartTime = null;

        // Using lowercase .png for consistency and to avoid case-sensitivity issues.
        // The 'sign' variable comes from button text, assume it's already the correct case (e.g., "A", "B")
        const filename = sign.toUpperCase() + '.png'; // Ensure sign is uppercase, extension is lowercase

        const imageUrl = `${staticBaseUrl}Images/${filename}`;
        console.log(`Setting target image URL to: ${imageUrl}`);
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

        if (videoFeedElement && videoFeedElement.style.display === 'block' && !predictionInterval) {
            startPredictionPolling();
        } else if (videoFeedElement && videoFeedElement.style.display !== 'block') {
             if(instructionText) instructionText.textContent = `Click 'Start Camera' first, then try signing "${sign}"`;
             if(feedbackElement) {
                feedbackElement.textContent = 'Camera not active';
                feedbackElement.className = 'status-waiting';
             }
        }
    }

    function startPredictionPolling() {
        if (predictionInterval) { clearInterval(predictionInterval); }
        // Ensure predictionUrl is defined (should be from inline script in HTML)
        if (typeof predictionUrl !== 'undefined') {
            predictionInterval = setInterval(fetchPrediction, 500); // Poll every 500ms
            console.log("Prediction polling started.");
        } else {
            console.error("predictionUrl is not defined. Cannot start polling.");
        }
    }

    function stopPredictionPolling() {
         if (predictionInterval) {
            clearInterval(predictionInterval);
            predictionInterval = null;
            console.log("Prediction polling stopped.");
        }
    }

    async function fetchPrediction() {
    if (!currentPracticeSign || !videoFeedElement || videoFeedElement.style.display !== 'block') {
        return;
    }

    try {
        if (typeof predictionUrl === 'undefined') {
            console.error("predictionUrl is not defined in fetchPrediction.");
            return;
        }
        const response = await fetch(predictionUrl + "?t=" + new Date().getTime());
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        // const predictionText = await response.text(); // OLD WAY

        const predictionData = await response.json(); // NEW: Parse as JSON
        const predictedSign = predictionData.sign;    // NEW: Extract the sign
       

        if (detectedSignDisplay) {
            // detectedSignDisplay.textContent = predictionText || "..."; // OLD WAY
            detectedSignDisplay.textContent = `Sign: ${predictedSign}`; // NEW: Display sign and confidence
        }
        // updateFeedback(predictionText || "..."); // OLD WAY
        updateFeedback(predictedSign || "...");   // NEW: Pass only the sign string to updateFeedback
    } catch (error) {
        console.error("Error fetching prediction:", error);
        if (feedbackElement) {
            feedbackElement.textContent = "Error getting prediction. Check console.";
            feedbackElement.className = 'status-incorrect';
        }
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
            if (prediction === "Ready..." || prediction === "..." || prediction === "No hand detected") {
                feedbackElement.textContent = "Place your hand clearly in the frame.";
                feedbackElement.className = 'status-waiting';
            } else if (prediction === "Processing Error" || prediction === "System Error" || prediction === "Unknown" || prediction.startsWith("System Error")) {
                feedbackElement.textContent = `Status: ${prediction}. Try adjusting hand position.`;
                feedbackElement.className = 'status-incorrect';
            } else {
                feedbackElement.textContent = `Not quite "${currentPracticeSign}". You signed "${prediction}". Keep trying!`;
                feedbackElement.className = 'status-incorrect';
            }
        }
    }
});
