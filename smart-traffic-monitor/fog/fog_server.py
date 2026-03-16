from flask import Flask, request, jsonify, send_file
import csv, os, cv2, time, threading, base64
from ultralytics import YOLO

# ── config ───────────────────────────────────────────────
DATA_CSV        = "logs/traffic_log.csv"    # live data — wiped every run
RESULTS_LOG     = "logs/results_log.csv"    # one row per run — permanent
ANNOTATED_VIDEO = "data/annotated_output.mp4"  # output video — replaced every run
FRAME_SKIP      = 5
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
# ─────────────────────────────────────────────────────────

app = Flask(__name__)
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# ── shared state (RAM only — resets on server restart) ────
state = {
    "processing":      False,
    "done":            False,
    "progress":        0,
    "total_frames":    0,
    "processed":       0,
    "current_count":   0,
    "current_density": "—",
    "frame_b64":       None,
    "run_start":       None,
    "video_name":      None,
    "video_ready":     False,
}


# ── helpers ───────────────────────────────────────────────

def reset_data_csv():
    """Wipe live CSV — called at start of every new detection run."""
    with open(DATA_CSV, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp", "frame", "vehicle_count", "density"])


def write_results_log(video_name, processed, duration_sec, peak, avg, density_counts):
    """Append one summary row to permanent results log after each completed run."""
    if not os.path.exists(RESULTS_LOG):
        with open(RESULTS_LOG, "w", newline="") as f:
            csv.writer(f).writerow([
                "run_time", "video_name", "duration_sec",
                "frames_analyzed", "peak_count", "avg_count",
                "low_frames", "medium_frames", "high_frames"
            ])
    with open(RESULTS_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            video_name,
            round(duration_sec, 1),
            processed,
            peak,
            round(avg, 1),
            density_counts.get("Low", 0),
            density_counts.get("Medium", 0),
            density_counts.get("High", 0),
        ])


def classify_density(count):
    if count <= 5:
        return "Low"
    elif count <= 15:
        return "Medium"
    else:
        return "High"


def frame_to_b64(frame_bgr):
    """Convert annotated BGR frame to base64 JPEG for dashboard display."""
    _, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buf).decode()


