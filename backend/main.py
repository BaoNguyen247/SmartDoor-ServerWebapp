from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
import uvicorn
import MySQLdb
from MySQLdb import Error
from datetime import datetime
import cv2
import time
import threading
import cv2.face as face_rec
from contextlib import asynccontextmanager # Thư viện mới
import io

import numpy as np # Needed for thread-safe frame sharing
from starlette.responses import StreamingResponse # Import the streaming class
from typing import Dict

# Import the reusable add_face function
try:
    from add_face import add_face
except Exception:
    # Fallback to package-style import when run as a package
    from .add_face import add_face

global_processed_frame = None 
 
# Thread-safe flag to indicate a registration (add_face) job is running.
# When set, the recognition worker should avoid publishing/acting on detections.
registration_active = threading.Event()


app = FastAPI()

# --- CẤU HÌNH ---
DOOR_HOLD_TIME = 7
RECOGNITION_THRESHOLD = 100
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_CONTROL = "door/control" # Đổi tên biến để tránh nhầm lẫn
MQTT_ALERT_TOPIC = "door/alert"
MQTT_OPENLOG_TOPIC = "door/open"
# ESP32 camera and local daemon stream
ESP32_CAM_STREAM = "http://10.251.12.188:81/stream" # 👈 Địa chỉ ESP32-CAM 640x480
# When daemon runs separately it will serve processed MJPEG on port 8001
PC_STREAM = "http://localhost:8001/video_feed"
#PC_STREAM = 0

# --- Ví dụ về Tải mô hình và Kết nối MQTT (Giả định) ---
recognizer = face_rec.LBPHFaceRecognizer_create()
recognizer.read("/home/bao/esp32project/SmartlockServerWeb/backend/data/lbph_model.yml")
label_map = {1: "Admin", 2: "User"}
client = mqtt.Client()
client.connect("localhost", 1883, 60)
client.loop_start() 

# CORS configuration for frontend compatibility
app.add_middleware(
    CORSMiddleware,
    # During development allow the common local dev origins. Use a stricter list in production.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": "localhost",
    "user": "backend_user",
    "passwd": "Workfromhome247@",
    "db": "smart_lock_db"
}



# --- KHỞI TẠO GLOBAL ---
# Dùng VERSION2 để loại bỏ DeprecationWarning
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) 
recognizer = face_rec.LBPHFaceRecognizer_create()
recognizer.read("/home/bao/esp32project/SmartlockServerWeb/backend/data/lbph_model.yml")
label_map = {1: "Admin", 2: "User"}


