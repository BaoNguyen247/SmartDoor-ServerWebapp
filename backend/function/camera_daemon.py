import threading
import time
import cv2
import cv2.face as face_rec
import numpy as np
import paho.mqtt.client as mqtt

# Shared buffer and flag for inter-process communication with main.py
global_processed_frame = None
registration_active = threading.Event()

# Configuration (keep aligned with main.py)
DOOR_HOLD_TIME = 7
RECOGNITION_THRESHOLD = 100
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_CONTROL = "door/control"

# MQTT client used by the worker
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[camera_daemon] MQTT connected")
except Exception as e:
    print(f"[camera_daemon] MQTT connect failed: {e}")


class FaceRecognitionWorker:
    def __init__(self, video_source=0):
        self.facedetect = cv2.CascadeClassifier(
            "/home/bao/esp32project/SmartlockServerWeb/backend/data/haarcascade_frontalface_default.xml"
        )
        self.recognizer = face_rec.LBPHFaceRecognizer_create()
        try:
            self.recognizer.read("/home/bao/esp32project/SmartlockServerWeb/backend/data/lbph_model.yml")
            print("[camera_daemon] Recognizer model loaded")
        except Exception as e:
            print(f"[camera_daemon] Recognizer model not found or failed to load: {e}")
        
        self.label_map = {1: "Admin", 2: "User"}
        self.client = mqtt_client
        self.video_source = video_source
        self.door_open = False
        self.last_open_time = 0
        self.door_hold_time = DOOR_HOLD_TIME

    def process_frame(self, frame):
        """Process a single frame: detect faces, recognize, and update global buffer."""
        global global_processed_frame
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.facedetect.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            oh, ow = face.shape[:2]
            interp = cv2.INTER_AREA if (ow > 200 or oh > 200) else cv2.INTER_CUBIC
            face = cv2.resize(face, (200, 200), interpolation=interp)

            # If registration is active, just draw and skip recognition
            if registration_active.is_set():
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 165, 0), 2)
                continue

            # Perform recognition
            try:
                id, confidence = self.recognizer.predict(face)
                current_time = time.time()
                
                if confidence < RECOGNITION_THRESHOLD:
                    name = self.label_map.get(id, "Unknown")
                    # Check if enough time has passed since last door open
                    if not self.door_open and (current_time - self.last_open_time > self.door_hold_time):
                        self.client.publish(MQTT_TOPIC_CONTROL, "unlock")
                        print(f"[camera_daemon] Door unlocked for {name}")
                        self.door_open = True
                        self.last_open_time = current_time
                else:
                    print(f"[camera_daemon] Face detected but low confidence: {confidence}")
            except Exception as e:
                print(f"[camera_daemon] Recognition error: {e}")

            # Draw rectangle around detected face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # Check if door hold time has expired
        if self.door_open and (time.time() - self.last_open_time > self.door_hold_time):
            self.door_open = False
            print("[camera_daemon] Door hold time expired, ready for next unlock")

        # Update global frame buffer for streaming
        global_processed_frame = frame.copy()

    def run_stream(self):
        """Main loop: open video source and process frames continuously."""
        video = cv2.VideoCapture(self.video_source)
        if not video.isOpened():
            print(f"[camera_daemon] ERROR: cannot open video source {self.video_source}")
            return

        print(f"[camera_daemon] Video stream opened: {self.video_source}")
        try:
            frame_count = 0
            while True:
                ret, frame = video.read()
                if not ret:
                    print("[camera_daemon] Failed to read frame, reconnecting...")
                    video.release()
                    time.sleep(1)
                    video = cv2.VideoCapture(self.video_source)
                    continue
                
                self.process_frame(frame)
                frame_count += 1
                
                # Log every 100 frames
                if frame_count % 100 == 0:
                    print(f"[camera_daemon] Processed {frame_count} frames")
                
                time.sleep(1/30)  # ~30 FPS
        except KeyboardInterrupt:
            print("[camera_daemon] Stopping worker (KeyboardInterrupt)")
        except Exception as e:
            print(f"[camera_daemon] Unexpected error in run_stream: {e}")
        finally:
            video.release()
            print("[camera_daemon] Video stream released")