def draw_overlay(frame, count, density, frame_num):
    """Burn detection info overlay onto frame."""
    h, w = frame.shape[:2]
    color_map = {
        "Low":    (136, 255, 0),
        "Medium": (0,   170, 255),
        "High":   (55,   51, 255),
    }
    accent = color_map.get(density, (255, 255, 255))

    # semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 70), (10, 10, 20), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # title
    cv2.putText(frame, "TRAFFIC AI",
                (16, 28), cv2.FONT_HERSHEY_DUPLEX, 0.7,
                (255, 255, 255), 1, cv2.LINE_AA)

    # vehicle count
    cv2.putText(frame, f"VEHICLES: {count}",
                (16, 56), cv2.FONT_HERSHEY_DUPLEX, 0.65,
                accent, 2, cv2.LINE_AA)

    # density badge top right
    badge = f"[ {density.upper()} TRAFFIC ]"
    tsz   = cv2.getTextSize(badge, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)[0]
    cv2.putText(frame, badge,
                (w - tsz[0] - 16, 38), cv2.FONT_HERSHEY_DUPLEX, 0.6,
                accent, 1, cv2.LINE_AA)

    # frame number bottom right of bar
    cv2.putText(frame, f"FRAME {frame_num}",
                (w - 130, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (100, 100, 120), 1, cv2.LINE_AA)

    # colour bar at bottom
    cv2.rectangle(frame, (0, h - 5), (w, h), accent, -1)

    return frame


# ── core detection loop ───────────────────────────────────

def run_yolo(video_path, video_name):
    """
    Full YOLO detection pipeline.
    Runs in a background thread — updates shared state dict.
    Writes annotated video, live CSV, and results log.
    Deletes input video when done.
    """
    global state

    state.update({
        "processing":      True,
        "done":            False,
        "progress":        0,
        "processed":       0,
        "current_count":   0,
        "current_density": "—",
        "frame_b64":       None,
        "run_start":       time.time(),
        "video_name":      video_name,
        "video_ready":     False,
    })

    reset_data_csv()

    # delete old annotated output if it exists
    if os.path.exists(ANNOTATED_VIDEO):
        os.remove(ANNOTATED_VIDEO)
        print("[FOG] Deleted old annotated video")

    print(f"[FOG] Loading YOLOv8n...")
    model = YOLO("yolov8n.pt")

    print(f"[FOG] Opening video: {video_path}")
    cap   = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0
    state["total_frames"] = total
    print(f"[FOG] Total frames: {total} | FPS: {fps:.1f}")

    writer         = None
    frame_num      = 0
    all_counts     = []
    density_counts = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1
        state["progress"] = int((frame_num / total) * 100) if total > 0 else 0

        if frame_num % FRAME_SKIP != 0:
            continue

        # run YOLO detection
        results   = model(frame, verbose=False)
        count     = sum(1 for b in results[0].boxes if int(b.cls[0]) in VEHICLE_CLASSES)
        density   = classify_density(count)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # write row to live CSV
        with open(DATA_CSV, "a", newline="") as f:
            csv.writer(f).writerow([timestamp, frame_num, count, density])

        # track stats for results log
        all_counts.append(count)
        density_counts[density] = density_counts.get(density, 0) + 1

        # annotate frame — YOLO boxes + our overlay
        annotated = results[0].plot()
        annotated = draw_overlay(annotated, count, density, frame_num)

        # init video writer on first processed frame
        if writer is None:
            h, w   = annotated.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            # use original fps so playback speed is smooth and natural
            writer = cv2.VideoWriter(ANNOTATED_VIDEO, fourcc, fps, (w, h))
            print(f"[FOG] VideoWriter initialised: {w}x{h} @ {fps}fps")

        # write each annotated frame fps/FRAME_SKIP times
        # this fills the "skipped" frames so video plays at correct speed
        repeat = max(1, round(fps / (fps / FRAME_SKIP)))
        for _ in range(repeat):
            writer.write(annotated)

        # update dashboard state
        state["frame_b64"]       = frame_to_b64(annotated)
        state["current_count"]   = count
        state["current_density"] = density
        state["processed"]      += 1

        print(f"[FOG] Frame {frame_num:>5} | Vehicles: {count:>3} | Density: {density}")

    cap.release()

    if writer:
        writer.release()
        state["video_ready"] = True
        print(f"[FOG] Annotated video saved: {ANNOTATED_VIDEO}")

    # delete input video — no longer needed
    try:
        os.remove(video_path)
        print(f"[FOG] Deleted input video: {video_path}")
    except Exception as e:
        print(f"[FOG] Could not delete input video: {e}")

    # write summary row to permanent results log
    duration = time.time() - state["run_start"]
    write_results_log(
        video_name     = video_name,
        processed      = state["processed"],
        duration_sec   = duration,
        peak           = max(all_counts) if all_counts else 0,
        avg            = sum(all_counts) / len(all_counts) if all_counts else 0,
        density_counts = density_counts,
    )

    state["processing"] = False
    state["done"]       = True
    state["progress"]   = 100
    print(f"[FOG] Run complete — {state['processed']} frames in {duration:.1f}s")


# ── routes ────────────────────────────────────────────────

@app.route("/upload_video", methods=["POST"])
def upload_video():
    """Receive video upload from dashboard and start YOLO detection."""
    if "video" not in request.files:
        return jsonify({"error": "no video file in request"}), 400

    if state["processing"]:
        return jsonify({"error": "already processing a video — wait or reset"}), 409

    f = request.files["video"]

    # check file size — reject over 200MB
    f.seek(0, 2)
    size_mb = f.tell() / 1024 / 1024
    f.seek(0)
    if size_mb > 200:
        return jsonify({"error": f"File too large ({size_mb:.0f}MB). Max allowed: 200MB."}), 413

    # delete any old videos in data/ before saving new one
    for old_file in os.listdir("data"):
        if old_file.endswith((".mp4", ".avi", ".mov")):
            try:
                os.remove(f"data/{old_file}")
                print(f"[FOG] Deleted old video: {old_file}")
            except:
                pass

    name      = f.filename
    save_path = f"data/{name}"
    f.save(save_path)
    print(f"[FOG] Saved new video: {save_path} ({size_mb:.1f}MB)")

    # start detection in background thread
    thread = threading.Thread(target=run_yolo, args=(save_path, name), daemon=True)
    thread.start()

    return jsonify({"status": "started", "file": name, "size_mb": round(size_mb, 1)})


@app.route("/status", methods=["GET"])
def status():
    """Current processing state + latest annotated frame for dashboard."""
    return jsonify({
        "processing":      state["processing"],
        "done":            state["done"],
        "progress":        state["progress"],
        "total_frames":    state["total_frames"],
        "processed":       state["processed"],
        "current_count":   state["current_count"],
        "current_density": state["current_density"],
        "frame_b64":       state["frame_b64"],
        "video_name":      state["video_name"],
        "video_ready":     state["video_ready"],
    })


@app.route("/data", methods=["GET"])
def get_data():
    """Return current run's CSV rows as JSON for dashboard charts."""
    rows = []
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, "r") as f:
            rows = list(csv.DictReader(f))
    return jsonify(rows)


