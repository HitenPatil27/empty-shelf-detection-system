# Supermarket Empty Shelf Detection System

This repository implements a real-time empty shelf detector using a custom-trained **YOLOv9** model, a serverless **Llama 3.1 Instruct** model (via Hugging Face API) to generate restock alert notifications, and a **Flutter mobile app** to receive push notifications and display live alerts.

---

## Live Detection Screenshot
![Live Stream Detection Screenshot](file:///d:/CV/Screenshot.png)

*View full image file: [Screenshot.png](file:///d:/CV/Screenshot.png)*

---

## Unified System Architecture

The project is structured with a unified streaming, reasoning, and alerting backend along with a Flutter mobile app.

```
d:/CV/
├── best.pt                             # Trained YOLOv9 weights
├── Recording 2025-04-05 225407.mp4     # Supermarket recording (fallback source)
├── Screenshot.png                      # Screenshot of the live detection stream
├── README.md                           # Setup and execution guide
├── backend/                            # Unified backend service
│   ├── ollama_server.py                # Unified Flask server (handles YOLO loops, Web streaming, VLM reasoning)
│   ├── detect_and_alert.py             # Desktop OpenCV-based detection client (optional)
│   ├── serviceAccountKey.json.example  # Example/template structure for the Firebase key
│   └── requirements.txt                # Backend Python package requirements
└── empty_shelf_app/                    # Unified Flutter project
    ├── android/app/google-services.json# Firebase Android config
    ├── pubspec.yaml                    # Flutter dependencies
    └── lib/
        └── main.dart                   # Enhanced Flutter UI with Alerts feed and notifications
```

---

## Setup & Running Guide

### 1. Prerequisites & Environment Setup

#### Environment Variables:
Obtain a Hugging Face API Token (from [Hugging Face Settings](https://huggingface.co/settings/tokens)) and configure it in your terminal environment:
```powershell
# Windows PowerShell
$env:HF_TOKEN="your_hugging_face_token_here"
```

#### Python Dependencies:
Install required packages using pip:
```bash
pip install -r backend/requirements.txt
```

---

### 2. Firebase Configuration

The application logs alerts to Firestore and dispatches notifications via FCM.

#### Backend Firebase Private Key:
1. Go to your **Firebase Console** -> **Project Settings** -> **Service accounts**.
2. Click **Generate new private key** and download the JSON.
3. Save it as `serviceAccountKey.json` inside the [backend/](file:///d:/CV/backend) directory.
*(Note: If not found, the server will run in **DRY-RUN** mode, skipping Firebase logging/notifications but keeping the live web stream and Hugging Face reasoning fully active).*

#### Flutter Mobile Client Config:
1. Ensure your Flutter environment is configured.
2. The [google-services.json](file:///d:/CV/empty_shelf_app/android/app/google-services.json) file is already added to the Android configuration.

---

### 3. Execution

1. **Start the Unified Web Streaming & Reasoning Server:**
   ```bash
   # Run the server with your HF_TOKEN configured
   $env:HF_TOKEN="your_hugging_face_token_here"
   python backend/ollama_server.py
   ```
   * This opens the video stream (prioritizing webcam `0`, with automatic fallback to the `Recording 2025-04-05 225407.mp4` video recording).
   * Web server starts on **`http://localhost:5000`**.

2. **Watch the Detection Stream:**
   * Open your web browser and go to **[http://localhost:5000](http://localhost:5000)**.
   * You will see the real-time YOLOv9 empty shelf detection bounding boxes overlaid on your camera feed.

3. **Start the Mobile Application (Optional):**
   ```bash
   cd empty_shelf_app
   flutter run
   ```

---

## Model Training & Demonstration
There is no Jupyter Notebook (`.ipynb`) included in this repository. Instead, the demonstration of the system training, execution, and detection runs has been captured and uploaded to the GitHub repository:

* **Demo/Training Recording:** [Recording 2025-04-05 225407.mp4](https://github.com/HitenPatil27/empty-shelf-detection-system/blob/main/Recording%202025-04-05%20225407.mp4) (126 MB)

### Git LFS (Large File Storage):
Because the recording is a large 126 MB file, it is tracked and hosted using **Git LFS**. 
When cloning this repository, run the following commands to download the actual video file:
```bash
# Initialize LFS and pull the video file
git lfs install
git lfs pull
```
