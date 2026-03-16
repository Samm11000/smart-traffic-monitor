from flask import Flask, request, jsonify
import csv
import os

# ── config ───────────────────────────────────────────────
LOG_FILE = "logs/traffic_log.csv"
# ─────────────────────────────────────────────────────────

app = Flask(__name__)

# create logs folder and CSV with headers if not exists
os.makedirs("logs", exist_ok=True)
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "frame", "vehicle_count", "density"])
    print(f"[FOG] Created log file: {LOG_FILE}")


def classify_density(count):
    """Rule-based traffic density classification."""
    if count <= 5:
        return "Low"
    elif count <= 15:
        return "Medium"
    else:
        return "High"


@app.route("/receive", methods=["POST"])
def receive():
    """Receive vehicle count from Edge layer."""
    data      = request.get_json()

    count     = data.get("vehicle_count", 0)
    frame     = data.get("frame", 0)
    timestamp = data.get("timestamp", "")
    density   = classify_density(count)

    # save to CSV
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, frame, count, density])

    print(f"[FOG] Frame {frame:>5} | Count: {count:>3} | Density: {density}")

    return jsonify({
        "status":  "ok",
        "density": density,
        "frame":   frame,
        "count":   count
    })


@app.route("/data", methods=["GET"])
def get_data():
    """Return all logged data as JSON — used by Streamlit dashboard."""
    rows = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return jsonify(rows)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint — used by GitHub Actions and Docker."""
    total = 0
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            total = sum(1 for _ in f) - 1   # subtract header row
    return jsonify({
        "status":      "fog server running",
        "total_logged": total
    })


@app.route("/reset", methods=["POST"])
def reset():
    """Clear all logs — useful for fresh demo runs."""
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "frame", "vehicle_count", "density"])
    print("[FOG] Log file reset.")
    return jsonify({"status": "log cleared"})


if __name__ == "__main__":
    print("[FOG] Fog server starting on port 5000...")
    print(f"[FOG] Logging to: {LOG_FILE}")
    # host 0.0.0.0 makes it reachable from outside (needed for EC2)
    app.run(host="0.0.0.0", port=5000, debug=False)