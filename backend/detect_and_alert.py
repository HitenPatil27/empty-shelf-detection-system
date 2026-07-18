from ultralytics import YOLO
import cv2
import requests
import base64
import os
import time
import datetime

# Attempt to initialize Firebase Admin SDK
firebase_enabled = False
db = None
messaging = None

# Look for credentials file
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
        print("[Firebase] Running in DRY-RUN mode (no Firestore logging or push notifications).")
else:
    print(f"[Firebase] serviceAccountKey.json not found at {cred_path}.")
    print("[Firebase] Running in DRY-RUN mode (no Firestore logging or push notifications).")

# Resolve model path (expect best.pt in the workspace root, one level up)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(base_dir, "best.pt")

if not os.path.exists(model_path):
    # Fallback to local directory if not found one level up
    model_path = "best.pt"

print(f"Loading YOLO model from: {model_path}")
model = YOLO(model_path)

# Initialize video source: try live webcam first
video_source = 0
print("Attempting to open live webcam (0)...")
cap = cv2.VideoCapture(video_source)

if not cap.isOpened():
    print("Live webcam not available. Attempting fallback to video recording...")
    mp4_path = os.path.join(base_dir, "Recording 2025-04-05 225407.mp4")
    if os.path.exists(mp4_path):
        video_source = mp4_path
        print(f"Running detection on video recording fallback: {mp4_path}")
        cap = cv2.VideoCapture(video_source)
    else:
        print("Error: Neither live webcam nor fallback video recording was found.")
        exit(1)

# Configuration parameters
REASON_URL = "http://localhost:5000/reason"
COOLDOWN_SECONDS = 30
last_alert_time = 0

print("Starting Empty Shelf Detection loop. Press 'q' or 'ESC' to exit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to read frame from camera.")
        break

    # Run inference
    results = model(frame, verbose=False)
    
    empty_detected = False
    
    for r in results:
        # Check if 'empty' is in the detected classes
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = r.names[cls_id]
            if label.lower() == "empty":
                empty_detected = True
                break

    # Draw boxes on the frame to show on screen
    annotated_frame = results[0].plot()

    current_time = time.time()
    if empty_detected and (current_time - last_alert_time > COOLDOWN_SECONDS):
        last_alert_time = current_time
        print("\n[Alert] Empty shelf detected! Triggering reasoning and notifications...")

        # Encode frame to base64
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Request detailed analysis from the Ollama reasoning server
        try:
            response = requests.post(REASON_URL, json={"image_base64": img_base64}, timeout=30)
            if response.status_code == 200:
                analysis = response.json().get("message", "No description returned.")
                print(f"[LLM Analysis] {analysis}")

                # Send Firebase Notification and log to Firestore
                if firebase_enabled:
                    try:
                        # Log to Firestore
                        now = datetime.datetime.now()
                        alert_data = {
                            "product": "Empty Shelf",
                            "timestamp": now.isoformat(),
                            "reason": analysis
                        }
                        db.collection("alerts").add(alert_data)
                        print("[Firebase] Alert logged to Firestore collection 'alerts'.")

                        # Send Push Notification
                        message = messaging.Message(
                            notification=messaging.Notification(
                                title="Shelf Empty Alert!",
                                body=analysis
                            ),
                            topic="shelf_alerts"
                        )
                        response_id = messaging.send(message)
                        print(f"[Firebase] Push notification sent: {response_id}")
                    except Exception as e:
                        print(f"[Firebase] Error sending notification/log: {e}")
                else:
                    print("[Firebase] Bypassed Firestore and Push notification (dry-run mode).")
            else:
                print(f"[Error] Reasoning server returned error: {response.text}")
        except Exception as e:
            print(f"[Error] Could not connect to reasoning server at {REASON_URL}: {e}")
            print("Make sure backend/ollama_server.py is running and Ollama is active.")

    # Show live feed
    cv2.imshow("YOLOv9 - Empty Shelf Detection", annotated_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27: # 'q' or ESC
        break

cap.release()
cv2.destroyAllWindows()