class FaceRecognitionWorker:
    def __init__(self, recognizer, label_map, mqtt_client, video_source=0):
        # Đã sửa lỗi đường dẫn trong file gốc của bạn
        self.facedetect = cv2.CascadeClassifier("/home/bao/esp32project/SmartlockServerWeb/backend/data/haarcascade_frontalface_default.xml")
        self.recognizer = recognizer
        self.label_map = label_map
        self.client = mqtt_client
        self.video_source = video_source
        self.door_open = False
        self.last_open_time = 0
        self.door_hold_time = DOOR_HOLD_TIME
        self.mqtt_topic = MQTT_TOPIC_CONTROL # Dùng biến mới
        self.recognition_threshold = RECOGNITION_THRESHOLD  

    def process_frame(self, frame):
        """Xử lý logic nhận diện trên một frame duy nhất."""
        
        # 1. Tiền xử lý
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Đã thêm minSize để hỗ trợ nhận diện khuôn mặt nhỏ hơn từ luồng IP
        faces = self.facedetect.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            # Resize to 200x200 using INTER_AREA for shrinking and INTER_CUBIC for enlarging
            oh, ow = face.shape[:2]
            if ow > 200 or oh > 200:
                interp = cv2.INTER_AREA
            else:
                interp = cv2.INTER_CUBIC
            face = cv2.resize(face, (200, 200), interpolation=interp)

            # If a registration job is active, skip recognition/publishing to avoid
            # interfering with the add_face process. Still draw the rectangle so the
            # processed stream remains visually useful.
            if registration_active.is_set():
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 165, 0), 2)  # orange to indicate paused recognition
                continue

            id, confidence = self.recognizer.predict(face)
            current_time = time.time()

            if confidence < self.recognition_threshold:
                name = self.label_map.get(id, "Unknown")
                if not self.door_open and (current_time - self.last_open_time > self.door_hold_time):
                    # Gửi lệnh mở cửa
                    self.client.publish(self.mqtt_topic, "unlock")
                    # Ghi log mở cửa bởi người được nhận diện
                    interact_smart_lock_logs(operation="insert", event_type="OPEN", name=name)
                    self.door_open = True
                    self.last_open_time = current_time
                    print(f"USER, confidence {confidence:.2f}")

            else:
                # ⚠️ Tùy chọn: Bạn có thể thêm code hiển thị "Unknown"
                print(f"DEBUG: Unknown face, confidence {confidence:.2f}")

            # Draw recognition rectangle in green
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # ❌ CRITICAL FIX: REMOVED FRAME SHARING FROM HERE!
            # It was: global_processed_frame = frame.copy() 
        
        # 3. Logic Reset trạng thái (Runs after checking all faces)
        if self.door_open and (time.time() - self.last_open_time > self.door_hold_time):
            self.door_open = False
            print("⏱️ Cho phép nhận diện lại để mở cửa")
            # Bạn có thể gửi lệnh "lock" ở đây nếu khóa của bạn cần lệnh đóng rõ ràng
            # self.client.publish(self.mqtt_topic, "lock") 

        # --- CORRECTED LOCATION FOR FRAME SHARING ---
        # Share the fully processed frame (with all rectangles and after door logic)
        global global_processed_frame
        # It's better to store a copy or encoded version for thread-safety 
        # but for simplicity, we'll assign the processed NumPy array here.
        # Ensure you handle thread synchronization in a production system.
        global_processed_frame = frame.copy() # Store a copy of the processed frame

        # Trả về frame (tùy chọn, nếu bạn muốn stream video đã xử lý)
        return frame


    def run_stream(self):
        """Khởi chạy vòng lặp xử lý video liên tục (Dùng cho Camera kết nối trực tiếp)"""
        video = cv2.VideoCapture(self.video_source)
        if not video.isOpened():
            print(f"Lỗi: Không thể mở nguồn video {self.video_source}")
            return

        print("Bắt đầu xử lý luồng video...")
        
        # ⚠️ Tùy chọn: Bạn có thể thêm cv2.namedWindow và cv2.imshow ở đây
        # nếu bạn chạy backend trên máy có giao diện và muốn xem kết quả debug.

        try:
            while True:
                ret, frame = video.read()
                if not ret:
                    break
                
                # Xử lý frame
                processed_frame = self.process_frame(frame)
                
                # ⚠️ Tùy chọn: Hiển thị kết quả (chỉ dùng cho debug/desktop app)
                # cv2.imshow("Debug Stream", processed_frame)
                # if cv2.waitKey(1) == ord('q'):
                #     break
                
                # Giả sử tốc độ xử lý là 30 FPS
                time.sleep(1/30) 

        except KeyboardInterrupt:
            print("Dừng luồng nhận diện.")
        finally:
            video.release()
            # cv2.destroyAllWindows() # Chỉ gọi nếu đã dùng imshow


# Biến toàn cục để giữ luồng worker
face_worker: FaceRecognitionWorker = None
worker_thread: threading.Thread = None

# Simple in-memory job tracker for add_face background jobs
add_face_jobs: Dict[str, dict] = {}

# Callback when the client connects to the broker
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with code {rc}")
    # Subscribe to the door/alert topic
    client.subscribe(MQTT_ALERT_TOPIC)
    client.subscribe(MQTT_OPENLOG_TOPIC)
    print(f"Subscribed to topic: {MQTT_ALERT_TOPIC}")
    print(f"Subscribed to topic: {MQTT_OPENLOG_TOPIC}")

# Callback when a message is received from the subscribed topic
def on_message(client, userdata, msg):
    print(f"Received topic {msg.topic}: {msg.payload.decode()}")
    if (msg.topic == "door/open"):
        result_insert_open = interact_smart_lock_logs(
            operation="insert",
            event_type="OPEN",
            name="Unknown"
        )
        print(result_insert_open)
    if (msg.topic == "door/alert"):
        result_insert_open = interact_smart_lock_logs(
            operation="insert",
            event_type="ALERT",
            name="Unknown"
        )
        print(result_insert_open)    


mqtt_client.on_message = on_message
mqtt_client.on_connect = on_connect

