/**
 * Client-Side Sign Recognition for Assignment Page
 * Converts hand signs to text input for assignment answers
 */

class SignRecognitionAssignment {
    constructor() {
        this.hands = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.canvasCtx = null;
        this.isRunning = false;
        
        // Prediction tracking
        this.currentPrediction = "Waiting...";
        this.lastPrediction = "";
        this.stableCounter = 0;
        this.STABILITY_THRESHOLD = 25;
        this.minConfidence = 0.90;
        
        // Cooldown after adding sign to prevent immediate re-detection
        this.lastSignAddedTime = 0;
        this.signCooldownMs = 1500; // 1.5 seconds cooldown after adding a sign
        this.isInCooldown = false;
        
        // Request throttling
        this.lastPredictionTime = 0;
        this.predictionThrottleMs = 600;
        this.pendingPrediction = false;
        
        // UI elements
        this.predictionTextElement = null;
        this.stabilityTimerElement = null;
        this.submissionNotesTextarea = null;
        this.startButton = null;
        this.placeholderText = null;
        
        // Recorded attempts for submission
        this.recordedSignAttempts = [];
    }

    /**
     * Initialize the system
     */
    async initialize() {
        try {
            console.log("Initializing Sign Recognition for Assignment...");
            
            // Get UI elements
            this.predictionTextElement = document.getElementById('prediction_text');
            this.stabilityTimerElement = document.getElementById('stability_timer_text');
            this.submissionNotesTextarea = document.getElementById('submission-notes');
            this.startButton = document.getElementById('start_camera_assignment_btn');
            this.placeholderText = document.getElementById('video_feed_placeholder_text');
            
            if (!this.predictionTextElement || !this.stabilityTimerElement || 
                !this.submissionNotesTextarea || !this.startButton) {
                throw new Error("Required UI elements not found");
            }
            
            // Initialize MediaPipe Hands
            await this.initializeMediaPipeHands();
            
            console.log("Initialization complete");
            return true;
        } catch (error) {
            console.error("Failed to initialize:", error);
            if (this.predictionTextElement) {
                this.predictionTextElement.textContent = "Initialization Failed";
            }
            throw error;
        }
    }

