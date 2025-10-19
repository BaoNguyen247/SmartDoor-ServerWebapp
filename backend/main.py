from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.api_door import router as door_router


import threading
from starlette.responses import StreamingResponse
import time
import cv2
from .function.camera_daemon import FaceRecognitionWorker, global_processed_frame

print("[main.py] Starting imports...")

try:
    from .api.api_door import router as door_router
    print("[main.py] ✓ api_door imported successfully")
except Exception as e:
    print(f"[main.py] ✗ FAILED to import api_door: {e}")
    import traceback
    traceback.print_exc()
    door_router = None

try:
    from .function.camera_daemon import FaceRecognitionWorker, global_processed_frame
    print("[main.py] ✓ camera_daemon imported successfully")
except Exception as e:
    print(f"[main.py] ✗ FAILED to import camera_daemon: {e}")
    import traceback
    traceback.print_exc()

app = FastAPI()     

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
if door_router:
    app.include_router(door_router)
    print("[main.py] ✓ door_router included")
else:
    print("[main.py] ✗ door_router is None, skipping include")

# Debug: Print all registered routes
print("\n[main.py] Registered routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        print(f"  {route.methods} {route.path}")
print()

def start_daemon_worker(video_source=0):
    """Start the face recognition worker in a background thread."""
    try:
        worker = FaceRecognitionWorker(video_source=video_source)
        worker_thread = threading.Thread(target=worker.run_stream, daemon=True)
        worker_thread.start()
        print("[main.py] ✓ Daemon worker started on port 8000")
        return worker_thread
    except Exception as e:
        print(f"[main.py] ✗ Failed to start daemon worker: {e}")
        import traceback
        traceback.print_exc()
        return None

# Start the daemon on app startup
daemon_thread = start_daemon_worker(video_source=0)
def generate_mjpeg_stream():
    """Generate MJPEG stream from global_processed_frame."""
    from .function import camera_daemon
    
    frame_count = 0
    while True:
        frame = camera_daemon.global_processed_frame
        
        if frame is None:
            time.sleep(0.1)
            frame_count += 1
            if frame_count > 300:
                print("[video_feed] WARNING: No frames received from daemon for 30 seconds!")
                frame_count = 0
            continue
        
        try:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
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
        
        time.sleep(1/30)

@app.get('/video_feed')
def video_feed():
    """Stream processed video feed."""
    print("[video_feed] Client connected, starting stream...")
    return StreamingResponse(generate_mjpeg_stream(), media_type='multipart/x-mixed-replace; boundary=frame')

# ===== HEALTH CHECK =====
@app.get('/health')
def health():
    return {'status': 'ok', 'daemon': 'running'}