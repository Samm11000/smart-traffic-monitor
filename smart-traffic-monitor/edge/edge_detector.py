import cv2
import requests
import time
from ultralytics import YOLO

# ── config ──────────────────────────────────────────────
VIDEO_PATH      = "data/traffic.mp4"
EC2_PUBLIC_IP   = "YOUR_EC2_PUBLIC_IP"          # ← replace this
FOG_URL         = f"http://{EC2_PUBLIC_IP}:5000/receive"
FRAME_SKIP      = 5                              # process every 5th frame
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
# ────────────────────────────────────────────────────────

model = YOLO("yolov8n.pt")
cap   = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
    exit()

frame_num = 0
print(f"[EDGE] Started. Sending data to {FOG_URL}")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[EDGE] Video ended.")
        break

    frame_num += 1

    # ── skip frames to reduce CPU load ──────────────────
    if frame_num % FRAME_SKIP != 0:
        continue

    # ── run YOLO detection ──────────────────────────────
    results = model(frame, verbose=False)   # verbose=False stops console spam
    count   = 0

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        if cls_id in VEHICLE_CLASSES:
            count += 1

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[EDGE] Frame {frame_num} | {count} vehicles | {timestamp}")

    # ── send to Fog server ──────────────────────────────
    try:
        response = requests.post(FOG_URL, json={
            "frame":         frame_num,
            "vehicle_count": count,
            "timestamp":     timestamp
        }, timeout=5)
        fog_reply = response.json()
        print(f"[FOG]  Density → {fog_reply.get('density', '?')}")
    except requests.exceptions.ConnectionError:
        print("[WARN] Fog server not reachable — is EC2 running?")
    except Exception as e:
        print(f"[WARN] POST failed: {e}")

    # ── annotate and display frame ───────────────────────
    annotated = results[0].plot()
    cv2.putText(
        annotated,
        f"Vehicles: {count}",
        (20, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1, (0, 255, 0), 2
    )
    cv2.imshow("Traffic Detection - Edge Layer", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("[EDGE] Quit by user.")
        break

cap.release()
cv2.destroyAllWindows()