def interact_smart_lock_logs(operation, **kwargs):
    """
    Interact with the smart_lock_logs table, using the updated schema 
    (timestamp is auto-generated, 'name' column added, 'created_at' removed).
    
    Args:
        operation (str): Operation to perform ('query_all', 'search_by_day', 'filter_by_event', 'insert')
        **kwargs: Additional parameters depending on the operation
            - For search_by_day: date (str, format 'YYYY-MM-DD')
            - For filter_by_event: event_type (str)
            - For insert: event_type (str), name (str, optional)
            
            NOTE: 'timestamp' for insert is now automatically handled by the database.
    
    Returns:
        dict: Result of the operation (e.g., list of logs or success message)
    """
    connection = None
    try:
        # Connect to the database
        # ⚠️ DB_CONFIG phải được định nghĩa trong phạm vi này hoặc được truyền vào
        connection = MySQLdb.connect(**DB_CONFIG) 
        cursor = connection.cursor()

        # --- Cấu trúc dữ liệu mới: id, timestamp, event_type, name ---
        
        if operation == "query_all":
            # Retrieve all logs
            cursor.execute("SELECT id, timestamp, event_type, name FROM smart_lock_logs")
            logs = cursor.fetchall()
            return {
                "logs": [
                    {
                        "id": log[0],
                        "timestamp": log[1].isoformat(),
                        "event_type": log[2],
                        "name": log[3]
                    } for log in logs
                ]
            }

        elif operation == "search_by_day":
            # Search logs by date (based on timestamp)
            date = kwargs.get("date")
            if not date:
                raise ValueError("date parameter is required for search_by_day")
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise ValueError("date must be in YYYY-MM-DD format")
            
            query = """
            SELECT id, timestamp, event_type, name
            FROM smart_lock_logs 
            WHERE DATE(timestamp) = %s
            """
            cursor.execute(query, (date,))
            logs = cursor.fetchall()
            return {
                "logs": [
                    {
                        "id": log[0],
                        "timestamp": log[1].isoformat(),
                        "event_type": log[2],
                        "name": log[3]
                    } for log in logs
                ]
            }

        elif operation == "filter_by_event":
            # Filter logs by event_type
            event_type = kwargs.get("event_type")
            if not event_type:
                raise ValueError("event_type parameter is required for filter_by_event")
            if event_type not in ["OPEN", "LOCK", "ALERT"]:
                raise ValueError("event_type must be one of: OPEN, LOCKSYSTEM, ALERT")
            
            query = """
            SELECT id, timestamp, event_type, name
            FROM smart_lock_logs 
            WHERE event_type = %s
            """
            cursor.execute(query, (event_type,))
            logs = cursor.fetchall()
            return {
                "logs": [
                    {
                        "id": log[0],
                        "timestamp": log[1].isoformat(),
                        "event_type": log[2],
                        "name": log[3]
                    } for log in logs
                ]
            }

        elif operation == "insert":
            # Insert a new log entry (timestamp is auto-generated by the DB)
            event_type = kwargs.get("event_type")
            name = kwargs.get("name", None) # name is optional in the call, defaults to None/NULL
            
            if not event_type:
                raise ValueError("event_type is required for insert")
            if event_type not in ["OPEN", "LOCKSYSTEM", "ALERT"]:
                raise ValueError("event_type must be one of: OPEN, LOCK, ERROR, ATTEMPT")
            
            query = """
            INSERT INTO smart_lock_logs (event_type, name) 
            VALUES (%s, %s)
            """
            # Sử dụng tuple (event_type, name) cho tham số
            cursor.execute(query, (event_type, name)) 
            connection.commit()
            return {"message": "Log entry inserted successfully", "id": cursor.lastrowid}

        else:
            raise ValueError(f"Unsupported operation: {operation}")

    except Error as e:
        return {"error": f"Database error: {e}"}
    except ValueError as e:
        return {"error": str(e)}
    except NameError as e:
        # Xử lý nếu DB_CONFIG chưa được định nghĩa
        return {"error": f"Configuration error: {e}. Ensure DB_CONFIG is defined."}
    finally:
        if connection and connection.open:
            cursor.close()
            connection.close()

