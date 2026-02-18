import streamlit as st
import requests
import pandas as pd
from io import StringIO
from streamlit_lottie import st_lottie
import time
import json
import os
import base64
import re
from datetime import datetime, timedelta
import altair as alt
from pypdf import PdfReader

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="Antsy - Etsy2JTL Secure Scan", layout="wide")

# Sicherheitseinstellungen
UPLOAD_DELAY = 25
STATS_FILE = "antsy_global_stats.json"  # Nur anonyme Summen
TIME_PER_ORDER_MIN = 2.5

# PDF Magic Bytes Validierung
PDF_MAGIC_BYTES = b"%PDF"

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    * { font-family: 'Outfit', sans-serif; }
    
    .stApp { background-color: #0d1117; }
    
    /* Premium Cards */
    .main-card {
        background: linear-gradient(135deg, #1c2128 0%, #161b22 100%);
        padding: 40px;
        border-radius: 24px;
        border: 1px solid rgba(48, 54, 61, 0.7);
        text-align: center;
        margin-top: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    
    /* Stats Dashboard */
    .stats-container {
        display: flex;
        justify-content: space-around;
        gap: 20px;
        margin: 30px 0;
        flex-wrap: wrap;
    }
    
    .stat-card {
        background: rgba(33, 38, 45, 0.6);
        border: 1px solid #30363d;
        border-radius: 18px;
        padding: 20px;
        min-width: 200px;
        flex: 1;
        transition: transform 0.3s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
        border-color: #ff5a1f;
    }
    
    .stat-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ff5a1f;
        margin-bottom: 5px;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Buttons */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #ff5a1f 0%, #ff814d 100%);
        color: white;
        border-radius: 14px;
        border: none;
        padding: 18px 30px;
        font-weight: 600;
        font-size: 1.1rem;
        width: 100%;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    
    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 20px rgba(255, 90, 31, 0.3);
    }
    
    /* History Cards */
    .history-card {
        background: #161b22;
        border-left: 4px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin: 12px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .history-card:hover {
        border-left-color: #ff5a1f;
    }

    .howto-card {
        background: rgba(33, 38, 45, 0.6);
        border: 1px solid #30363d;
        border-radius: 18px;
        padding: 14px;
        margin-bottom: 16px;
    }

    .howto-title {
        font-size: 0.95rem;
        color: #c9d1d9;
        margin: 0 0 10px 0;
        font-weight: 600;
    }

    .howto-thumb {
        width: 100%;
        border-radius: 14px;
        border: 1px solid #30363d;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
        display: block;
        cursor: zoom-in;
    }

    .howto-lightbox {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.86);
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        z-index: 9999;
    }

    .howto-toggle {
        display: none;
    }

    .howto-toggle:checked + .howto-lightbox {
        opacity: 1;
        pointer-events: auto;
    }

    .howto-lightbox img {
        max-width: 92vw;
        max-height: 88vh;
        border-radius: 16px;
        border: 1px solid #30363d;
        box-shadow: 0 20px 48px rgba(0, 0, 0, 0.55);
    }

    .howto-close {
        position: fixed;
        top: 24px;
        right: 28px;
        color: #c9d1d9;
        pointer-events: none;
        font-size: 2rem;
        line-height: 1;
    }

    .time-badge {
        background: rgba(255, 90, 31, 0.1);
        color: #ff5a1f;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    /* Custom Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }

    .stTabs [aria-selected="true"] {
        background-color: transparent;
        border-bottom: 2px solid #ff5a1f !important;
        color: #ff5a1f !important;
    }
    </style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---
def load_lottieurl(url: str):
    try:
        r = requests.get(url, timeout=5, verify=True)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


def format_duration(minutes: float) -> str:
    """Formatiert Minuten in eine lesbare Dauer (h m)."""
    if minutes < 60:
        return f"{int(minutes)} Min."
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours} Std."
    return f"{hours}h {mins}m"


def validate_pdf(uploaded_file) -> tuple[bool, str]:
    """Prüft strikt auf Etsy-Bestellbestätigungen mit mehreren Pflicht-Fingerabdrücken."""
    generic_invalid_msg = "Datei abgelehnt. Nur gültige Etsy-Bestellbestätigungen sind erlaubt."

    if uploaded_file.type != "application/pdf":
        return False, generic_invalid_msg

    try:
        from io import BytesIO
        file_bytes = uploaded_file.getvalue()
        if not file_bytes.startswith(PDF_MAGIC_BYTES):
            return False, generic_invalid_msg

        reader = PdfReader(BytesIO(file_bytes))
        if len(reader.pages) == 0:
            return False, generic_invalid_msg

        scan_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        text_lower = scan_text.lower()

        # Etsy-Fingerprint: alle Kernmarker müssen vorhanden sein
        order_marker_ok = bool(
            re.search(r"bestellung\s+nr\.\s*\d+", text_lower)
            or re.search(r"order\s*#\s*\d+", text_lower)
        )
        etsy_brand_ok = "etsy" in text_lower
        payment_ok = "etsy payments" in text_lower or "paypal" in text_lower
        shipping_ok = "versand an" in text_lower or "ship to" in text_lower
        total_ok = "gesamtsumme der bestellung" in text_lower or "order total" in text_lower
        origami_ok = "origami" in text_lower and "konfetti" in text_lower

        if order_marker_ok and etsy_brand_ok and payment_ok and shipping_ok and total_ok and origami_ok:
            return True, ""
        return False, generic_invalid_msg

    except Exception:
        return False, generic_invalid_msg


def update_global_stats(order_count: int):
    """Speichert NUR anonyme Summen global (DSGVO-safe)."""
    stats = load_global_stats()
    stats["total_orders"] = stats.get("total_orders", 0) + order_count
    stats["total_time_saved"] = stats.get("total_time_saved", 0) + (order_count * TIME_PER_ORDER_MIN)
    stats["total_conversions"] = stats.get("total_conversions", 0) + 1
    hourly_orders = stats.get("hourly_orders", {})
    hour_key = datetime.now().replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00")
    hourly_orders[hour_key] = int(hourly_orders.get(hour_key, 0)) + int(order_count)
    stats["hourly_orders"] = hourly_orders
    
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except IOError:
        pass


def load_global_stats() -> dict:
    """Lädt die anonymen globalen Statistiken."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {"total_orders": 0, "total_time_saved": 0, "total_conversions": 0, "hourly_orders": {}}


# --- LOTTIE ANIMATION ---
lottie_loading = load_lottieurl(
    "https://lottie.host/c10aad43-6efb-48f6-a720-a4692411b24f/sLPRdZxhya.json"
)

# --- SESSION STATE ---
# --- SESSION STATE MARKER ---
if "stage" not in st.session_state:
    st.session_state.stage = "upload"
if "last_upload_time" not in st.session_state:
    st.session_state.last_upload_time = 0
if "latest_upload_at" not in st.session_state:
    st.session_state.latest_upload_at = None
if "latest_uploaded_file_key" not in st.session_state:
    st.session_state.latest_uploaded_file_key = None

# --- HOW-TO IMAGE ---
HOWTO_IMAGE_PATH = "Howtoorders.png"
show_howto_image = os.path.exists(HOWTO_IMAGE_PATH)
howto_base64 = None
if show_howto_image:
    with open(HOWTO_IMAGE_PATH, "rb") as img_file:
        howto_base64 = base64.b64encode(img_file.read()).decode("utf-8")

st.markdown(
    "<h1 style='text-align: center; color: white;'>Antsy <span style='color: #ff5a1f;'>Secure Gateway</span></h1>",
    unsafe_allow_html=True,
)

# --- PHASE 1: UPLOAD ---
if st.session_state.stage == "upload":
    _, col, _ = st.columns([1, 2, 1])
    with col:
        if show_howto_image and howto_base64:
            st.markdown(
                f"""
                <div class="howto-card">
                    <p class="howto-title">How-to: Etsy Bestellungen als PDF exportieren</p>
                    <label for="howto-lightbox-toggle">
                        <img class="howto-thumb" src="data:image/png;base64,{howto_base64}" alt="How-to Anleitung">
                    </label>
                </div>
                <input id="howto-lightbox-toggle" class="howto-toggle" type="checkbox">
                <label class="howto-lightbox" for="howto-lightbox-toggle">
                    <img src="data:image/png;base64,{howto_base64}" alt="How-to Anleitung groß">
                    <span class="howto-close">×</span>
                </label>
                """,
                unsafe_allow_html=True,
            )

        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Etsy-PDF hochladen", type=["pdf"])

        if uploaded_file:
            current_file_key = f"{uploaded_file.name}:{uploaded_file.size}"
            if current_file_key != st.session_state.latest_uploaded_file_key:
                st.session_state.latest_uploaded_file_key = current_file_key
                st.session_state.latest_upload_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # PDF Validierung
            is_valid, error_msg = validate_pdf(uploaded_file)

            if is_valid:
                st.success("Datei verifiziert. Sicherheits-Check bestanden.")

                current_time = time.time()
                time_since_last = current_time - st.session_state.last_upload_time

                if time_since_last < UPLOAD_DELAY:
                    st.warning(f"API-Schutz: Bitte noch {int(UPLOAD_DELAY - time_since_last)}s warten.")
                else:
                    if st.button("Jetzt sicher konvertieren"):
                        st.session_state.last_upload_time = current_time
                        st.session_state.uploaded_file = uploaded_file
                        st.session_state.stage = "processing"
                        st.rerun()
            else:
                st.error(error_msg)

        st.markdown("</div>", unsafe_allow_html=True)

# --- PHASE 2: PROCESSING ---
if st.session_state.stage == "processing":
    # SICHERHEITS-GATE: Nochmals validieren bevor an n8n gesendet wird
    is_valid, error_msg = validate_pdf(st.session_state.uploaded_file)
    if not is_valid:
        st.error("Upload abgebrochen: Datei nicht zulässig.")
        st.session_state.stage = "upload"
        time.sleep(2)
        st.rerun()

    _, col, _ = st.columns([1, 2, 1])
    with col:
        if lottie_loading:
            st_lottie(lottie_loading, height=350, key="loading_anim")

        with st.status("Verbinde zum Server...", expanded=True) as status:
            try:
                webhook_url = st.secrets["N8N_URL"]

                auth_token = st.secrets["N8N_TOKEN"]
                headers = {"x-antsy-token": auth_token}

                files = {
                    "data": (
                        st.session_state.uploaded_file.name,
                        st.session_state.uploaded_file.getvalue(),
                        "application/pdf",
                    )
                }

                response = requests.post(
                    webhook_url, files=files, headers=headers, timeout=90, verify=True
                )

                if response.status_code == 200:
                    st.session_state.csv_text = response.text
                    st.session_state.csv_bytes = response.content

                    try:
                        df_temp = pd.read_csv(StringIO(response.text), sep=";")
                        order_count = len(df_temp)
                    except (pd.errors.ParserError, ValueError):
                        order_count = 0

                    if order_count <= 0:
                        status.update(
                            label="Datei abgelehnt: Keine Etsy-Bestellungen erkannt.",
                            state="error",
                            expanded=True,
                        )
                        st.error("Datei abgelehnt.")
                        if st.button("Zurück"):
                            st.session_state.stage = "upload"
                            st.rerun()
                        st.stop()

                    status.update(
                        label="Sicherheits-Check bestanden!",
                        state="complete",
                        expanded=False,
                    )

                    st.session_state.current_order_count = order_count
                    update_global_stats(order_count)

                    time.sleep(1)
                    st.session_state.stage = "result"
                    st.rerun()
                elif response.status_code == 406:
                    st.error("Datei wurde vom Sicherheitscheck abgelehnt.")
                    if st.button("Abbrechen"):
                        st.session_state.stage = "upload"
                        st.rerun()
                elif response.status_code == 403:
                    st.error("Shop ist nicht autorisiert.")
                    if st.button("Zurück"):
                        st.session_state.stage = "upload"
                        st.rerun()
                else:
                    st.error(f"Fehler: {response.status_code}. Bitte n8n-Log prüfen.")
                    if st.button("Zurück"):
                        st.session_state.stage = "upload"
                        st.rerun()

            except requests.ConnectionError:
                st.error("Verbindungsfehler: n8n-Server nicht erreichbar.")
            except requests.Timeout:
                st.error("Timeout: n8n hat nicht rechtzeitig geantwortet.")
            except Exception as e:
                st.error(f"Unerwarteter Fehler: {e}")

# --- PHASE 3: RESULT ---
if st.session_state.stage == "result":
    order_count = st.session_state.get("current_order_count", 0)
    time_saved_this_file = order_count * TIME_PER_ORDER_MIN
    global_stats = load_global_stats()
    total_orders = global_stats.get("total_orders", 0)
    total_time_saved = global_stats.get("total_time_saved", 0)

    st.markdown(f"""
        <div class="main-card" style="padding: 30px; margin-bottom: 25px;">
            <h2 style="color: white; margin-bottom: 20px;">Konvertierung abgeschlossen</h2>
            <div class="stats-container">
                <div class="stat-card">
                    <div class="stat-label">Zeitersparnis dieser Datei</div>
                    <div class="stat-value">{format_duration(time_saved_this_file)}</div>
                    <p style="color: #8b949e; margin-top: 8px;">
                        Verarbeitete Einzelbestellungen: {order_count}
                    </p>
                </div>
                <div class="stat-card" style="border-color: #ff5a1f;">
                    <div class="stat-label">Zeitersparnis insgesamt</div>
                    <div class="stat-value">{format_duration(total_time_saved)}</div>
                    <p style="color: #8b949e; margin-top: 8px;">
                        Verarbeitete Einzelbestellungen: {total_orders}
                    </p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    hourly_orders = global_stats.get("hourly_orders", {})
    # Last 24 full hours; current running hour is excluded.
    timeline_data = []
    timeline_start = now - timedelta(hours=24)
    for i in range(24):
        hour_start = timeline_start + timedelta(hours=i)
        hour_key = hour_start.strftime("%Y-%m-%d %H:00")
        timeline_data.append(
            {
                "time": hour_start,
                "hour_label": hour_start.strftime("%d.%m %H:00"),
                "orders": int(hourly_orders.get(hour_key, 0)),
            }
        )

    timeline_df = pd.DataFrame(timeline_data)
    st.markdown(
        "<div style='margin-top: 20px; color: #c9d1d9; font-size: 0.95rem;'>"
        "Bestellungen pro Stunde (letzte 24h, Balkendiagramm)"
        "</div>",
        unsafe_allow_html=True,
    )
    chart = (
        alt.Chart(timeline_df)
        .mark_bar(color="#ff5a1f")
        .encode(
            x=alt.X("time:T", axis=alt.Axis(title="Uhrzeit", format="%H:00")),
            y=alt.Y("orders:Q", axis=alt.Axis(title="Bestellungen")),
            tooltip=[
                alt.Tooltip("hour_label:N", title="Stunde"),
                alt.Tooltip("orders:Q", title="Bestellungen"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)

    if "csv_text" in st.session_state:
        try:
            df = pd.read_csv(StringIO(st.session_state.csv_text), sep=";")
            st.dataframe(df, use_container_width=True)
        except (pd.errors.ParserError, ValueError):
            st.info("Vorschau nicht verfügbar. CSV bereit zum Download.")

    st.download_button(
        "JTL-Ameise Datei speichern",
        st.session_state.csv_bytes,
        file_name="antsy_jtl_import.csv",
    )
    if st.button("Neue Datei"):
        st.session_state.stage = "upload"
        st.rerun()

st.divider()
st.caption("Keine Haftung für Fehler")
