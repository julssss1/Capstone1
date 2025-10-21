/**
 * Basic Phrase Client-Side Sign Language Recognition (Single-Hand Model)
 * Uses MediaPipe Hands for single-hand tracking and TensorFlow.js for sign classification
 */

class SignRecognitionBasicPhraseClient {
    constructor() {
        this.model = null;
        this.hands = null;
        this.classNames = [];
        this.videoElement = null;
        this.canvasElement = null;
        this.canvasCtx = null;
        this.isRunning = false;
        this.predictionBuffer = [];
        this.bufferSize = 10;
        this.smoothingThreshold = 0.9;
        this.minConfidence = 0.90;
        this.stableDisplay = "Initializing...";
        this.lastValidTimestamp = null;
        this.stableHoldDuration = 1500; // ms
        this.onPredictionUpdate = null; // Callback for prediction updates
        
        // Request throttling
        this.lastPredictionTime = 0;
        this.predictionThrottleMs = 600;
        this.pendingPrediction = false;
    }

    /**
     * Initialize the Basic Phrase recognition system
     */
    async initialize() {
        try {
            console.log("Initializing Basic Phrase Sign Recognition Client (Single-Hand)...");
            
            // Load class names
            await this.loadClassNames();
            
            // Load TensorFlow.js TFLite model (using server-side API)
            await this.loadModel();
            
            // Initialize MediaPipe Hands for one hand
            await this.initializeMediaPipeHands();
            
            console.log("Basic Phrase Sign Recognition Client initialized successfully");
            this.stableDisplay = "Ready...";
            return true;
        } catch (error) {
            console.error("Failed to initialize Basic Phrase recognition:", error);
            this.stableDisplay = "Initialization Failed";
            throw error;
        }
    }

    /**
     * Load class names
     */
    async loadClassNames() {
        // Class names will be determined by the model
        this.classNames = [];
        console.log("Using server-side Basic Phrase API for class names");
    }

    /**
     * Load the TFLite model (using server-side API)
     */
    async loadModel() {
        console.log("Basic Phrase Model loading skipped - using server-side API");
        this.model = "server-side-basic-phrase";
        return true;
    }

