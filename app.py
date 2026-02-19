import json
import os
import re
import time
import base64
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from typing import Optional
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import requests
import streamlit as st
from pypdf import PdfReader
from streamlit_lottie import st_lottie

st.set_page_config(page_title="Etsy2JTL", layout="wide")

UPLOAD_DELAY = 25
STATS_FILE = "antsy_global_stats.json"
TIME_PER_ORDER_MIN = 2.5
PDF_MAGIC_BYTES = b"%PDF"
HISTORY_HOURS = 12
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def inject_styles():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&display=swap');

            .stApp {
                background:
                    radial-gradient(circle at 20% 0%, rgba(255, 184, 121, 0.35), transparent 40%),
                    radial-gradient(circle at 80% 100%, rgba(129, 193, 255, 0.25), transparent 45%),
                    linear-gradient(135deg, #102038 0%, #1a2f4a 100%);
            }

            .stApp, .stApp * {
                font-family: "Sora", "Trebuchet MS", sans-serif !important;
            }

            [data-testid="stMainBlockContainer"],
            [data-testid="stAppViewContainer"] .main .block-container,
            .main .block-container {
                width: min(1280px, calc(100vw - 3rem)) !important;
                max-width: 1280px !important;
                margin-left: auto !important;
                margin-right: auto !important;
                margin-top: 10rem;
                margin-bottom: 2rem;
                padding: 1.7rem 1.6rem 1.8rem !important;
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, 0.28);
                background: rgba(255, 255, 255, 0.09);
                box-shadow: 0 18px 50px rgba(4, 11, 24, 0.42);
                animation: fadeInCard 0.45s ease-out;
            }

            @keyframes fadeInCard {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes greenShimmer {
                0% { background-position: 0% 50%; }
                100% { background-position: 200% 50%; }
            }

            h1, h2, h3, h4, p, label,
            div[data-testid="stCaptionContainer"],
            div[data-testid="stAlert"] p {
                text-align: center !important;
            }

            div[data-testid="stFileUploaderDropzone"] {
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.08);
                text-align: center;
            }

            div[data-testid="stFileUploader"] {
                width: min(820px, 100%);
                margin-left: auto;
                margin-right: auto;
            }

            div.stButton,
            div.stDownloadButton,
            div[data-testid="stButton"],
            div[data-testid="stDownloadButton"],
            div[data-testid="stFormSubmitButton"] {
                width: 100%;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
            }

            div[data-testid="stFileUploaderDropzone"] > div {
                width: 100%;
                display: flex;
                flex-direction: column;
                align-items: center;
            }

            div.stButton > button,
            div.stDownloadButton > button,
            div[data-testid="stButton"] > button,
            div[data-testid="stDownloadButton"] > button,
            div[data-testid="stFileUploaderDropzone"] button,
            button[data-testid="baseButton-primary"],
            button[data-testid="baseButton-secondary"] {
                margin: 0.35rem auto 0 !important;
                display: flex !important;
                width: 320px !important;
                max-width: 100% !important;
                border-radius: 999px;
                border: 1px solid rgba(126, 255, 182, 0.42);
                font-weight: 600;
                padding: 0.55rem 1.2rem;
                color: #eafff2;
                text-align: center !important;
                justify-content: center !important;
                align-items: center !important;
                background: linear-gradient(
                    115deg,
                    rgba(17, 91, 59, 0.45) 0%,
                    rgba(64, 220, 141, 0.38) 25%,
                    rgba(178, 255, 218, 0.5) 50%,
                    rgba(50, 187, 117, 0.38) 75%,
                    rgba(17, 91, 59, 0.45) 100%
                );
                background-size: 220% 220%;
                box-shadow:
                    inset 0 1px 0 rgba(255, 255, 255, 0.3),
                    0 0 0 1px rgba(109, 255, 174, 0.12),
                    0 8px 24px rgba(33, 173, 111, 0.34);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                animation: greenShimmer 2.8s linear infinite;
            }

            div.stButton > button:hover,
            div.stDownloadButton > button:hover,
            div[data-testid="stFileUploaderDropzone"] button:hover,
            button[data-testid="baseButton-primary"]:hover,
            button[data-testid="baseButton-secondary"]:hover {
                transform: translateY(-1px) scale(1.01);
                box-shadow:
                    inset 0 1px 0 rgba(255, 255, 255, 0.35),
                    0 0 0 1px rgba(109, 255, 174, 0.2),
                    0 10px 28px rgba(33, 173, 111, 0.42);
            }

            div[data-testid="stMetric"] {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 16px;
                padding: 0.8rem;
            }

            div[data-testid="stMetricLabel"],
            div[data-testid="stMetricValue"] {
                width: 100% !important;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
                text-align: center !important;
            }

            div[data-testid="stMetricLabel"] > div,
            div[data-testid="stMetricValue"] > div {
                width: 100% !important;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
                text-align: center !important;
            }

            div[data-testid="stMetric"] label,
            div[data-testid="stMetric"] p,
            div[data-testid="stMetric"] span {
                width: 100% !important;
                display: block !important;
                text-align: center !important;
            }

            div[data-testid="stDataFrame"] {
                border-radius: 14px;
                overflow: hidden;
            }

            .glass-howto-card {
                margin: 0 auto 1.2rem;
                padding: 0.45rem 0.45rem 0.5rem;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.22);
                background: rgba(255, 255, 255, 0.09);
                box-shadow: 0 8px 20px rgba(8, 19, 35, 0.28);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                width: min(820px, 100%);
            }

            .glass-howto-title {
                margin: 0 0 0.4rem;
                font-size: 1.02rem;
                font-weight: 600;
                color: #eaf4ff;
                text-align: center;
            }

            .glass-howto-thumb-link {
                display: block;
                width: 100%;
                margin: 0 auto;
            }

            .glass-howto-thumb {
                display: block;
                width: 100%;
                margin: 0;
                border-radius: 14px;
                border: 0;
                box-shadow: none;
                cursor: zoom-in;
            }

            .glass-howto-hint {
                margin: 0.4rem 0 0;
                font-size: 0.84rem;
                color: rgba(235, 245, 255, 0.88);
                text-align: center;
            }

            .howto-lightbox-wrap {
                position: relative;
            }

            .howto-lightbox-toggle {
                position: fixed;
                left: -9999px;
                opacity: 0;
            }

            .howto-lightbox {
                position: fixed !important;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                z-index: 99999;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 0;
                background: rgba(5, 11, 23, 0.84);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.22s ease;
            }

            .howto-lightbox-toggle:checked ~ .howto-lightbox {
                opacity: 1;
                pointer-events: auto;
            }

            .howto-lightbox-backdrop {
                position: absolute;
                inset: 0;
                z-index: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: zoom-out;
            }

            .howto-lightbox-image {
                width: 100vw;
                height: 100vh;
                max-width: none;
                max-height: none;
                object-fit: contain;
                border-radius: 0;
                border: 0;
                box-shadow: none;
                display: block;
            }

            .howto-lightbox-close {
                position: fixed;
                top: 24px;
                right: 28px;
                font-size: 2.1rem;
                line-height: 1;
                color: #eafff2;
                text-decoration: none;
                z-index: 3;
                cursor: pointer;
                padding: 0.3rem 0.6rem;
                border-radius: 10px;
                background: rgba(5, 11, 23, 0.48);
                border: 1px solid rgba(234, 255, 242, 0.28);
            }

            .post-convert-howto {
                width: min(820px, 100%);
                margin: 1rem auto 0.6rem;
                padding: 0.95rem 1rem;
                border-radius: 16px;
                border: 1px solid rgba(100, 232, 170, 0.28);
                background: rgba(14, 55, 40, 0.22);
                box-shadow: 0 10px 24px rgba(6, 21, 16, 0.25);
            }

            .post-convert-howto h4 {
                margin: 0 0 0.5rem;
                font-size: 1rem;
                color: #eafff2;
                text-align: left !important;
            }

            .post-convert-howto ol,
            .post-convert-howto ul {
                margin: 0;
                padding-left: 1.15rem;
                text-align: left !important;
            }

            .post-convert-howto ul {
                margin-top: 0.35rem;
            }

            .post-convert-howto li {
                margin: 0.24rem 0;
                text-align: left !important;
                color: #eafff2;
            }

            .post-convert-howto-image-wrap {
                width: min(820px, 100%);
                margin: 0 auto 0.25rem;
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(100, 232, 170, 0.28);
                box-shadow: 0 10px 24px rgba(6, 21, 16, 0.25);
            }

            .post-convert-howto-image {
                display: block;
                width: 100%;
                height: auto;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def centered_button(label: str, **kwargs):
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        return st.button(label, use_container_width=True, **kwargs)


def centered_download_button(label: str, data, file_name: str, **kwargs):
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        return st.download_button(
            label,
            data,
            file_name=file_name,
            use_container_width=True,
            **kwargs,
        )


def render_howto_lightbox():
    howto_image_path = None
    for candidate in ("howtoorder.png", "Howtoorders.png"):
        if os.path.exists(candidate):
            howto_image_path = candidate
            break

    if not howto_image_path:
        return

    try:
        with open(howto_image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    except IOError:
        return

    st.markdown(
        f"""
        <div class="howto-lightbox-wrap">
            <input type="checkbox" id="howto-lightbox-toggle" class="howto-lightbox-toggle"/>
            <div class="glass-howto-card">
                <p class="glass-howto-title">Etsy PDF erstellen</p>
                <label class="glass-howto-thumb-link" for="howto-lightbox-toggle" aria-label="How-To Bild vergroessern">
                    <img class="glass-howto-thumb" src="data:image/png;base64,{encoded_image}" alt="How-To Anleitung"/>
                </label>
            </div>
            <div class="howto-lightbox">
                <label class="howto-lightbox-backdrop" for="howto-lightbox-toggle" aria-label="Lightbox schliessen">
                    <img class="howto-lightbox-image" src="data:image/png;base64,{encoded_image}" alt="How-To Anleitung gross"/>
                </label>
                <label class="howto-lightbox-close" for="howto-lightbox-toggle" aria-label="Lightbox schliessen">&times;</label>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_post_conversion_howto():
    st.markdown(
        """
        <div class="post-convert-howto">
            <h4>How-to nach der Konvertierung</h4>
            <ol>
                <li>Denke daran, bei Etsy alle Bestellungen als verschickt zu markieren.</li>
                <li>Stelle in der JTL-Ameise beim Import der Aufträge Folgendes ein:
                    <ul>
                        <li>Dezimaltrennzeichen: Punkt</li>
                        <li>Tausendertrennzeichen: Komma</li>
                        <li>Preis darf 0 sein: Nein</li>
                        <li>Vorhandene Aufträge aktualisieren: Nicht aktualisieren</li>
                        <li>Speichere die Vorlage für tägliche Imports</li>
                    </ul>
                 <li>Täglicher automatischer Upload mit der Ameise folgt nach der Beta zeitnah.</li>
                </li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

    image_path = "SCR-20260218-ocyu.png"
    if not os.path.exists(image_path):
        return

    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    except IOError:
        return

    st.markdown(
        f"""
        <div class="post-convert-howto-image-wrap">
            <img class="post-convert-howto-image" src="data:image/png;base64,{encoded_image}" alt="JTL-Ameise Importeinstellungen"/>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_lottieurl(url: str):
    try:
        r = requests.get(url, timeout=5, verify=True)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


def format_duration(minutes: float) -> str:
    if minutes < 60:
        return f"{int(minutes)} Min."
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours} Std."
    return f"{hours}h {mins}m"


def berlin_now_naive() -> datetime:
    # Keep timestamps in Berlin local time while storing naive hour keys.
    return datetime.now(BERLIN_TZ).replace(tzinfo=None)


def berlin_now_hour_naive() -> datetime:
    return berlin_now_naive().replace(minute=0, second=0, microsecond=0)


def validate_pdf(uploaded_file) -> tuple[bool, str]:
    generic_invalid_msg = "Datei abgelehnt. Nur gültige Etsy-Bestellbestätigungen sind erlaubt."

    if uploaded_file.type != "application/pdf":
        return False, generic_invalid_msg

    try:
        file_bytes = uploaded_file.getvalue()
        if not file_bytes.startswith(PDF_MAGIC_BYTES):
            return False, generic_invalid_msg

        reader = PdfReader(BytesIO(file_bytes))
        if len(reader.pages) == 0:
            return False, generic_invalid_msg

        scan_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        text_lower = scan_text.lower()

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


def trim_hourly_history(history: dict, now_hour: Optional[datetime] = None) -> dict:
    if not isinstance(history, dict):
        return {}

    reference_hour = now_hour or berlin_now_hour_naive()
    trimmed: dict[str, int] = {}

    for hour_key, value in history.items():
        try:
            hour_dt = datetime.strptime(hour_key, "%Y-%m-%d %H:00")
            count = max(int(value), 0)
        except (TypeError, ValueError):
            continue

        hours_ago = (reference_hour - hour_dt).total_seconds() / 3600
        if 0 <= hours_ago < HISTORY_HOURS:
            trimmed[hour_key] = count

    return trimmed


def build_hourly_history_df(stats: dict) -> pd.DataFrame:
    now_hour = berlin_now_hour_naive()
    history = trim_hourly_history(stats.get("hourly_orders", {}), now_hour)

    rows = []
    for offset in range(HISTORY_HOURS - 1, -1, -1):
        hour_dt = now_hour - timedelta(hours=offset)
        hour_key = hour_dt.strftime("%Y-%m-%d %H:00")
        rows.append(
            {
                "Stunde": hour_dt.strftime("%H:%M"),
                "Bestellungen": int(history.get(hour_key, 0)),
            }
        )
    return pd.DataFrame(rows)


def render_hourly_orders_chart(stats: dict):
    history_df = build_hourly_history_df(stats)

    chart = (
        alt.Chart(history_df)
        .mark_bar(size=24, cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("Stunde:N", axis=alt.Axis(title=None, labelAngle=0)),
            y=alt.Y("Bestellungen:Q", axis=alt.Axis(title="Bestellungen"), scale=alt.Scale(domainMin=0)),
            color=alt.value("#2FD38A"),
            tooltip=[
                alt.Tooltip("Stunde:N", title="Stunde"),
                alt.Tooltip("Bestellungen:Q", title="Bestellungen"),
            ],
        )
        .properties(height=230)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#eafff2",
            titleColor="#eafff2",
            gridColor="rgba(234, 255, 242, 0.16)",
            domainColor="rgba(234, 255, 242, 0.22)",
            tickColor="rgba(234, 255, 242, 0.22)",
        )
    )

    st.markdown("#### Bestellungen pro Stunde (letzte 12h, Berlin)")
    st.altair_chart(chart, use_container_width=True)


def update_global_stats(order_count: int):
    stats = load_global_stats()
    stats["total_orders"] = stats.get("total_orders", 0) + order_count
    stats["total_time_saved"] = stats.get("total_time_saved", 0) + (order_count * TIME_PER_ORDER_MIN)
    stats["total_conversions"] = stats.get("total_conversions", 0) + 1

    current_hour = berlin_now_hour_naive()
    current_hour_key = current_hour.strftime("%Y-%m-%d %H:00")
    hourly_history = trim_hourly_history(stats.get("hourly_orders", {}), current_hour)
    hourly_history[current_hour_key] = hourly_history.get(current_hour_key, 0) + order_count
    stats["hourly_orders"] = trim_hourly_history(hourly_history, current_hour)

    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except IOError:
        pass


def load_global_stats() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
                stats["hourly_orders"] = trim_hourly_history(stats.get("hourly_orders", {}))
                return stats
        except (json.JSONDecodeError, IOError):
            return {}
    return {"total_orders": 0, "total_time_saved": 0, "total_conversions": 0, "hourly_orders": {}}


lottie_loading = load_lottieurl(
    "https://lottie.host/c10aad43-6efb-48f6-a720-a4692411b24f/sLPRdZxhya.json"
)

if "stage" not in st.session_state:
    st.session_state.stage = "upload"
if "last_upload_time" not in st.session_state:
    st.session_state.last_upload_time = 0

inject_styles()
st.title("ETSY2CSV")

if st.session_state.stage == "upload":
    render_howto_lightbox()
    uploaded_file = st.file_uploader("Etsy-PDF hochladen", type=["pdf"])

    if uploaded_file:
        is_valid, error_msg = validate_pdf(uploaded_file)

        if is_valid:
            st.success("Datei verifiziert. Sicherheits-Check bestanden.")

            current_time = time.time()
            time_since_last = current_time - st.session_state.last_upload_time

            if time_since_last < UPLOAD_DELAY:
                st.warning(f"API-Schutz: Bitte noch {int(UPLOAD_DELAY - time_since_last)}s warten.")
            elif centered_button("Jetzt umwandeln"):
                st.session_state.last_upload_time = current_time
                st.session_state.uploaded_file = uploaded_file
                st.session_state.stage = "processing"
                st.rerun()
        else:
            st.error(error_msg)

if st.session_state.stage == "processing":
    is_valid, _ = validate_pdf(st.session_state.uploaded_file)
    if not is_valid:
        st.error("Upload abgebrochen: Datei nicht zulässig.")
        st.session_state.stage = "upload"
        time.sleep(2)
        st.rerun()

    if lottie_loading:
        st_lottie(lottie_loading, height=250, key="loading_anim")

    status_placeholder = st.empty()
    status_placeholder.info("Verbinde zum Server...")

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
            webhook_url,
            files=files,
            headers=headers,
            timeout=90,
            verify=True,
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
                status_placeholder.empty()
                st.error("Datei abgelehnt: Keine Etsy-Bestellungen erkannt.")
                if centered_button("Zurück"):
                    st.session_state.stage = "upload"
                    st.rerun()
                st.stop()

            status_placeholder.success("Sicherheits-Check bestanden!")
            st.session_state.current_order_count = order_count
            update_global_stats(order_count)

            time.sleep(1)
            status_placeholder.empty()
            st.session_state.stage = "result"
            st.rerun()
        elif response.status_code == 406:
            status_placeholder.empty()
            st.error("Datei wurde vom Sicherheitscheck abgelehnt.")
            if centered_button("Abbrechen"):
                st.session_state.stage = "upload"
                st.rerun()
        elif response.status_code == 403:
            status_placeholder.empty()
            st.error("Shop ist nicht autorisiert.")
            if centered_button("Zurück"):
                st.session_state.stage = "upload"
                st.rerun()
        else:
            status_placeholder.empty()
            st.error(f"Fehler: {response.status_code}. Bitte n8n-Log prüfen.")
            if centered_button("Zurück"):
                st.session_state.stage = "upload"
                st.rerun()

    except requests.ConnectionError:
        status_placeholder.empty()
        st.error("Verbindungsfehler: n8n-Server nicht erreichbar.")
    except requests.Timeout:
        status_placeholder.empty()
        st.error("Timeout: n8n hat nicht rechtzeitig geantwortet.")
    except Exception as e:
        status_placeholder.empty()
        st.error(f"Unerwarteter Fehler: {e}")

if st.session_state.stage == "result":
    order_count = st.session_state.get("current_order_count", 0)
    time_saved_this_file = order_count * TIME_PER_ORDER_MIN
    global_stats = load_global_stats()
    total_orders = global_stats.get("total_orders", 0)
    total_time_saved = global_stats.get("total_time_saved", 0)

    st.subheader("Konvertierung abgeschlossen")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Zeitersparnis dieser Datei", format_duration(time_saved_this_file))
        st.caption(f"Verarbeitete Einzelbestellungen: {order_count}")
    with col2:
        st.metric("Zeitersparnis insgesamt", format_duration(total_time_saved))
        st.caption(f"Verarbeitete Einzelbestellungen: {total_orders}")

    render_hourly_orders_chart(global_stats)

    if "csv_text" in st.session_state:
        try:
            df = pd.read_csv(StringIO(st.session_state.csv_text), sep=";")
            st.dataframe(df, use_container_width=True)
        except (pd.errors.ParserError, ValueError):
            st.info("Vorschau nicht verfügbar. CSV bereit zum Download.")

    centered_download_button(
        "JTL-Ameise Datei speichern",
        st.session_state.csv_bytes,
        file_name="antsy_jtl_import.csv",
    )
    if centered_button("Neue Datei"):
        st.session_state.stage = "upload"
        st.rerun()

    render_post_conversion_howto()

st.divider()
st.caption("Es handelt sich hier um eine Beta Version. Bitte prüfe die generierte CSV vor dem Import in JTL-Ameise auf Korrektheit. Bei Problemen wende dich an den Support.")
st.caption("Hier wird keine KI verwendet.")
