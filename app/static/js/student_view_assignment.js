document.addEventListener('DOMContentLoaded', function () {
    const predictionTextElement = document.getElementById('prediction_text');
    const submissionNotesTextarea = document.getElementById('submission-notes');
    const stabilityTimerTextElement = document.getElementById('stability_timer_text');
    const startCameraButton = document.getElementById('start_camera_assignment_btn'); // Updated ID
    const cameraPlaceholderDiv = document.getElementById('video_feed_placeholder_text'); // This is the <p> tag
    const videoFeedImg = document.getElementById('video_feed_assignment_img'); // Updated ID
    const videoFeedContainer = document.querySelector('.video-feed-container'); // Parent of img and placeholder text

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
            .then(response => response.text())
            .then(text => {
                if (text && text !== "No prediction" && text.trim() !== "") {
                    predictionTextElement.textContent = text;
                    if (text === lastPrediction) {
                        stableCounter++;
                        const lowerTextCompare = text.toLowerCase().trim();
                        // Only show "Holding..." if it's a valid sign being held
                        if (lowerTextCompare !== 'ready' && lowerTextCompare !== 'ready...' && lowerTextCompare !== 'no prediction' && stableCounter > 0 && stableCounter < STABILITY_THRESHOLD) {
                            stabilityTimerTextElement.textContent = `Holding: ${stableCounter}/${STABILITY_THRESHOLD}`;
                        } else {
                            // Clear timer text if it's a placeholder or threshold is met/not started
                            stabilityTimerTextElement.textContent = ""; 
                        }

                        if (stableCounter === STABILITY_THRESHOLD) {
                            const lowerText = text.toLowerCase().trim();
                            // Exclude "ready", "ready...", and "no prediction" from being appended
                            if (lowerText !== 'ready' && lowerText !== 'ready...' && lowerText !== 'no prediction') {
                                const currentNotes = submissionNotesTextarea.value;
                                const separator = currentNotes.length > 0 ? " " : "";
                                submissionNotesTextarea.value += separator + text;
                                
                                predictionTextElement.style.color = '#28a745';
                                setTimeout(() => {
                                    predictionTextElement.style.color = '#007bff';
                                }, 500);
                                stabilityTimerTextElement.textContent = "Added to notes!";
                                setTimeout(() => { stabilityTimerTextElement.textContent = ""; }, 3000); // Clear "Added" message after 3 seconds
                            } else {
                                stabilityTimerTextElement.textContent = ""; // Clear timer if it was "Ready"
                            }
                            stableCounter = 0; // Reset after action or if it was "Ready"
                        }
                    } else {
                        lastPrediction = text;
                        stableCounter = 0;
                        stabilityTimerTextElement.textContent = ""; // Clear timer text
                    }
                } else if (text === "No prediction" || text.trim() === "") {
                    predictionTextElement.textContent = "Waiting for prediction...";
                    lastPrediction = ""; 
                    stableCounter = 0;
                    stabilityTimerTextElement.textContent = ""; // Clear timer text
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
    
    // Initial check: if video_feed_img already has a src (e.g. if page was reloaded after starting)
    // This part might be tricky if the stream doesn't auto-restart well.
    // For now, we rely on the button click.

    // Ensure all elements are present before adding event listener or starting interval
    if (startCameraButton && document.getElementById('video_feed_assignment_img') && predictionTextElement && submissionNotesTextarea && stabilityTimerTextElement) {
        startCameraButton.addEventListener('click', startSignPractice);
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
