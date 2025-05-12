document.addEventListener('DOMContentLoaded', function () {
    const predictionTextElement = document.getElementById('prediction_text');
    const submissionNotesTextarea = document.getElementById('submission-notes');
    const stabilityTimerTextElement = document.getElementById('stability_timer_text');
    const startCameraButton = document.getElementById('start_camera_assignment_btn'); // Updated ID
    const cameraPlaceholderDiv = document.getElementById('video_feed_placeholder_text'); // This is the <p> tag
    const videoFeedImg = document.getElementById('video_feed_assignment_img'); // Updated ID
    const videoFeedContainer = document.querySelector('.video-feed-container'); // Parent of img and placeholder text

    let recordedSignAttempts = []; // Array to store {sign, confidence}
    let lastPrediction = "";
    let stableCounter = 0;
    const STABILITY_THRESHOLD = 30; // Approx 3 seconds if interval is 100ms (30 * 100ms = 3000ms)
    let predictionIntervalId = null;

    const getPredictionUrl = predictionTextElement ? predictionTextElement.dataset.getPredictionUrl : null;
    const videoFeedUrl = videoFeedImg ? videoFeedImg.dataset.videoFeedUrl : null;

    function fetchPrediction() {
        if (!getPredictionUrl) {
            // console.error("Get prediction URL is not set.");
            if(predictionTextElement) predictionTextElement.textContent = "Error: Config issue.";
            return;
        }

        fetch(getPredictionUrl)
            .then(response => response.json()) // Expect JSON now
            .then(data => {
                // data should be an object like {"sign": "A", "confidence": 0.95}
                const sign = data.sign;
                const confidence = data.confidence; // This is the confidence of the last processed frame

                if (sign && sign !== "No prediction" && sign.trim() !== "") {
                    // Display the sign from the server (which might include "Detect: ...")
                    // For user display, we might want to show just the sign.
                    // The `predictionTextElement` is used by the regex later, so it needs the full "Detect: X (Y%)"
                    // This means `get_prediction` should ideally return the raw display text too, or JS reconstructs it.
                    // For now, let's assume `sign_logic.py` still makes `predictionTextElement.textContent` show the detailed string.
                    // The `sign` variable from JSON is the clean sign.
                    
                    predictionTextElement.textContent = sign; // This will now be just the sign letter or "Ready..." etc.
                                                        // The detailed "Detect: X (Y%)" is on the video feed itself.

                    if (sign === lastPrediction) {
                        stableCounter++;
                        const lowerSignCompare = sign.toLowerCase().trim();
                        
                        if (lowerSignCompare !== 'ready' && lowerSignCompare !== 'ready...' && lowerSignCompare !== 'no prediction' && lowerSignCompare !== 'low confidence' && stableCounter > 0 && stableCounter < STABILITY_THRESHOLD) {
                            stabilityTimerTextElement.textContent = `Holding: ${stableCounter}/${STABILITY_THRESHOLD}`;
                        } else {
                            stabilityTimerTextElement.textContent = ""; 
                        }

                        if (stableCounter === STABILITY_THRESHOLD) {
                            const lowerSign = sign.toLowerCase().trim();
                            if (lowerSign !== 'ready' && lowerSign !== 'ready...' && lowerSign !== 'no prediction' && lowerSign !== 'low confidence') {
                                const currentNotes = submissionNotesTextarea.value;
                                const separator = currentNotes.length > 0 ? " " : "";
                                
                                // Use the sign and confidence directly from the JSON response
                                submissionNotesTextarea.value += separator + sign; 
                                recordedSignAttempts.push({ sign: sign, confidence: confidence });
                                console.log("Recorded attempt:", { sign: sign, confidence: confidence });
                                
                                predictionTextElement.style.color = '#28a745';
                                setTimeout(() => {
                                    predictionTextElement.style.color = '#007bff';
                                }, 500);
                                stabilityTimerTextElement.textContent = "Added to notes!";
                                setTimeout(() => { stabilityTimerTextElement.textContent = ""; }, 3000);
                            } else {
                                stabilityTimerTextElement.textContent = ""; 
                            }
                            stableCounter = 0; 
                        }
                    } else {
                        lastPrediction = sign; 
                        stableCounter = 0;
                        stabilityTimerTextElement.textContent = ""; 
                    }
                } else if (sign === "No prediction" || (sign && sign.trim() === "") || !sign) {
                    predictionTextElement.textContent = "Waiting for prediction...";
                    lastPrediction = ""; 
                    stableCounter = 0;
                    stabilityTimerTextElement.textContent = ""; 
                }
            })
            .catch(error => {
                console.error('Error fetching prediction:', error);
                if(predictionTextElement) predictionTextElement.textContent = "Error fetching prediction.";
                lastPrediction = "";
                stableCounter = 0;
                if(stabilityTimerTextElement) stabilityTimerTextElement.textContent = ""; // Clear timer text
            });
    }

    function startSignPractice() {
        if (!videoFeedUrl) {
            console.error("Video feed URL is not set.");
            if(cameraPlaceholderDiv) cameraPlaceholderDiv.textContent = "Error: Camera feed URL not configured.";
            return;
        }

        if (videoFeedImg && cameraPlaceholderDiv && videoFeedContainer) {
            videoFeedImg.src = videoFeedUrl;
            videoFeedImg.style.display = 'block'; 
            cameraPlaceholderDiv.style.display = 'none'; // Hide the placeholder text
            // The button is outside cameraPlaceholderDiv now, so no need to hide cameraPlaceholderDiv itself
        }

        if (predictionTextElement && submissionNotesTextarea && stabilityTimerTextElement && !predictionIntervalId) {
            predictionIntervalId = setInterval(fetchPrediction, 100); 
        }
        if (startCameraButton) {
            startCameraButton.disabled = true; // Disable button after starting
            startCameraButton.textContent = "Camera Active";
        }
    }

    if (startCameraButton) {
        startCameraButton.addEventListener('click', startSignPractice);
    }
    
    // Add hidden input to form for submitting recordedSignAttempts
    const form = document.querySelector('form[action*="/submit"]'); // Find the submission form
    if (form) {
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'sign_attempts_json';
        form.appendChild(hiddenInput);

        form.addEventListener('submit', function() {
            hiddenInput.value = JSON.stringify(recordedSignAttempts);
        });
    }


    // Ensure all elements are present before adding event listener or starting interval
    if (startCameraButton && videoFeedImg && predictionTextElement && submissionNotesTextarea && stabilityTimerTextElement) {
        // Event listener already added above
    } else {
        console.error("One or more critical elements for sign practice are missing from the DOM on StudentViewAssignment page.");
    }

    window.addEventListener('pagehide', function() {
        if (predictionIntervalId) {
            clearInterval(predictionIntervalId);
            predictionIntervalId = null;
            console.log("Cleared prediction interval on page hide (StudentViewAssignment).");
        }
        if (videoFeedImg && videoFeedImg.src !== "") {
            videoFeedImg.src = ""; // Attempt to stop the stream
            console.log("Cleared video feed source on page hide (StudentViewAssignment).");
        }
        // Optionally, could send a beacon/fetch to a server endpoint to explicitly release camera
        // For example: navigator.sendBeacon('/release_camera_signal');
        // But for now, relying on stream termination and server-side finally block.
    });

    if (submissionNotesTextarea) {
        submissionNotesTextarea.addEventListener('keydown', function(event) {
            // Allow backspace, delete, arrow keys, home, end, select all (Ctrl+A)
            if (event.key === 'Backspace' || 
                event.key === 'Delete' || 
                event.key.startsWith('Arrow') || // ArrowLeft, ArrowRight, ArrowUp, ArrowDown
                event.key === 'Home' || 
                event.key === 'End' ||
                (event.ctrlKey && event.key.toLowerCase() === 'a')) {
                return; // Allow default action
            }
            // Prevent typing other characters
            if (event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey) {
                event.preventDefault();
            }
        });
    }
});
