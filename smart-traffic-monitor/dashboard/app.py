import streamlit as st
import requests
import pandas as pd
import time
import os

# ── config ───────────────────────────────────────────────
FOG_HOST = os.getenv("FOG_HOST", "localhost")
FOG_API  = f"http://{FOG_HOST}:5000/data"
REFRESH  = 3   # seconds between dashboard refresh
# ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Traffic Monitor",
    page_icon="🚦",
    layout="wide"
)

st.title("Smart Traffic Density Monitor")
st.caption("Edge (Laptop) → Fog (EC2 Flask) → Cloud (Streamlit Dashboard)")

def get_data():
    try:
        res = requests.get(FOG_API, timeout=3)
        df  = pd.DataFrame(res.json())
        return df
    except:
        return pd.DataFrame()

def density_color(density):
    return {"Low": "green", "Medium": "orange", "High": "red"}.get(density, "gray")

placeholder = st.empty()

while True:
    df = get_data()

    with placeholder.container():

        if df.empty:
            st.warning("Waiting for data from Fog server...")

        else:
            df["vehicle_count"] = pd.to_numeric(df["vehicle_count"])
            df["frame"]         = pd.to_numeric(df["frame"])

            latest  = df.iloc[-1]
            density = latest["density"]
            count   = latest["vehicle_count"]

            # ── top metrics row ──────────────────────────
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Vehicle Count",      count)
            col2.metric("Traffic Density",    density)
            col3.metric("Frames Processed",   len(df))
            col4.metric("Total Vehicles Seen", int(df["vehicle_count"].sum()))

            # ── density status badge ─────────────────────
            color = density_color(density)
            st.markdown(
                f"<h3 style='color:{color}'>● Current Status: {density} Traffic</h3>",
                unsafe_allow_html=True
            )

            st.divider()

            # ── charts row ───────────────────────────────
            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("Vehicle Count Over Time")
                st.line_chart(df.set_index("frame")["vehicle_count"])

            with col_right:
                st.subheader("Density Distribution")
                st.bar_chart(df["density"].value_counts())

            st.divider()

            # ── recent logs table ────────────────────────
            st.subheader("Recent Detections")
            st.dataframe(
                df.tail(10).sort_index(ascending=False),
                use_container_width=True
            )

    time.sleep(REFRESH)