from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.api_door import router as door_router


import threading
from starlette.responses import StreamingResponse
import time
import cv2
from .function.camera_daemon import FaceRecognitionWorker, global_processed_frame



app = FastAPI()     

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(door_router)

def start_daemon_worker(video_source=0):
    """Start the face recognition worker in a background thread."""
    worker = FaceRecognitionWorker(video_source=video_source)
    worker_thread = threading.Thread(target=worker.run_stream, daemon=True)
    worker_thread.start()
    print("[main.py] Daemon worker started on port 8000")
    return worker_thread

# Start the daemon on app startup
daemon_thread = start_daemon_worker(video_source=0)  # Change to your video source (e.g., ESP32 URL)


def generate_mjpeg_stream():
    """Generate MJPEG stream from global_processed_frame."""
    import sys
    from .function import camera_daemon
    
    frame_count = 0
    while True:
        # Access the global variable from camera_daemon module
        frame = camera_daemon.global_processed_frame
        
        if frame is None:
            print(f"[video_feed] Waiting for first frame from daemon... ({frame_count})")
            time.sleep(0.1)
            frame_count += 1
            if frame_count > 300:  # After 30 seconds of no frames, log warning
                print("[video_feed] WARNING: No frames received from daemon for 30 seconds!")
                frame_count = 0
            continue
        
        try:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                print("[video_feed] Failed to encode frame")
                time.sleep(0.05)
                continue
            
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                   b'\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"[video_feed] Error encoding frame: {e}")
            time.sleep(0.05)
            continue
        
        time.sleep(1/30)  # ~30 FPS
@app.get('/video_feed')
def video_feed():
    """Stream processed video feed."""
    print("[video_feed] Client connected, starting stream...")
    return StreamingResponse(generate_mjpeg_stream(), media_type='multipart/x-mixed-replace; boundary=frame')

# ===== HEALTH CHECK =====
@app.get('/health')
def health():
    return {'status': 'ok', 'daemon': 'running'}