from fastapi import FastAPI
import threading
import time
import cv2
import cv2.face as face_rec
import numpy as np
import paho.mqtt.client as mqtt
from starlette.responses import StreamingResponse

# Shared buffer and flag
global_processed_frame = None
registration_active = threading.Event()

app = FastAPI()

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
    print("Daemon: MQTT connected")
except Exception as e:
    print(f"Daemon: MQTT connect failed: {e}")


class FaceRecognitionWorker:
    def __init__(self, video_source=0):
        self.facedetect = cv2.CascadeClassifier("/home/bao/esp32project/SmartlockServerWeb/backend/data/haarcascade_frontalface_default.xml")
        self.recognizer = face_rec.LBPHFaceRecognizer_create()
        try:
            self.recognizer.read("/home/bao/esp32project/SmartlockServerWeb/backend/data/lbph_model.yml")
        except Exception:
            print("Daemon: recognizer model not found or failed to load")
        self.label_map = {1: "Admin", 2: "User"}
        self.client = mqtt_client
        self.video_source = video_source
        self.door_open = False
        self.last_open_time = 0
        self.door_hold_time = DOOR_HOLD_TIME

    def process_frame(self, frame):
        global global_processed_frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.facedetect.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            oh, ow = face.shape[:2]
            interp = cv2.INTER_AREA if (ow > 200 or oh > 200) else cv2.INTER_CUBIC
            face = cv2.resize(face, (200, 200), interpolation=interp)

            if registration_active.is_set():
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 165, 0), 2)
                continue

            try:
                id, confidence = self.recognizer.predict(face)
                current_time = time.time()
                if confidence < RECOGNITION_THRESHOLD:
                    name = self.label_map.get(id, "Unknown")
                    if not self.door_open and (current_time - self.last_open_time > self.door_hold_time):
                        self.client.publish(MQTT_TOPIC_CONTROL, "unlock")
                        # Optionally log to DB via API if needed
                        self.door_open = True
                        self.last_open_time = current_time
                else:
                    pass
            except Exception:
                pass

            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        if self.door_open and (time.time() - self.last_open_time > self.door_hold_time):
            self.door_open = False

        global_processed_frame = frame.copy()
        return frame

    def run_stream(self):
        video = cv2.VideoCapture(self.video_source)
        if not video.isOpened():
            print(f"Daemon: cannot open video source {self.video_source}")
            return

        print("Daemon: starting video stream processing...")
        try:
            while True:
                ret, frame = video.read()
                if not ret:
                    break
                self.process_frame(frame)
                time.sleep(1/30)
        except KeyboardInterrupt:
            print("Daemon: stopping worker")
        finally:
            video.release()


def generate_mjpeg_stream():
    global global_processed_frame
    while True:
        if global_processed_frame is None:
            time.sleep(0.05)
            continue
        ret, buffer = cv2.imencode('.jpg', global_processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ret:
            time.sleep(0.1)
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
               b'\r\n' + frame_bytes + b'\r\n')
        time.sleep(1/30)


@app.get('/video_feed')
def video_feed():
    return StreamingResponse(generate_mjpeg_stream(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.post('/pause_registration')
def pause_registration():
    registration_active.set()
    return {'status': 'paused'}


@app.post('/resume_registration')
def resume_registration():
    registration_active.clear()
    return {'status': 'running'}


@app.get('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    # start worker and run on port 8001
    worker = FaceRecognitionWorker(video_source=0)
    wt = threading.Thread(target=worker.run_stream, daemon=True)
    wt.start()
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001)
