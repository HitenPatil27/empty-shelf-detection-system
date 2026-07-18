from flask import Flask, render_template_string, Response, jsonify
import cv2
import os
import time
import requests
import datetime
from ultralytics import YOLO

app = Flask(__name__)

# Hugging Face configuration
HF_TOKEN = os.environ.get("HF_TOKEN")
# Default to meta-llama/Llama-3.1-8B-Instruct which is live on featherless-ai provider
DEFAULT_MODEL_ID = os.environ.get("HF_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")

# OpenAI compatible API URL on Hugging Face router for featherless-ai
API_URL = "https://router.huggingface.co/featherless-ai/v1/chat/completions"

# Firebase Setup
firebase_enabled = False
db = None
messaging = None
cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")

if os.path.exists(cred_path):
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore, messaging as f_messaging
        
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        messaging = f_messaging
        firebase_enabled = True
        print("[Firebase] Successfully initialized Firebase Admin SDK.")
    except Exception as e:
        print(f"[Firebase] Error initializing Firebase: {e}")
else:
    print("[Firebase] serviceAccountKey.json not found. Running in DRY-RUN mode.")

# Load YOLO model
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(base_dir, "best.pt")
if not os.path.exists(model_path):
    model_path = "best.pt"

print(f"Loading YOLO model from: {model_path}")
model = YOLO(model_path)

# Resolve video source: try webcam (0) first, fallback to video file
video_source = 0
mp4_path = os.path.join(base_dir, "Recording 2025-04-05 225407.mp4")
camera_available = False

# Test webcam index 0
cap_test = cv2.VideoCapture(0)
if cap_test.isOpened():
    camera_available = True
    cap_test.release()

if camera_available:
    video_source = 0
    print("Using live webcam (0) as the video feed.")
elif os.path.exists(mp4_path):
    video_source = mp4_path
    print(f"Webcam not available. Using video recording fallback: {mp4_path}")
else:
    print("Error: Neither live webcam nor fallback video recording was found.")

# Alert debouncer/cooldown
COOLDOWN_SECONDS = 30
last_alert_time = 0

# HTML template for streaming view
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YOLOv9 - Empty Shelf Detection Stream</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #121212;
            color: #ffffff;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: #e53935;
        }
        .container {
            max-width: 900px;
            text-align: center;
            background: #1e1e1e;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.5);
        }
        img {
            max-width: 100%;
            border-radius: 5px;
            border: 2px solid #333;
        }
        .status {
            margin-top: 15px;
            font-size: 1.1em;
            color: #81c784;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Empty Shelf Detection Stream</h1>
        <p>Live YOLOv9 frame processing & visual analysis</p>
        <img src="/video_feed" alt="Live stream loading...">
        <div class="status">System status: Active & Monitoring</div>
    </div>
</body>
</html>
"""

def generate_alert(analysis_text):
    """Sends Firestore log and FCM push notification using HF analysis."""
    if not firebase_enabled:
        print("[Firebase] Bypassed Firestore log and FCM alert (dry-run mode).")
        return
        
    try:
        now = datetime.datetime.now()
        alert_data = {
            "product": "Empty Shelf",
            "timestamp": now.isoformat(),
            "reason": analysis_text
        }
        db.collection("alerts").add(alert_data)
        print("[Firebase] Alert logged to Firestore collection 'alerts'.")

        message = messaging.Message(
            notification=messaging.Notification(
                title="Shelf Empty Alert!",
                body=analysis_text
            ),
            topic="shelf_alerts"
        )
        response_id = messaging.send(message)
        print(f"[Firebase] Push notification sent: {response_id}")
    except Exception as e:
        print(f"[Firebase] Error sending notification: {e}")

def query_llama_alert(model_id=DEFAULT_MODEL_ID):
    """Queries Hugging Face Llama 3.1 to generate alert text."""
    # Map Meta-Llama-3.1 to Llama-3.1-8B-Instruct for provider compatibility
    if "meta-llama-3.1" in model_id.lower() or "meta-llama/meta-llama-3.1" in model_id.lower():
        model_id = "meta-llama/Llama-3.1-8B-Instruct"

    if not HF_TOKEN:
        return "Attention staff: An empty shelf has been detected and requires restocking."
        
    try:
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": "Write a short, professional supermarket notification alert informing staff that a shelf is empty and needs restocking. Keep the response concise, under 25 words."
                }
            ],
            "max_tokens": 60
        }
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            print(f"[HF API Error] {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[HF API Error] Exception: {e}")
        
    return "Attention staff: An empty shelf has been detected and requires restocking."

def gen_frames():
    global last_alert_time
    cap = cv2.VideoCapture(video_source)
    
    while True:
        success, frame = cap.read()
        if not success:
            # If it's a video file, loop it back to the beginning when it ends
            if isinstance(video_source, str):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                break
                
        # Run inference
        results = model(frame, verbose=False)
        
        empty_detected = False
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = r.names[cls_id]
                if label.lower() == "empty":
                    empty_detected = True
                    break
                    
        # Draw boxes on the frame
        annotated_frame = results[0].plot()
        
        # Check alert debouncing
        current_time = time.time()
        if empty_detected and (current_time - last_alert_time > COOLDOWN_SECONDS):
            last_alert_time = current_time
            print("\n[Alert] Empty shelf detected! Querying Hugging Face Llama 3.1...")
            
            # Query LLM and dispatch alerts
            analysis_text = query_llama_alert()
            print(f"[Alert Text] {analysis_text}")
            generate_alert(analysis_text)
            
        # Encode frame as JPEG bytes
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
    cap.release()

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/reason', methods=['POST'])
def reason():
    # Keep support for manual reasoning POST requests
    try:
        data = request.json or {}
        model_id = data.get("model", DEFAULT_MODEL_ID)
        analysis_text = query_llama_alert(model_id)
        return jsonify({"message": analysis_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Unified Streaming Reasoning Flask Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