    /**
     * Initialize MediaPipe Hands
     */
    async initializeMediaPipeHands() {
        this.hands = new Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }
        });

        this.hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.6,
            minTrackingConfidence: 0.6
        });

        this.hands.onResults((results) => this.onHandsResults(results));
    }

    /**
     * Start camera
     */
    async startCamera() {
        try {
            this.videoElement = document.getElementById('camera-video-assignment');
            this.canvasElement = document.getElementById('camera-canvas-assignment');
            
            if (!this.videoElement || !this.canvasElement) {
                throw new Error("Video or canvas element not found");
            }

            this.canvasCtx = this.canvasElement.getContext('2d');

            // Request camera access
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                }
            });

            this.videoElement.srcObject = stream;
            this.videoElement.play();

            // Wait for video to be ready
            await new Promise((resolve) => {
                this.videoElement.onloadedmetadata = () => {
                    this.canvasElement.width = this.videoElement.videoWidth;
                    this.canvasElement.height = this.videoElement.videoHeight;
                    resolve();
                };
            });

            // Hide placeholder, show canvas
            if (this.placeholderText) {
                this.placeholderText.style.display = 'none';
            }
            this.canvasElement.style.display = 'block';

            // Update button
            if (this.startButton) {
                this.startButton.disabled = true;
                this.startButton.textContent = "Camera Active";
            }

            this.isRunning = true;
            this.processFrame();
            
            console.log("Camera started successfully");
            return true;
        } catch (error) {
            console.error("Error starting camera:", error);
            if (this.predictionTextElement) {
                this.predictionTextElement.textContent = "Camera Error";
            }
            throw error;
        }
    }

    /**
     * Process video frames
     */
    async processFrame() {
        if (!this.isRunning) return;

        try {
            await this.hands.send({ image: this.videoElement });
        } catch (error) {
            console.error("Error processing frame:", error);
        }

        requestAnimationFrame(() => this.processFrame());
    }

    /**
     * Handle MediaPipe Hands results
     */
    async onHandsResults(results) {
        // Clear canvas
        this.canvasCtx.save();
        this.canvasCtx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        
        // Draw video frame
        this.canvasCtx.drawImage(results.image, 0, 0, this.canvasElement.width, this.canvasElement.height);

        let sign = "No hand detected";
        let confidence = 0.0;

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            const landmarks = results.multiHandLandmarks[0];
            
            // Draw landmarks
            drawConnectors(this.canvasCtx, landmarks, HAND_CONNECTIONS, { color: '#00FF00', lineWidth: 2 });
            drawLandmarks(this.canvasCtx, landmarks, { color: '#FF0000', lineWidth: 1, radius: 3 });

            // Normalize landmarks
            const normalizedLandmarks = this.normalizeLandmarks(landmarks);
            
            if (normalizedLandmarks) {
                // Make prediction
                const prediction = await this.predict(normalizedLandmarks);
                sign = prediction.sign;
                confidence = prediction.confidence;
            }
        }

        // Update stability tracking
        this.updateStability(sign, confidence);

        // Draw prediction text on canvas
        this.drawPredictionText(sign, confidence);

        this.canvasCtx.restore();
    }

    /**
     * Normalize hand landmarks
     */
    normalizeLandmarks(landmarks) {
        try {
            const wrist = landmarks[0];
            const originX = wrist.x;
            const originY = wrist.y;

            const middleMCP = landmarks[9];
            const scale = Math.sqrt(
                Math.pow(middleMCP.x - originX, 2) + 
                Math.pow(middleMCP.y - originY, 2)
            );

            if (scale < 1e-6) return null;

            const normalized = [];
            for (const landmark of landmarks) {
                const normX = (landmark.x - originX) / scale;
                const normY = (landmark.y - originY) / scale;
                normalized.push(normX, normY);
            }

            return normalized;
        } catch (error) {
            console.error("Error normalizing landmarks:", error);
            return null;
        }
    }

    /**
     * Make prediction using server API with throttling
     */
    async predict(landmarkData) {
        const currentTime = Date.now();
        
        // Throttle requests
        if (currentTime - this.lastPredictionTime < this.predictionThrottleMs) {
            return {
                sign: this.currentPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        if (this.pendingPrediction) {
            return {
                sign: this.currentPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        this.pendingPrediction = true;
        this.lastPredictionTime = currentTime;
        
        try {
            const response = await fetch('/student/api/predict_landmarks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    landmarks: landmarkData
                })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();
            
            this.lastConfidence = result.confidence;
            
            if (result.confidence >= this.minConfidence) {
                return {
                    sign: result.sign,
                    confidence: result.confidence
                };
            } else {
                return {
                    sign: "Low Confidence",
                    confidence: result.confidence
                };
            }
        } catch (error) {
            console.error("Error making prediction:", error);
            return {
                sign: "Prediction Error",
                confidence: 0.0
            };
        } finally {
            this.pendingPrediction = false;
        }
    }

    /**
     * Update stability tracking and add to textarea when stable
     */
    updateStability(sign, confidence) {
        const currentTime = Date.now();
        
        // Check if we're in cooldown period
        if (this.isInCooldown) {
            const cooldownRemaining = this.signCooldownMs - (currentTime - this.lastSignAddedTime);
            if (cooldownRemaining > 0) {
                // Still in cooldown
                if (this.stabilityTimerElement) {
                    this.stabilityTimerElement.textContent = `Wait ${Math.ceil(cooldownRemaining / 1000)}s...`;
                }
                if (this.predictionTextElement) {
                    this.predictionTextElement.textContent = "Cooldown...";
                }
                // Reset counter during cooldown
                this.stableCounter = 0;
                this.lastPrediction = "";
                return;
            } else {
                // Cooldown ended
                this.isInCooldown = false;
                this.stableCounter = 0;
                this.lastPrediction = "";
                if (this.stabilityTimerElement) {
                    this.stabilityTimerElement.textContent = "";
                }
            }
        }
        
        this.currentPrediction = sign;
        
        // Update prediction display
        if (this.predictionTextElement) {
            this.predictionTextElement.textContent = sign;
        }

        // Check if it's a valid sign
        const invalidStates = ["No hand detected", "Low Confidence", "Prediction Error", 
                               "Processing...", "Waiting...", "Ready", "Ready...", "Cooldown..."];
        const lowerSign = sign.toLowerCase().trim();
        const isValidSign = !invalidStates.some(state => lowerSign === state.toLowerCase());

        // Don't count invalid states
        if (!isValidSign) {
            this.lastPrediction = sign;
            this.stableCounter = 0;
            if (this.stabilityTimerElement) {
                this.stabilityTimerElement.textContent = "";
            }
            return;
        }

        if (sign === this.lastPrediction) {
            this.stableCounter++;
            
            // Show stability progress
            if (this.stableCounter > 0 && this.stableCounter < this.STABILITY_THRESHOLD) {
                if (this.stabilityTimerElement) {
                    this.stabilityTimerElement.textContent = `Holding: ${this.stableCounter}/${this.STABILITY_THRESHOLD}`;
                }
            }

            // Add to textarea when stable
            if (this.stableCounter === this.STABILITY_THRESHOLD) {
                this.addSignToTextarea(sign, confidence);
                // Reset and enter cooldown
                this.stableCounter = 0;
                this.lastPrediction = "";
                this.isInCooldown = true;
                this.lastSignAddedTime = currentTime;
            }
        } else {
            this.lastPrediction = sign;
            this.stableCounter = 0;
            if (this.stabilityTimerElement && !this.isInCooldown) {
                this.stabilityTimerElement.textContent = "";
            }
        }
    }

    /**
     * Add recognized sign to textarea
     */
    addSignToTextarea(sign, confidence) {
        if (!this.submissionNotesTextarea) return;

        const currentText = this.submissionNotesTextarea.value;
        const separator = currentText.length > 0 ? " " : "";
        
        // Add sign to textarea
        this.submissionNotesTextarea.value += separator + sign;
        
        // Record attempt
        this.recordedSignAttempts.push({ sign: sign, confidence: confidence });
        console.log("Recorded attempt:", { sign, confidence });
        
        // Visual feedback
        if (this.predictionTextElement) {
            this.predictionTextElement.style.color = '#28a745';
            setTimeout(() => {
                this.predictionTextElement.style.color = '#007bff';
            }, 500);
        }
        
        if (this.stabilityTimerElement) {
            this.stabilityTimerElement.textContent = "Added to notes!";
            setTimeout(() => {
                this.stabilityTimerElement.textContent = "";
            }, 2000);
        }
    }

    /**
     * Draw prediction text on canvas
     */
    drawPredictionText(sign, confidence) {
        
        // Draw "Detect:" text
        const detectText = `Detect: ${sign} ${confidence > 0 ? `(${(confidence * 100).toFixed(1)}%)` : ''}`;
        this.canvasCtx.font = 'bold 26px Arial';
        this.canvasCtx.strokeStyle = 'black';
        this.canvasCtx.lineWidth = 3;
        this.canvasCtx.strokeText(detectText, 15, 35);
        this.canvasCtx.fillStyle = '#FF7800';
        this.canvasCtx.fillText(detectText, 15, 35);

        // Draw stability counter
        const stableText = `Stable: ${this.stableCounter}/${this.STABILITY_THRESHOLD}`;
        this.canvasCtx.font = 'bold 32px Arial';
        this.canvasCtx.strokeStyle = 'black';
        this.canvasCtx.lineWidth = 4;
        this.canvasCtx.strokeText(stableText, 15, 75);
        this.canvasCtx.fillStyle = '#00FF00';
        this.canvasCtx.fillText(stableText, 15, 75);
    }

    /**
     * Stop camera
     */
    stop() {
        this.isRunning = false;
        
        if (this.videoElement && this.videoElement.srcObject) {
            const tracks = this.videoElement.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            this.videoElement.srcObject = null;
        }

        console.log("Camera stopped");
    }

    /**
     * Get recorded sign attempts for form submission
     */
    getRecordedAttempts() {
        return this.recordedSignAttempts;
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async function () {
    const signRecognition = new SignRecognitionAssignment();
    
    try {
        await signRecognition.initialize();
        
        // Start button handler
        const startButton = document.getElementById('start_camera_assignment_btn');
        if (startButton) {
            startButton.addEventListener('click', async () => {
                try {
                    await signRecognition.startCamera();
                } catch (error) {
                    console.error("Failed to start camera:", error);
                    alert("Failed to start camera. Please check permissions.");
                }
            });
        }
        
        // Add hidden input to form for recorded attempts
        const form = document.querySelector('form[action*="/submit"]');
        if (form) {
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'sign_attempts_json';
            form.appendChild(hiddenInput);

            form.addEventListener('submit', function() {
                hiddenInput.value = JSON.stringify(signRecognition.getRecordedAttempts());
            });
        }
        
        // Prevent manual typing (allow only backspace, delete, arrows)
        const textarea = document.getElementById('submission-notes');
        if (textarea) {
            textarea.addEventListener('keydown', function(event) {
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
        
        // Cleanup on page unload
        window.addEventListener('pagehide', function() {
            signRecognition.stop();
        });
        
    } catch (error) {
        console.error("Initialization failed:", error);
    }
});
