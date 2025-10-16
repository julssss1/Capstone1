/**
 * Client-Side Sign Language Recognition
 * Uses MediaPipe Hands for hand tracking and TensorFlow.js for sign classification
 */

class SignRecognitionClient {
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
        
        // Request throttling for free Render hosting
        this.lastPredictionTime = 0;
        this.predictionThrottleMs = 600; // Only predict every 200ms (5 times per second)
        this.pendingPrediction = false;
    }

    /**
     * Initialize the recognition system
     */
    async initialize() {
        try {
            console.log("Initializing Sign Recognition Client...");
            
            // Load class names
            await this.loadClassNames();
            
            // Load TensorFlow.js TFLite model
            await this.loadModel();
            
            // Initialize MediaPipe Hands
            await this.initializeMediaPipeHands();
            
            console.log("Sign Recognition Client initialized successfully");
            this.stableDisplay = "Ready...";
            return true;
        } catch (error) {
            console.error("Failed to initialize:", error);
            this.stableDisplay = "Initialization Failed";
            throw error;
        }
    }

    /**
     * Load class names from JSON file
     */
    async loadClassNames() {
        // Use alphabet as class names (server-side API handles actual class names)
        this.classNames = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
        console.log("Using alphabet class names (server-side API handles predictions)");
    }

    /**
     * Load the TFLite model using TensorFlow.js
     * NOTE: Due to conversion issues, we'll use server-side prediction API
     */
    async loadModel() {
        console.log("Model loading skipped - using server-side API");
        console.log("This works better on Render hosting");
        this.model = "server-side"; // Flag to use server API
        return true;
    }

    /**
     * Initialize MediaPipe Hands
     */
    async initializeMediaPipeHands() {
        console.log("Initializing MediaPipe Hands...");
        
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
        
        console.log("MediaPipe Hands initialized");
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

            this.isRunning = true;
            this.processFrame();
            
            console.log("Camera started successfully");
            return true;
        } catch (error) {
            console.error("Error starting camera:", error);
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
     * Handle MediaPipe Hands results
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
            const landmarks = results.multiHandLandmarks[0];
            
            // Draw landmarks
            drawConnectors(this.canvasCtx, landmarks, HAND_CONNECTIONS, { color: '#00FF00', lineWidth: 2 });
            drawLandmarks(this.canvasCtx, landmarks, { color: '#FF0000', lineWidth: 1, radius: 3 });

            // Normalize landmarks
            const normalizedLandmarks = this.normalizeLandmarks(landmarks);
            
            if (normalizedLandmarks) {
                // Make prediction
                const prediction = await this.predict(normalizedLandmarks);
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
     * Normalize hand landmarks
     */
    normalizeLandmarks(landmarks) {
        try {
            // Use wrist as origin
            const wrist = landmarks[0];
            const originX = wrist.x;
            const originY = wrist.y;

            // Calculate scale using middle finger MCP
            const middleMCP = landmarks[9];
            const scale = Math.sqrt(
                Math.pow(middleMCP.x - originX, 2) + 
                Math.pow(middleMCP.y - originY, 2)
            );

            if (scale < 1e-6) return null;

            // Normalize all landmarks
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
     * Make prediction using server-side API with throttling
     * Limits requests to reduce server load on free Render hosting
     */
    async predict(landmarkData) {
        const currentTime = Date.now();
        
        // Throttle: Only make prediction if enough time has passed
        if (currentTime - this.lastPredictionTime < this.predictionThrottleMs) {
            // Return last prediction if throttled
            return {
                sign: this.lastPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        // Prevent concurrent requests
        if (this.pendingPrediction) {
            return {
                sign: this.lastPrediction || "Processing...",
                confidence: this.lastConfidence || 0.0
            };
        }
        
        this.pendingPrediction = true;
        this.lastPredictionTime = currentTime;
        
        try {
            // Send landmarks to server for prediction
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
            
            // Cache result
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
     * Update stable prediction based on buffer
     */
    updateStablePrediction() {
        if (this.predictionBuffer.length < this.bufferSize) return;

        const invalidStates = ["Unknown", "No hand detected", "Processing Error", 
                               "Landmark count error", "Detect Error", "...", 
                               "Low Confidence", "Prediction Error"];

        // Count occurrences
        const counts = {};
        for (const pred of this.predictionBuffer) {
            counts[pred] = (counts[pred] || 0) + 1;
        }

        // Find most common prediction
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
        this.canvasCtx.font = 'bold 24px Arial';
        this.canvasCtx.fillStyle = '#FF7800';
        this.canvasCtx.fillText(
            `Detect: ${instantPrediction} ${confidence > 0 ? `(${(confidence * 100).toFixed(2)}%)` : ''}`,
            10, 30
        );

        const invalidStates = ["Unknown", "No hand detected", "Ready...", "Initializing..."];
        let stableColor = '#00FF00';
        if (invalidStates.includes(this.stableDisplay)) {
            stableColor = '#C8C8C8';
        }
        if (this.stableDisplay.includes("Error")) {
            stableColor = '#FF0000';
        }

        this.canvasCtx.font = 'bold 32px Arial';
        this.canvasCtx.fillStyle = stableColor;
        this.canvasCtx.fillText(`Stable: ${this.stableDisplay}`, 10, 70);
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

        this.stableDisplay = "Offline";
        console.log("Camera stopped");
    }
}

// Export for use in other scripts
window.SignRecognitionClient = SignRecognitionClient;
