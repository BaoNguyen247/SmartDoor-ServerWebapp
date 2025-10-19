import cv2
import os
import numpy as np
import pickle
from typing import Dict, Optional


def add_face(name: str,
             camera_index: int = 0,
             video_source: Optional[str] = None,
             output_dir: str = None,
             num_images: int = 100,
             frame_interval: int = 10,
             display: bool = True) -> Dict[int, str]:
    """Capture face images for a new person, save them, and retrain LBPH model.

    Args:
        name: Person name (used as folder name under output_dir/faces).
        camera_index: Index of the camera to use (default 0).
        output_dir: Base data directory. If None, it uses the `data` folder next to this file.
        num_images: Number of face images to collect.
        frame_interval: Save 1 image every `frame_interval` frames when a face is detected.
        display: If True, show a preview window while collecting; set False to run headless.

    Returns:
        label_map: dictionary mapping label_id -> person name

    Raises:
        RuntimeError: if camera cannot be opened or no faces were collected.
    """

    base_dir = output_dir or os.path.join(os.path.dirname(__file__), 'data')
    faces_dir = os.path.join(base_dir, 'faces')
    os.makedirs(faces_dir, exist_ok=True)

    # Cascade path (relative to this file)
    cascade_path = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
    if not os.path.exists(cascade_path):
        raise FileNotFoundError(f"Cascade file not found: {cascade_path}")

    # Determine video source: prefer explicit video_source (URL or device path),
    # otherwise fall back to camera_index.
    cap_source = video_source if video_source is not None else camera_index
    video = cv2.VideoCapture(cap_source)
    if not video.isOpened():
        video.release()
        raise RuntimeError(f"Cannot open video source: {cap_source}")

    if display:
        cv2.namedWindow("Thu thap khuon mat", cv2.WINDOW_NORMAL)

    facedetect = cv2.CascadeClassifier(cascade_path)

    person_path = os.path.join(faces_dir, name)
    os.makedirs(person_path, exist_ok=True)

    count = 0
    frame_count = 0

    try:
        while True:
            ret, frame = video.read()
            if not ret:
                # Try to reconnect
                video.release()
                video = cv2.VideoCapture(camera_index)
                if not video.isOpened():
                    raise RuntimeError("Lost connection to camera and cannot reconnect")
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = facedetect.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                if frame_count % frame_interval == 0 and count < num_images:
                    face = gray[y:y+h, x:x+w]
                    # Choose interpolation: INTER_AREA for shrinking, INTER_CUBIC for enlarging
                    oh, ow = face.shape[:2]
                    if ow > 200 or oh > 200:
                        interp = cv2.INTER_AREA
                    else:
                        interp = cv2.INTER_CUBIC
                    face_resized = cv2.resize(face, (200, 200), interpolation=interp)
                    save_path = os.path.join(person_path, f"{count}.jpg")
                    cv2.imwrite(save_path, face_resized)
                    # Debug log to help verify saved image size
                    try:
                        saved_img = cv2.imread(save_path, cv2.IMREAD_GRAYSCALE)
                        sh, sw = saved_img.shape[:2]
                        print(f"[add_face] Saved {save_path} size={sw}x{sh}")
                    except Exception:
                        print(f"[add_face] Saved {save_path}")
                    count += 1
                    count += 1

                frame_count += 1
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, str(count), (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            if display:
                cv2.imshow("Thu thap khuon mat", frame)

            if (display and cv2.waitKey(1) == ord('q')) or count >= num_images:
                break

    finally:
        video.release()
        if display:
            cv2.destroyAllWindows()

    if count == 0:
        raise RuntimeError("No face images were collected.")

    # Train LBPH model
    faces_list, labels = [], []
    label_map = {}
    label_id = 0

    for person in sorted(os.listdir(faces_dir)):
        person_folder = os.path.join(faces_dir, person)
        if not os.path.isdir(person_folder):
            continue
        label_map[label_id] = person
        for image_name in sorted(os.listdir(person_folder)):
            img_path = os.path.join(person_folder, image_name)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            faces_list.append(img)
            labels.append(label_id)
        label_id += 1

    if len(faces_list) == 0:
        raise RuntimeError("No face images available for training.")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces_list, np.array(labels))

    model_path = os.path.join(base_dir, 'lbph_model.yml')
    recognizer.save(model_path)

    label_map_path = os.path.join(base_dir, 'label_map.pkl')
    with open(label_map_path, 'wb') as f:
        pickle.dump(label_map, f)

    return label_map


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Collect face images and train LBPH model')
    parser.add_argument('name', help='Name of the person to add')
    parser.add_argument('--camera', type=int, default=0, help='Camera index')
    parser.add_argument('--images', type=int, default=100, help='Number of images to collect')
    parser.add_argument('--interval', type=int, default=10, help='Frame interval')
    parser.add_argument('--nodisplay', action='store_true', help='Run without showing preview window')
    args = parser.parse_args()

    try:
        mapping = add_face(args.name, camera_index=args.camera, num_images=args.images, frame_interval=args.interval, display=not args.nodisplay)
        print('Training complete. Label map:')
        for k, v in mapping.items():
            print(k, v)
    except Exception as e:
        print('Error:', e)
        raise
