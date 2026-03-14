import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# --- SAYFA VE TASARIM AYARLARI ---
st.set_page_config(page_title="F1 Engineering Dashboard", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #15151e; color: white; }
    .stMetric { background-color: #1e1e27; padding: 15px; border-radius: 10px; border-left: 5px solid #ff1801; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏁 F1 Pro Analytics: H2H & Constructor Suite")
st.write("---")

BASE_URL = "https://api.openf1.org/v1"

# --- YARDIMCI FONKSİYONLAR ---
@st.cache_data
def get_data(endpoint, params=None):
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", params=params)
        return res.json() if res.status_code == 200 else []
    except:
        return []

def format_lap_time(seconds):
    """Saniyeyi Dakika:Saniye.Milisaniye formatına çevirir."""
    if pd.isna(seconds) or seconds <= 0:
        return "-"
    minutes = int(seconds // 60)
    rem_seconds = seconds % 60
    return f"{minutes}:{rem_seconds:06.3f}"

# --- SIDEBAR: DİNAMİK SEZON VE TAKIM SEÇİMİ ---
with st.sidebar:
    st.header("📅 Yarış Seçimi")
    selected_year = st.selectbox("Sezon", [2024, 2023], index=0)
    
    # Yarış seanslarını çek (Sadece 'Race' olanlar)
    sessions_data = get_data("sessions", {"year": selected_year, "session_name": "Race"})
    
    if sessions_data:
        session_map = {f"{s['location']} GP": s['session_key'] for s in sessions_data}
        selected_gp = st.selectbox("Grand Prix", list(session_map.keys()))
        session_key = session_map[selected_gp]
    else:
        st.error("Sezon verileri yüklenemedi.")
        st.stop()

    st.write("---")
    st.header("🏎️ Takım Kontrol")
    all_drivers = get_data("drivers", {"session_key": session_key})
    
    if all_drivers:
        teams = sorted(list(set([d['team_name'] for d in all_drivers])))
        selected_team = st.selectbox("Takım", teams)
        team_drivers = [d for d in all_drivers if d['team_name'] == selected_team]
        
        for td in team_drivers:
            st.image(td['headshot_url'], caption=td['full_name'], width=80)
    else:
        st.stop()

# --- ANA PANEL: TABLI YAPI ---
tab1, tab2 = st.tabs(["⚔️ Head-to-Head (Sürücü)", "🔧 Constructor (Araç Teknik)"])

# --- TAB 1: HEAD-TO-HEAD (H2H) ---
with tab1:
    if len(team_drivers) >= 2:
        d1, d2 = team_drivers[0], team_drivers[1]
        st.subheader(f"Battle: {d1['last_name']} vs {d2['last_name']}")
        
        laps1 = pd.DataFrame(get_data("laps", {"session_key": session_key, "driver_number": d1['driver_number']})).dropna(subset=['lap_duration'])
        laps2 = pd.DataFrame(get_data("laps", {"session_key": session_key, "driver_number": d2['driver_number']})).dropna(subset=['lap_duration'])

        if not laps1.empty and not laps2.empty:
            f1, f2 = laps1['lap_duration'].min(), laps2['lap_duration'].min()
            delta = abs(f1 - f2)
            
            # Metrik Kartları (Formatlanmış)
            c1, c2, c3 = st.columns(3)
            c1.metric(d1['last_name'], format_lap_time(f1))
            c2.metric(d2['last_name'], format_lap_time(f2))
            c3.metric("Fark (Delta)", f"{delta:.3f}s", delta_color="inverse")

            # Race Pace Grafiği (Saniye üzerinden çizilir)
            common = min(len(laps1), len(laps2))
            comp_df = pd.DataFrame({
                "Tur": range(1, common + 1),
                d1['last_name']: laps1['lap_duration'].iloc[:common].values,
                d2['last_name']: laps2['lap_duration'].iloc[:common].values
            })
            fig_h2h = px.line(comp_df, x="Tur", y=[d1['last_name'], d2['last_name']],
                             title="Race Pace (Tur Bazlı Karşılaştırma)", template="plotly_dark",
                             color_discrete_sequence=['#FF1801', '#00D2BE'], labels={"value": "Saniye"})
            st.plotly_chart(fig_h2h, use_container_width=True)

            # Detaylı Tur Tablosu
            with st.expander("Tur Zamanları Listesi"):
                display_df = pd.DataFrame({
                    "Tur": range(1, common + 1),
                    d1['last_name']: laps1['lap_duration'].iloc[:common].apply(format_lap_time),
                    d2['last_name']: laps2['lap_duration'].iloc[:common].apply(format_lap_time)
                })
                st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("Bu takımda iki sürücü bulunamadı.")

# --- TAB 2: CONSTRUCTOR & TELEMETRY ---
with tab2:
    st.subheader(f"Engineering Suite: {selected_team} Chassis Analysis")
    
    with st.spinner("Telemetri verileri senkronize ediliyor..."):
        # Son 300 telemetri kaydını çekiyoruz
        tel1 = pd.DataFrame(get_data("car_data", {"session_key": session_key, "driver_number": d1['driver_number']})).tail(300)
        tel2 = pd.DataFrame(get_data("car_data", {"session_key": session_key, "driver_number": d2['driver_number']})).tail(300)

    if not tel1.empty and not tel2.empty:
        # 1. Mühendislik Grafiği: Engine Map
        fig_engine = go.Figure()
        fig_engine.add_trace(go.Scatter(x=tel1['speed'], y=tel1['rpm'], mode='markers', name=d1['last_name'], marker=dict(color='#FF1801', opacity=0.6)))
        fig_engine.add_trace(go.Scatter(x=tel2['speed'], y=tel2['rpm'], mode='markers', name=d2['last_name'], marker=dict(color='#00D2BE', opacity=0.6)))
        fig_engine.update_layout(title="Power Unit Analysis: Speed vs RPM", xaxis_title="Hız (km/h)", yaxis_title="RPM", template="plotly_dark")
        st.plotly_chart(fig_engine, use_container_width=True)

        col_left, col_right = st.columns(2)
        with col_left:
            st.write("### Vites Dağılım Analizi")
            g1 = tel1['n_gear'].value_counts().sort_index()
            g2 = tel2['n_gear'].value_counts().sort_index()
            gear_df = pd.DataFrame({d1['last_name']: g1, d2['last_name']: g2}).fillna(0)
            st.bar_chart(gear_df)
            
        with col_right:
            st.write("### Teknik Verimlilik (DRS)")
            drs1 = (tel1['drs'] >= 10).mean() * 100
            drs2 = (tel2['drs'] >= 10).mean() * 100
            st.progress(drs1/100, text=f"{d1['last_name']} DRS Kullanımı: %{drs1:.1f}")
            st.progress(drs2/100, text=f"{d2['last_name']} DRS Kullanımı: %{drs2:.1f}")
            
            avg_s1, avg_s2 = tel1['speed'].mean(), tel2['speed'].mean()
            st.info(f"Ortalama Hız: {d1['last_name']} {avg_s1:.1f} km/h | {d2['last_name']} {avg_s2:.1f} km/h")
    else:
        st.error("Telemetri verisi bu seans için mevcut değil.")