# --- Video Streaming Generator ---
def generate_mjpeg_stream():
    """Generates the MJPEG stream from the global frame buffer."""
    global global_processed_frame
    
    while True:
        # Check if a frame is available
        if global_processed_frame is None:
            time.sleep(0.05) # Wait a bit if no frame is ready
            continue

        # Use a try block to ensure the lock/copy is handled safely in a real system
        # Encode the frame from OpenCV format (NumPy array) to JPEG bytes
        ret, buffer = cv2.imencode('.jpg', global_processed_frame, 
                                     [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        if not ret:
            time.sleep(0.1)
            continue
            
        frame_bytes = buffer.tobytes()

        # MJPEG format: Boundary + Headers + Image Bytes
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
               b'\r\n' + frame_bytes + b'\r\n')
        
        # Control the stream rate (e.g., aiming for 30 FPS)
        time.sleep(1/30) 

# --- FastAPI Endpoint ---
@app.get("/video_feed")
def video_feed():
    """Endpoint to stream the processed video feed as MJPEG."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        # The specific Content-Type for MJPEG streaming
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# FastAPI startup event to connect MQTT client
@app.on_event("startup")
async def startup_event():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print("MQTT client connected and loop started")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {str(e)}")

# FastAPI shutdown event to disconnect MQTT client
@app.on_event("shutdown")
async def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("MQTT client disconnected and loop stopped")



# Endpoint to open the door
@app.post("/open-door")
async def open_door():
    try:
        # Publish to the configured control topic
        mqtt_client.publish(MQTT_TOPIC_CONTROL, "unlock")
        print(f"Published open command to {MQTT_TOPIC_CONTROL}")
        return {"message": "Door open command sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send open command: {str(e)}")

# Endpoint to activate the door
@app.post("/activate-door")
async def activate_door():
    try:
        mqtt_client.publish(MQTT_TOPIC_CONTROL + "/activate", "activedoor")
        print(f"Published activate command to {MQTT_TOPIC_CONTROL}/activate")
        return {"message": "Door activate command sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send activate command: {str(e)}")

# Endpoint to deactivate the door
@app.post("/deactivate-door")
async def deactivate_door():
    try:
        mqtt_client.publish(MQTT_TOPIC_CONTROL + "/deactivate", "deactivatedoor")
        print(f"Published deactivate command to {MQTT_TOPIC_CONTROL}/deactivate")
        return {"message": "Door deactivate command sent"}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to send deactivate command: {str(e)}")


# Endpoint to start adding a face (runs add_face in background)
@app.post('/api/add_face')
def api_add_face(payload: dict):
    """Start collecting face images and retrain model in background.

    Expected JSON payload: {"name": "Bao", "camera": 0, "images": 100, "interval": 10, "nodisplay": false}
    Returns: {"job_id": "<id>", "status": "running"}
    """

    name = payload.get('name')
    if not name:
        raise HTTPException(status_code=400, detail='name is required')

    camera = int(payload.get('camera', 0))
    images = int(payload.get('images', 100))
    interval = int(payload.get('interval', 10))
    nodisplay = bool(payload.get('nodisplay', False))
    # Accept an optional video_source (e.g., an IP camera URL). If provided, pass it to add_face.
    video_source = payload.get('video_source')
    if not video_source:
        # default to the global PC_STREAM when available
        video_source = PC_STREAM

    import uuid
    job_id = uuid.uuid4().hex
    add_face_jobs[job_id] = {
        'status': 'running',
        'started_at': datetime.utcnow().isoformat(),
        'result': None,
        'error': None
    }

    def _run_job(jid, person_name, cam, imgs, inter, show, vsource):
        try:
            # When triggered via the web API, always run headless on the server
            # to avoid opening an OpenCV GUI window on the backend host.
            # Notify daemon to pause recognition while we collect training data
            try:
                import requests
                requests.post('http://127.0.0.1:8001/pause_registration', timeout=2)
            except Exception as _:
                # If the daemon isn't available, proceed anyway (best-effort)
                print('Warning: unable to notify daemon to pause_registration')

            mapping = add_face(person_name, camera_index=cam, video_source=vsource, num_images=imgs, frame_interval=inter, display=False)

            # Resume recognition on the daemon
            try:
                import requests
                requests.post('http://127.0.0.1:8001/resume_registration', timeout=2)
            except Exception:
                print('Warning: unable to notify daemon to resume_registration')
            add_face_jobs[jid]['status'] = 'done'
            add_face_jobs[jid]['result'] = mapping
            add_face_jobs[jid]['finished_at'] = datetime.utcnow().isoformat()
        except Exception as e:
            add_face_jobs[jid]['status'] = 'error'
            add_face_jobs[jid]['error'] = str(e)
            add_face_jobs[jid]['finished_at'] = datetime.utcnow().isoformat()

    t = threading.Thread(target=_run_job, args=(job_id, name, camera, images, interval, not nodisplay, video_source))
    t.daemon = True
    t.start()

    return {"job_id": job_id, "status": "running"}


@app.get('/api/add_face/status/{job_id}')
def api_add_face_status(job_id: str):
    info = add_face_jobs.get(job_id)
    if not info:
        raise HTTPException(status_code=404, detail='job_id not found')
    return info


if __name__ == "__main__":
    worker = FaceRecognitionWorker(
        recognizer=recognizer, 
        label_map=label_map, 
        mqtt_client=mqtt_client, 
        #video_source="http://10.251.13.156/stream" # Hoặc địa chỉ IP Camera
        video_source=0
    )

    worker_thread = threading.Thread(target=worker.run_stream)
    worker_thread.daemon = True # Luồng sẽ tự dừng khi chương trình chính dừng
    worker_thread.start()
    print(interact_smart_lock_logs("query_all"))
    uvicorn.run(app, host="0.0.0.0", port=8000)
