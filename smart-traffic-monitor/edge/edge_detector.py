import cv2
import requests
import time
from ultralytics import YOLO

# ── config ──────────────────────────────────────────────────────────────────
VIDEO_PATH      = "data/traffic.mp4"
EC2_PUBLIC_IP   = "127.0.0.1"        # ← change this later when EC2 is ready
FOG_URL         = f"http://{EC2_PUBLIC_IP}:5000/receive"
FRAME_SKIP      = 5                            # process every 5th frame only
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
# ────────────────────────────────────────────────────────────────────────────

def detect_vehicles(results):
    """Count only vehicle-class detections from YOLO results."""
    count = 0
    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        if cls_id in VEHICLE_CLASSES:
            count += 1
    return count

def send_to_fog(frame_num, count, timestamp):
    """Send detection data to Fog server via HTTP POST."""
    try:
        response = requests.post(FOG_URL, json={
            "frame":         frame_num,
            "vehicle_count": count,
            "timestamp":     timestamp
        }, timeout=5)
        density = response.json().get("density", "?")
        print(f"[FOG]  Reply → density: {density}")
    except requests.exceptions.ConnectionError:
        print("[WARN] Fog server not reachable — running in local mode")
    except Exception as e:
        print(f"[WARN] POST failed: {e}")

def run_edge():
    model = YOLO("yolov8n.pt")
    cap   = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
        return

    frame_num = 0
    print(f"[EDGE] Started — video: {VIDEO_PATH}")
    print(f"[EDGE] Sending to: {FOG_URL}")
    print("[EDGE] Press Q in the video window to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[EDGE] Video finished.")
            break

        frame_num += 1

        # skip frames to keep CPU light
        if frame_num % FRAME_SKIP != 0:
            continue

        # run YOLO
        results    = model(frame, verbose=False)
        count      = detect_vehicles(results)
        timestamp  = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[EDGE] Frame {frame_num:>5} | Vehicles: {count:>3} | {timestamp}")

        # send to fog
        send_to_fog(frame_num, count, timestamp)

        # draw on frame and show
        annotated = results[0].plot()
        cv2.putText(
            annotated,
            f"Vehicles: {count}",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (0, 255, 0), 2
        )
        cv2.putText(
            annotated,
            f"Frame: {frame_num}",
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (255, 255, 0), 2
        )
        cv2.imshow("Traffic Detection — Edge Layer", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[EDGE] Stopped by user.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_edge()