    /**
     * Initialize MediaPipe Hands for ONE hand
     */
    async initializeMediaPipeHands() {
        console.log("Initializing MediaPipe Hands for single-hand detection...");
        
        this.hands = new Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }
        });

        this.hands.setOptions({
            maxNumHands: 1, // Detect ONE hand only
            modelComplexity: 1,
            minDetectionConfidence: 0.6,
            minTrackingConfidence: 0.6
        });

        this.hands.onResults((results) => this.onHandsResults(results));
        
        console.log("MediaPipe Hands initialized for single-hand mode");
    }

    /**
     * Start camera and recognition
     */
    async startCamera(videoElementId, canvasElementId) {
        try {
            this.videoElement = document.getElementById(videoElementId);
            this.canvasElement = document.getElementById(canvasElementId);
            
            if (!this.videoElement || !this.canvasElement) {
                throw new Error("Video or canvas element not found");
            }

            this.canvasCtx = this.canvasElement.getContext('2d');
            this.canvasElement.style.display = 'block';

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                }
            });

            this.videoElement.srcObject = stream;
            this.videoElement.play();

            await new Promise((resolve) => {
                this.videoElement.onloadedmetadata = () => {
                    this.canvasElement.width = this.videoElement.videoWidth;
                    this.canvasElement.height = this.videoElement.videoHeight;
                    resolve();
                };
            });

            this.isRunning = true;
            this.processFrame();
            
            console.log("Basic Phrase Camera started successfully");
            return true;
        } catch (error) {
            console.error("Error starting Basic Phrase camera:", error);
            this.stableDisplay = "Camera Error";
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
     * Handle MediaPipe Hands results (ONE HAND)
     */
    async onHandsResults(results) {
        // Clear canvas
        this.canvasCtx.save();
        this.canvasCtx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        
        // Draw video frame
        this.canvasCtx.drawImage(results.image, 0, 0, this.canvasElement.width, this.canvasElement.height);

        let instantaneousPrediction = "No hand detected";
        let confidence = 0.0;

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            // Draw detected hand
            const landmarks = results.multiHandLandmarks[0];
            
            // Draw landmarks
            drawConnectors(this.canvasCtx, landmarks, HAND_CONNECTIONS, { color: '#00FF00', lineWidth: 2 });
            drawLandmarks(this.canvasCtx, landmarks, { color: '#FF0000', lineWidth: 1, radius: 3 });
            
            // Normalize landmarks for single hand
            const normalizedLandmarks = this.normalizeSingleHand(landmarks);
            
            if (normalizedLandmarks) {
                // Make prediction
                const prediction = await this.predictBasicPhrase(normalizedLandmarks);
                instantaneousPrediction = prediction.sign;
                confidence = prediction.confidence;
            }
        }

        // Update prediction buffer
        this.predictionBuffer.push(instantaneousPrediction);
        if (this.predictionBuffer.length > this.bufferSize) {
            this.predictionBuffer.shift();
        }

        // Calculate stable prediction
        this.updateStablePrediction();

        // Draw prediction text on canvas
        this.drawPredictionText(instantaneousPrediction, confidence);

        this.canvasCtx.restore();
    }

    /**
     * Extract raw landmarks (matching test_realtime.py approach)
     * Returns array of 63 values: x, y, z for each of 21 landmarks
     */
    normalizeSingleHand(landmarks) {
        try {
            // Extract raw x, y, z coordinates (no normalization)
            const raw_landmarks = [];
            for (const landmark of landmarks) {
                raw_landmarks.push(landmark.x, landmark.y, landmark.z);
            }
            return raw_landmarks; // Returns 63 values (21 landmarks * 3 coordinates)
        } catch (error) {
            console.error("Error extracting landmarks:", error);
            return null;
        }
    }

    /**
     * Make Basic Phrase prediction using server-side API with throttling
     */
    async predictBasicPhrase(landmarkData) {
        const currentTime = Date.now();
        
        // Throttle
        if (currentTime - this.lastPredictionTime < this.predictionThrottleMs) {
            return {
                sign: this.lastPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        if (this.pendingPrediction) {
            return {
                sign: this.lastPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        this.pendingPrediction = true;
        this.lastPredictionTime = currentTime;
        
        try {
            // Send landmarks to Basic Phrase server endpoint
            const response = await fetch('/student/api/predict_landmarks_basic_phrase', {
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
            
            this.lastPrediction = result.sign;
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
            console.error("Error making Basic Phrase prediction:", error);
            return {
                sign: "Prediction Error",
                confidence: 0.0
            };
        } finally {
            this.pendingPrediction = false;
        }
    }

    /**
     * Update stable prediction based on buffer
     */
    updateStablePrediction() {
        if (this.predictionBuffer.length < this.bufferSize) return;

        const invalidStates = ["Unknown", "No hand detected", "Processing Error", 
                               "Landmark count error", "Detect Error", "...", 
                               "Low Confidence", "Prediction Error"];

        const counts = {};
        for (const pred of this.predictionBuffer) {
            counts[pred] = (counts[pred] || 0) + 1;
        }

        let mostCommon = null;
        let maxCount = 0;
        for (const [pred, count] of Object.entries(counts)) {
            if (count > maxCount) {
                maxCount = count;
                mostCommon = pred;
            }
        }

        const requiredCount = Math.floor(this.bufferSize * this.smoothingThreshold);
        const isStable = maxCount >= requiredCount;
        const currentTime = Date.now();

        if (isStable) {
            if (!invalidStates.includes(mostCommon)) {
                if (this.stableDisplay !== mostCommon) {
                    this.stableDisplay = mostCommon;
                    this.notifyPredictionUpdate();
                }
                this.lastValidTimestamp = currentTime;
            } else {
                if (!invalidStates.includes(this.stableDisplay) && this.stableDisplay !== "Ready...") {
                    this.stableDisplay = "Ready...";
                    this.notifyPredictionUpdate();
                }
                this.lastValidTimestamp = null;
            }
        } else {
            if (this.lastValidTimestamp && (currentTime - this.lastValidTimestamp >= this.stableHoldDuration)) {
                if (this.stableDisplay !== "Ready...") {
                    this.stableDisplay = "Ready...";
                    this.notifyPredictionUpdate();
                }
                this.lastValidTimestamp = null;
            }
        }
    }

    /**
     * Draw prediction text on canvas
     */
    drawPredictionText(instantPrediction, confidence) {
        const detectText = `Detect: ${instantPrediction} ${confidence > 0 ? `(${(confidence * 100).toFixed(1)}%)` : ''}`;
        this.canvasCtx.font = 'bold 26px Arial';
        this.canvasCtx.strokeStyle = 'black';
        this.canvasCtx.lineWidth = 3;
        this.canvasCtx.strokeText(detectText, 15, 35);
        this.canvasCtx.fillStyle = '#FF7800';
        this.canvasCtx.fillText(detectText, 15, 35);

        const invalidStates = ["Unknown", "No hand detected", "Ready...", "Initializing..."];
        let stableColor = '#00FF00';
        if (invalidStates.includes(this.stableDisplay)) {
            stableColor = '#C8C8C8';
        }
        if (this.stableDisplay.includes("Error")) {
            stableColor = '#FF0000';
        }

        const stableText = `Stable: ${this.stableDisplay}`;
        this.canvasCtx.font = 'bold 32px Arial';
        this.canvasCtx.strokeStyle = 'black';
        this.canvasCtx.lineWidth = 4;
        this.canvasCtx.strokeText(stableText, 15, 75);
        this.canvasCtx.fillStyle = stableColor;
        this.canvasCtx.fillText(stableText, 15, 75);
    }

    /**
     * Notify listeners of prediction update
     */
    notifyPredictionUpdate() {
        if (this.onPredictionUpdate) {
            this.onPredictionUpdate(this.stableDisplay);
        }
    }

    /**
     * Get current stable prediction
     */
    getStablePrediction() {
        return this.stableDisplay;
    }

    /**
     * Stop camera and recognition
     */
    stop() {
        this.isRunning = false;
        
        if (this.videoElement && this.videoElement.srcObject) {
            const tracks = this.videoElement.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            this.videoElement.srcObject = null;
        }

        if (this.canvasCtx && this.canvasElement) {
            this.canvasCtx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
            this.canvasCtx.fillStyle = 'black';
            this.canvasCtx.fillRect(0, 0, this.canvasElement.width, this.canvasElement.height);
            this.canvasElement.style.display = 'none';
        }

        this.stableDisplay = "Offline";
        console.log("Basic Phrase Camera stopped");
    }
}

// Initialize Basic Phrase recognition when page loads
let recognitionClient = null;
let currentTargetSign = null;
let cameraStarted = false;
let successStartTime = null;
const SUCCESS_HOLD_TIME = 1500; // ms - require user to hold sign for 1.5 seconds
let predictionCheckInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    console.log("Basic Phrase Practice page loaded");
    
    // Initialize recognition client
    recognitionClient = new SignRecognitionBasicPhraseClient();
    
    try {
        await recognitionClient.initialize();
        console.log("Basic Phrase Recognition initialized");
    } catch (error) {
        console.error("Failed to initialize Basic Phrase recognition:", error);
    }
    
    // Set up prediction update callback
    recognitionClient.onPredictionUpdate = (stablePrediction) => {
        // This can be left for compatibility but we'll use polling
    };
    
    // Set up sign button handlers
    setupSignButtons();
    
    // Set up camera button
    setupCameraButton();
});

function setupSignButtons() {
    const signButtons = document.querySelectorAll('.sign-btn');
    signButtons.forEach(button => {
        button.addEventListener('click', () => {
            currentTargetSign = button.textContent.trim();
            selectSign(currentTargetSign);
        });
    });
}

function selectSign(sign) {
    currentTargetSign = sign;
    successStartTime = null;
    
    document.getElementById('instruction-text').textContent = `Practice the phrase: ${sign}`;
    document.getElementById('tip-sign-letter').textContent = sign;
    document.getElementById('tip-text').textContent = `Show the "${sign}" sign clearly to the camera with one hand.`;
    document.getElementById('sign-tips-area').style.display = 'block';
    
    const targetImage = document.getElementById('target-image');
    const imagePlaceholder = document.getElementById('image-placeholder-text');
    
    // Try to load image (if available)
    const imgPath = `${staticBaseUrl}Images/${sign}.png`;
    targetImage.src = imgPath;
    targetImage.style.display = 'block';
    imagePlaceholder.style.display = 'none';
    
    targetImage.onerror = () => {
        targetImage.style.display = 'none';
        imagePlaceholder.style.display = 'block';
        imagePlaceholder.textContent = `No image available for "${sign}"`;
    };
    
    document.getElementById('feedback').className = 'status-waiting';
    document.getElementById('feedback').textContent = 'Show your hand to start...';
    
    // Start checking predictions if camera is running
    if (cameraStarted && !predictionCheckInterval) {
        startPredictionChecking();
    }
}

function setupCameraButton() {
    const startBtn = document.getElementById('start-camera-btn');
    startBtn.addEventListener('click', async () => {
        if (!cameraStarted) {
            try {
                startBtn.disabled = true;
                startBtn.textContent = 'Starting...';
                
                await recognitionClient.startCamera('camera-video', 'camera-canvas');
                
                cameraStarted = true;
                startBtn.textContent = 'Stop Camera';
                startBtn.disabled = false;
                
                document.getElementById('video-placeholder-text').style.display = 'none';
                
                // Start checking predictions if a sign is selected
                if (currentTargetSign) {
                    startPredictionChecking();
                }
            } catch (error) {
                console.error("Error starting camera:", error);
                alert("Failed to start camera. Please check permissions.");
                startBtn.textContent = 'Start Camera';
                startBtn.disabled = false;
            }
        } else {
            recognitionClient.stop();
            stopPredictionChecking();
            cameraStarted = false;
            startBtn.textContent = 'Start Camera';
            document.getElementById('video-placeholder-text').style.display = 'block';
        }
    });
}

function startPredictionChecking() {
    if (predictionCheckInterval) clearInterval(predictionCheckInterval);
    predictionCheckInterval = setInterval(checkPrediction, 100); // Check every 100ms
    console.log("Basic Phrase prediction checking started.");
}

function stopPredictionChecking() {
    if (predictionCheckInterval) {
        clearInterval(predictionCheckInterval);
        predictionCheckInterval = null;
        console.log("Basic Phrase prediction checking stopped.");
    }
}

function checkPrediction() {
    if (!currentTargetSign || !recognitionClient) return;
    
    const prediction = recognitionClient.getStablePrediction();
    updateFeedback(prediction);
}

function updateFeedback(stablePrediction) {
    const feedbackEl = document.getElementById('feedback');
    const detectedSignDisplay = document.getElementById('detected-sign-display');
    
    if (detectedSignDisplay) {
        detectedSignDisplay.textContent = stablePrediction;
    }
    
    if (!currentTargetSign) {
        feedbackEl.className = 'status-waiting';
        feedbackEl.textContent = 'Select a phrase to practice';
        return;
    }
    
    const isCorrect = stablePrediction === currentTargetSign;
    
    if (isCorrect) {
        if (!successStartTime) {
            // Start the hold timer
            successStartTime = Date.now();
            feedbackEl.textContent = `Correct! Hold for ${(SUCCESS_HOLD_TIME / 1000).toFixed(1)}s...`;
            feedbackEl.className = 'status-holding';
        } else {
            // Check how long the sign has been held
            const timeHeld = Date.now() - successStartTime;
            if (timeHeld >= SUCCESS_HOLD_TIME) {
                // Success! User held the sign for 1.5 seconds
                feedbackEl.textContent = `✓ Great! You signed "${currentTargetSign}"!`;
                feedbackEl.className = 'status-success';
            } else {
                // Still holding, show countdown
                const timeLeft = Math.max(0, SUCCESS_HOLD_TIME - timeHeld);
                feedbackEl.textContent = `Correct! Hold for ${(timeLeft / 1000).toFixed(1)}s...`;
                feedbackEl.className = 'status-holding';
            }
        }
    } else {
        // Reset hold timer if prediction is incorrect
        successStartTime = null;
        
        if (stablePrediction === "Ready..." || stablePrediction === "Initializing..." || 
            stablePrediction.includes("No hand")) {
            feedbackEl.className = 'status-waiting';
            feedbackEl.textContent = 'Show your hand clearly...';
        } else if (stablePrediction.includes("Error") || stablePrediction === "Unknown") {
            feedbackEl.className = 'status-incorrect';
            feedbackEl.textContent = `Status: ${stablePrediction}. Try adjusting hand position.`;
        } else {
            feedbackEl.className = 'status-incorrect';
            feedbackEl.textContent = `Not quite "${currentTargetSign}". You signed "${stablePrediction}". Keep trying!`;
        }
    }
}
