import streamlit as st
import requests
import pandas as pd
import time
import os

# ── config ───────────────────────────────────────────────
FOG_HOST = os.getenv("FOG_HOST", "localhost")
FOG_URL  = f"http://{FOG_HOST}:5000"
# ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TrafficAI",
    page_icon="🚦",
    layout="wide"
)

# ── CSS — dark industrial theme ───────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Barlow:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
}
.stApp { background: #0a0a0f; }
h1 { font-family: 'Space Mono', monospace !important; letter-spacing: -1px; }

[data-testid="metric-container"] {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 0.2s;
}
[data-testid="metric-container"]:hover { border-color: #00ff88; }
[data-testid="stMetricLabel"] {
    color: #666 !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
[data-testid="stMetricValue"] {
    color: #fff !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 26px !important;
}

[data-testid="stSidebar"] {
    background: #0d0d14 !important;
    border-right: 1px solid #1e1e2e;
}

.stButton > button {
    background: linear-gradient(135deg, #00ff88, #00ccaa) !important;
    color: #000 !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px !important;
    font-size: 12px !important;
    letter-spacing: 1px;
    width: 100%;
}
.stButton > button:disabled {
    background: #1e1e2e !important;
    color: #444 !important;
}

[data-testid="stFileUploader"] {
    background: #12121a;
    border: 1px dashed #2a2a3e;
    border-radius: 12px;
}

.stProgress > div > div {
    background: linear-gradient(90deg, #00ff88, #00ccaa) !important;
}

hr { border-color: #1e1e2e !important; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2a2a3e; border-radius: 4px; }

.sl {
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #333;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1a1a28;
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.2} }
.ld {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 1.5s infinite;
}
.dg { background: #00ff88; }
.dr { background: #ff3355; }
.dz { background: #444; animation: none; }

.density-badge {
    display: inline-block;
    padding: 8px 22px;
    border-radius: 100px;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}
.badge-Low    { background: rgba(0,255,136,0.08);   color: #00ff88; border: 1px solid rgba(0,255,136,0.4); }
.badge-Medium { background: rgba(255,170,0,0.08);   color: #ffaa00; border: 1px solid rgba(255,170,0,0.4); }
.badge-High   { background: rgba(255,51,85,0.08);   color: #ff3355; border: 1px solid rgba(255,51,85,0.4); }
.badge-none   { background: rgba(100,100,100,0.08); color: #555;    border: 1px solid #333; }

.bar-track {
    background: #1a1a28;
    border-radius: 4px;
    height: 5px;
    overflow: hidden;
    margin-top: 4px;
}
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }

@keyframes spin { to { transform: rotate(360deg); } }

.info-card {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    padding: 14px 16px;
}
.info-card-title {
    font-size: 9px;
    color: #333;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 8px;
}
.info-card-body {
    font-size: 12px;
    color: #555;
    line-height: 2;
}
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────

def get_status():
    try:
        return requests.get(f"{FOG_URL}/status", timeout=3).json()
    except:
        return {}

def get_data():
    try:
        return pd.DataFrame(requests.get(f"{FOG_URL}/data", timeout=3).json())
    except:
        return pd.DataFrame()

def get_results():
    try:
        return pd.DataFrame(requests.get(f"{FOG_URL}/results", timeout=3).json())
    except:
        return pd.DataFrame()

def upload_and_start(file_bytes, filename):
    try:
        res = requests.post(
            f"{FOG_URL}/upload_video",
            files={"video": (filename, file_bytes, "video/mp4")},
            timeout=60
        )
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def reset_all():
    try:
        requests.post(f"{FOG_URL}/reset", timeout=3)
    except:
        pass

def fetch_annotated_video():
    """Download annotated video bytes from Fog server."""
    try:
        res = requests.get(f"{FOG_URL}/annotated_video", timeout=120, stream=True)
        if res.status_code == 200:
            return res.content, None
        else:
            try:
                return None, res.json().get("error", "Unknown error")
            except Exception:
                return None, f"HTTP {res.status_code}: {res.text[:200]}"
    except Exception as e:
        return None, str(e)


# ── fetch live state from Fog ─────────────────────────────
status        = get_status()
is_processing = status.get("processing", False)
is_done       = status.get("done", False)
progress      = status.get("progress", 0)
processed     = status.get("processed", 0)
total_frames  = status.get("total_frames", 0)
cur_count     = status.get("current_count", 0)
cur_density   = status.get("current_density", "—")
frame_b64     = status.get("frame_b64", None)
video_name    = status.get("video_name", None)
video_ready   = status.get("video_ready", False)


# ── HEADER ────────────────────────────────────────────────
col_t, col_s = st.columns([3, 1])

with col_t:
    st.markdown("# TRAFFIC AI")
    st.markdown(
        "<p style='color:#333;font-family:Space Mono,monospace;"
        "font-size:10px;margin-top:-14px;letter-spacing:2px'>"
        "SMART DENSITY MONITORING // EDGE → FOG → CLOUD</p>",
        unsafe_allow_html=True
    )

with col_s:
    if is_processing:
        st.markdown(
            "<div style='text-align:right;padding-top:22px'>"
            "<span class='ld dg'></span>"
            "<span style='font-family:Space Mono,monospace;font-size:11px;color:#00ff88'>PROCESSING</span>"
            "</div>", unsafe_allow_html=True)
    elif is_done:
        st.markdown(
            "<div style='text-align:right;padding-top:22px'>"
            "<span style='font-family:Space Mono,monospace;font-size:11px;color:#555'>COMPLETE</span>"
            "</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='text-align:right;padding-top:22px'>"
            "<span class='ld dz'></span>"
            "<span style='font-family:Space Mono,monospace;font-size:11px;color:#333'>STANDBY</span>"
            "</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin:6px 0 20px'/>", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────
with st.sidebar:

    st.markdown("<div class='sl'>Video Input</div>", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload traffic video",
        type=["mp4", "avi", "mov"],
        label_visibility="collapsed",
        disabled=is_processing
    )

    if uploaded:
        size_mb = round(uploaded.size / 1024 / 1024, 1)
        st.markdown(f"""
        <div style='background:#12121a;border:1px solid #1e1e2e;
                    border-radius:8px;padding:10px 12px;margin:8px 0'>
            <div style='font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px'>Ready</div>
            <div style='font-family:Space Mono,monospace;font-size:11px;
                        color:#ccc;margin-top:3px;word-break:break-all'>{uploaded.name}</div>
            <div style='font-size:10px;color:#333;margin-top:3px'>{size_mb} MB</div>
        </div>""", unsafe_allow_html=True)

        if st.button("START DETECTION", disabled=is_processing):
            with st.spinner("Uploading to Fog server..."):
                result = upload_and_start(uploaded.read(), uploaded.name)
            if "error" in result:
                st.error(f"Failed: {result['error']}")
            else:
                st.success("Detection started!")
                time.sleep(0.5)
                st.rerun()

    # progress bar
    if is_processing or is_done:
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown("<div class='sl'>Progress</div>", unsafe_allow_html=True)
        st.progress(progress / 100)
        st.markdown(
            f"<div style='font-family:Space Mono,monospace;font-size:10px;"
            f"color:#444;text-align:center;margin-top:4px'>"
            f"{progress}%  ·  {processed} frames analyzed</div>",
            unsafe_allow_html=True
        )
        if is_done:
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("RESET / NEW VIDEO"):
                reset_all()
                st.rerun()

    # detection config
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("<div class='sl'>Detection Config</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:11px;color:#444;line-height:2.2'>
        Model &nbsp;&nbsp;&nbsp;&nbsp; <span style='color:#666'>YOLOv8n</span><br/>
        Skip &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span style='color:#666'>Every 5th frame</span><br/>
        Classes &nbsp;&nbsp; <span style='color:#666'>Car · Bus · Truck · Bike</span><br/>
        <span style='color:#00ff8866'>●</span> Low &nbsp;&nbsp;&nbsp;&nbsp; <span style='color:#444'>0 – 5 vehicles</span><br/>
        <span style='color:#ffaa0066'>●</span> Medium &nbsp; <span style='color:#444'>6 – 15 vehicles</span><br/>
        <span style='color:#ff335566'>●</span> High &nbsp;&nbsp;&nbsp; <span style='color:#444'>16+ vehicles</span>
    </div>""", unsafe_allow_html=True)

    # system health
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("<div class='sl'>System</div>", unsafe_allow_html=True)
    try:
        h = requests.get(f"{FOG_URL}/health", timeout=2).json()
        st.markdown(
            f"<span class='ld dg'></span>"
            f"<span style='font-size:11px;color:#00ff88'>Fog online</span>"
            f"<br/><span style='font-size:10px;color:#333;margin-left:13px'>"
            f"{h.get('csv_rows', 0)} rows in CSV</span>",
            unsafe_allow_html=True)
    except:
        st.markdown(
            "<span class='ld dr'></span>"
            "<span style='font-size:11px;color:#ff3355'>Fog offline</span><br/>"
            "<span style='font-size:10px;color:#333;margin-left:13px'>"
            "Run: python fog/fog_server.py</span>",
            unsafe_allow_html=True)


# ── MAIN CONTENT ──────────────────────────────────────────
df       = get_data()
has_data = not df.empty

# ── EMPTY STATE ───────────────────────────────────────────
if not is_processing and not is_done and not has_data:
    st.markdown("""
    <div style='text-align:center;padding:90px 0'>
        <div style='font-size:52px;margin-bottom:18px'>🚦</div>
        <div style='font-family:Space Mono,monospace;font-size:16px;
                    color:#ccc;margin-bottom:10px'>No video loaded</div>
        <div style='font-size:13px;color:#333;line-height:2;max-width:360px;margin:0 auto'>
            Upload any MP4 traffic footage from the sidebar.<br/>
            YOLOv8 detects vehicles frame by frame on this machine.<br/>
            Results stream live to this dashboard.
        </div>
    </div>""", unsafe_allow_html=True)

else:

    # ── LIVE VIDEO FEED + STATS ───────────────────────────
    vid_col, stat_col = st.columns([3, 2])

    with vid_col:
        st.markdown("<div class='sl'>Live Detection Feed</div>", unsafe_allow_html=True)

        if frame_b64:
            st.markdown(f"""
            <div style='border:1px solid #1e1e2e;border-radius:10px;
                        overflow:hidden;background:#000'>
                <img src='data:image/jpeg;base64,{frame_b64}'
                     style='width:100%;display:block'/>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='border:1px solid #1a1a28;border-radius:10px;background:#0d0d14;
                        height:280px;display:flex;align-items:center;
                        justify-content:center;flex-direction:column;gap:14px'>
                <div style='width:30px;height:30px;border:2px solid #00ff88;
                            border-top-color:transparent;border-radius:50%;
                            animation:spin 1s linear infinite'></div>
                <span style='font-family:Space Mono,monospace;font-size:9px;
                             color:#333;letter-spacing:3px'>LOADING MODEL...</span>
            </div>""", unsafe_allow_html=True)

    with stat_col:
        st.markdown("<div class='sl'>Live Stats</div>", unsafe_allow_html=True)

        badge_cls = f"badge-{cur_density}" if cur_density in ["Low","Medium","High"] else "badge-none"
        st.markdown(
            f"<div style='margin-bottom:18px'>"
            f"<span class='density-badge {badge_cls}'>{cur_density} Traffic</span>"
            f"</div>", unsafe_allow_html=True)

        m1, m2 = st.columns(2)
        m1.metric("Vehicles Now", cur_count)
        m2.metric("Frames Done",  processed)

        if has_data:
            df["vehicle_count"] = pd.to_numeric(df["vehicle_count"])
            m3, m4 = st.columns(2)
            m3.metric("Avg Vehicles", round(df["vehicle_count"].mean(), 1))
            m4.metric("Peak Count",   int(df["vehicle_count"].max()))

            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("<div class='sl'>Density Breakdown</div>", unsafe_allow_html=True)

            counts = df["density"].value_counts()
            total  = len(df)

            for label, color in [("High","#ff3355"),("Medium","#ffaa00"),("Low","#00ff88")]:
                n   = counts.get(label, 0)
                pct = int((n / total) * 100) if total else 0
                st.markdown(f"""
                <div style='margin-bottom:12px'>
                    <div style='display:flex;justify-content:space-between;
                                font-size:11px;margin-bottom:5px'>
                        <span style='color:{color};font-family:Space Mono,monospace;
                                     letter-spacing:1px'>{label}</span>
                        <span style='color:#333'>{n} frames · {pct}%</span>
                    </div>
                    <div class='bar-track'>
                        <div class='bar-fill' style='background:{color};width:{pct}%'></div>
                    </div>
                </div>""", unsafe_allow_html=True)

    # ── CHARTS ────────────────────────────────────────────
    if has_data:
        df["frame"] = pd.to_numeric(df["frame"])

        st.markdown("<hr style='margin:22px 0'/>", unsafe_allow_html=True)

        cl, cr = st.columns(2)
        with cl:
            st.markdown("<div class='sl'>Vehicle Count Over Time</div>", unsafe_allow_html=True)
            st.line_chart(
                df.set_index("frame")[["vehicle_count"]],
                color=["#00ff88"],
                height=200
            )
        with cr:
            st.markdown("<div class='sl'>Density Distribution</div>", unsafe_allow_html=True)
            dist = df["density"].value_counts().reset_index()
            dist.columns = ["density", "count"]
            st.bar_chart(dist.set_index("density"), color=["#00ccaa"], height=200)

        # ── CURRENT RUN LOG + CSV EXPORT ──────────────────
        st.markdown("<hr style='margin:22px 0'/>", unsafe_allow_html=True)
        st.markdown("<div class='sl'>Current Run — Detection Log</div>", unsafe_allow_html=True)

        tbl_col, dl_col = st.columns([4, 1])

        with tbl_col:
            show = df[["timestamp","frame","vehicle_count","density"]] \
                     .tail(15).sort_index(ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True)

        with dl_col:
            st.markdown("<br/><br/>", unsafe_allow_html=True)
            st.download_button(
                "EXPORT CSV",
                data=df.to_csv(index=False),
                file_name="traffic_run.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.markdown(f"""
            <div style='background:#12121a;border:1px solid #1e1e2e;border-radius:8px;
                        padding:14px;text-align:center;margin-top:8px'>
                <div style='font-size:9px;color:#333;text-transform:uppercase;
                            letter-spacing:2px'>Total detected</div>
                <div style='font-family:Space Mono,monospace;font-size:30px;
                            color:#00ff88;margin-top:6px;line-height:1'>
                    {int(df["vehicle_count"].sum())}
                </div>
                <div style='font-size:9px;color:#333;margin-top:4px'>vehicles</div>
            </div>""", unsafe_allow_html=True)

    # ── DOWNLOAD ANNOTATED VIDEO — only shown after run completes ──
    if is_done:
        st.markdown("<hr style='margin:22px 0'/>", unsafe_allow_html=True)
        st.markdown("<div class='sl'>Download Annotated Video</div>", unsafe_allow_html=True)

        vid_dl_col, vid_info_col = st.columns([1, 3])

        with vid_dl_col:
            if video_ready:
                # fetch video bytes for download button
                with st.spinner("Preparing video..."):
                    video_bytes, error = fetch_annotated_video()

                if video_bytes:
                    output_filename = f"traffic_annotated_{video_name or 'output'}.mp4"
                    st.download_button(
                        label="DOWNLOAD VIDEO",
                        data=video_bytes,
                        file_name=output_filename,
                        mime="video/mp4",
                        use_container_width=True
                    )
                    size_mb = round(len(video_bytes) / 1024 / 1024, 1)
                    st.markdown(
                        f"<div style='font-size:10px;color:#333;text-align:center;margin-top:6px'>"
                        f"{size_mb} MB · mp4</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.error(f"Error: {error}")
            else:
                st.markdown("""
                <div style='background:#12121a;border:1px solid #1e1e2e;
                            border-radius:8px;padding:14px;text-align:center'>
                    <div style='width:20px;height:20px;border:2px solid #00ff88;
                                border-top-color:transparent;border-radius:50%;
                                animation:spin 1s linear infinite;margin:0 auto 8px'></div>
                    <div style='font-size:10px;color:#333;letter-spacing:2px'>
                        WRITING VIDEO...
                    </div>
                </div>""", unsafe_allow_html=True)

        with vid_info_col:
            st.markdown(f"""
            <div class='info-card'>
                <div class='info-card-title'>What's in this video</div>
                <div class='info-card-body'>
                    YOLO bounding boxes on every detected vehicle<br/>
                    Density badge burned into top-right corner<br/>
                    Vehicle count overlay on every frame<br/>
                    Colour-coded border — green / orange / red by density<br/>
                    Smooth playback at original video FPS
                </div>
            </div>""", unsafe_allow_html=True)

    # ── RESULTS LOG — only shown after run completes ──────
    if is_done:
        results_df = get_results()

        if not results_df.empty:
            st.markdown("<hr style='margin:22px 0'/>", unsafe_allow_html=True)
            st.markdown("<div class='sl'>Results Log — All Past Runs</div>", unsafe_allow_html=True)

            results_df["duration_sec"]    = pd.to_numeric(results_df["duration_sec"])
            results_df["peak_count"]      = pd.to_numeric(results_df["peak_count"])
            results_df["avg_count"]       = pd.to_numeric(results_df["avg_count"])
            results_df["frames_analyzed"] = pd.to_numeric(results_df["frames_analyzed"])

            rt_col, rd_col = st.columns([4, 1])

            with rt_col:
                st.dataframe(
                    results_df[[
                        "run_time", "video_name", "duration_sec",
                        "frames_analyzed", "peak_count", "avg_count",
                        "low_frames", "medium_frames", "high_frames"
                    ]].sort_index(ascending=False),
                    use_container_width=True,
                    hide_index=True
                )

            with rd_col:
                st.markdown("<br/><br/>", unsafe_allow_html=True)
                st.download_button(
                    "EXPORT LOG",
                    data=results_df.to_csv(index=False),
                    file_name="results_log.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                st.markdown(f"""
                <div style='background:#12121a;border:1px solid #1e1e2e;border-radius:8px;
                            padding:14px;text-align:center;margin-top:8px'>
                    <div style='font-size:9px;color:#333;text-transform:uppercase;
                                letter-spacing:2px'>Total runs</div>
                    <div style='font-family:Space Mono,monospace;font-size:30px;
                                color:#ffaa00;margin-top:6px;line-height:1'>
                        {len(results_df)}
                    </div>
                </div>""", unsafe_allow_html=True)


# ── AUTO REFRESH ──────────────────────────────────────────
if is_processing:
    time.sleep(1.5)
    st.rerun()
elif has_data and not is_done:
    time.sleep(3)
    st.rerun()
# keep refreshing for a few seconds after done to catch video_ready update
elif is_done and not video_ready:
    time.sleep(1)
    st.rerun()