@app.route("/results", methods=["GET"])
def get_results():
    """Return all past run summaries from permanent results log."""
    rows = []
    if os.path.exists(RESULTS_LOG):
        with open(RESULTS_LOG, "r") as f:
            rows = list(csv.DictReader(f))
    return jsonify(rows)


@app.route("/annotated_video", methods=["GET"])
def annotated_video():
    """Serve the annotated output video as a downloadable file."""
    abs_path = os.path.abspath(ANNOTATED_VIDEO)
    if not os.path.exists(abs_path):
        return jsonify({"error": "No annotated video available yet. Run detection first."}), 404
    if not state["video_ready"]:
        return jsonify({"error": "Video is still being written. Try again shortly."}), 425
    return send_file(
        abs_path,
        mimetype="video/mp4",
        as_attachment=True,
        download_name="traffic_annotated.mp4"
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check — used by dashboard sidebar and Docker healthcheck."""
    csv_rows = 0
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, "r") as f:
            csv_rows = max(sum(1 for _ in f) - 1, 0)
    return jsonify({
        "status":       "fog server running",
        "csv_rows":     csv_rows,
        "processing":   state["processing"],
        "done":         state["done"],
        "video_ready":  state["video_ready"],
    })


@app.route("/disk", methods=["GET"])
def disk_usage():
    """Disk usage info — useful for monitoring EC2 space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    videos = [f for f in os.listdir("data") if f.endswith((".mp4", ".avi", ".mov"))]
    csv_rows = 0
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV) as f:
            csv_rows = max(sum(1 for _ in f) - 1, 0)
    return jsonify({
        "disk_total_gb":  round(total / 1e9, 1),
        "disk_used_gb":   round(used  / 1e9, 1),
        "disk_free_gb":   round(free  / 1e9, 1),
        "disk_used_pct":  round((used / total) * 100, 1),
        "videos_on_disk": videos,
        "csv_rows":       csv_rows,
    })


@app.route("/reset", methods=["POST"])
def reset():
    """
    Reset state for a new run.
    Wipes live CSV and annotated video.
    Does NOT touch the permanent results log.
    """
    reset_data_csv()

    if os.path.exists(ANNOTATED_VIDEO):
        try:
            os.remove(ANNOTATED_VIDEO)
            print("[FOG] Deleted annotated video on reset")
        except:
            pass

    state.update({
        "processing":      False,
        "done":            False,
        "progress":        0,
        "processed":       0,
        "total_frames":    0,
        "frame_b64":       None,
        "current_count":   0,
        "current_density": "—",
        "run_start":       None,
        "video_name":      None,
        "video_ready":     False,
    })
    print("[FOG] Full reset complete.")
    return jsonify({"status": "reset ok"})


@app.route("/receive", methods=["POST"])
def receive():
    """
    Legacy manual POST endpoint.
    Kept for backward compatibility — accepts raw vehicle count POSTs.
    """
    data    = request.get_json()
    count   = data.get("vehicle_count", 0)
    frame   = data.get("frame", 0)
    ts      = data.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
    density = classify_density(count)
    with open(DATA_CSV, "a", newline="") as f:
        csv.writer(f).writerow([ts, frame, count, density])
    print(f"[FOG] Manual POST | Frame {frame} | Count: {count} | Density: {density}")
    return jsonify({"status": "ok", "density": density})


if __name__ == "__main__":
    reset_data_csv()
    print("[FOG] ─────────────────────────────────────")
    print("[FOG] Fog server starting on port 5000")
    print(f"[FOG] Live CSV    : {DATA_CSV}")
    print(f"[FOG] Results log : {RESULTS_LOG}")
    print(f"[FOG] Output video: {ANNOTATED_VIDEO}")
    print("[FOG] ─────────────────────────────────────")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)