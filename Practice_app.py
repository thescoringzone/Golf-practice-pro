import streamlit as st
import pandas as pd
import numpy as np
import datetime
import pytz
import json
import altair as alt
from supabase import create_client
from fpdf import FPDF
import tempfile

# ==========================================
# 1. APP CONFIG & PREMIUM CSS
# ==========================================
st.set_page_config(page_title="The Practice Club", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap');
    
    html, body, p, div, label, li, span, th, td, .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, [data-testid="stMetricValue"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; letter-spacing: -0.5px !important; }
    
    /* Premium Card Shadows */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
        border: 1px solid rgba(150,150,150,0.15) !important;
    }
    
    input[type="number"], input[type="text"] { text-align: center !important; font-weight: 500 !important; }
    .stButton > button { border-radius: 8px !important; transition: all 0.2s ease; font-weight: 600 !important; }
    [data-testid="stHeaderActions"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE CONNECTION
# ==========================================
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Database connection failed. Please check your Streamlit secrets.")

# ==========================================
# 3. GLOBAL STATE & TIME ENGINE
# ==========================================
pga_putts_baseline = {
    1: 1.00, 2: 1.01, 3: 1.04, 4: 1.11, 5: 1.23, 6: 1.34, 7: 1.43, 8: 1.50, 
    9: 1.56, 10: 1.61, 11: 1.65, 12: 1.69, 13: 1.72, 14: 1.75, 15: 1.78, 
    16: 1.81, 17: 1.83, 18: 1.85, 19: 1.87, 20: 1.88, 21: 1.89, 22: 1.90, 
    23: 1.91, 24: 1.92, 25: 1.94, 26: 1.95, 27: 1.96, 28: 1.97, 29: 1.99, 
    30: 2.00, 31: 2.01, 32: 2.03, 33: 2.04, 34: 2.05, 35: 2.06, 36: 2.08, 
    37: 2.09, 38: 2.10, 39: 2.12, 40: 2.13, 45: 2.19, 50: 2.25, 55: 2.31, 
    60: 2.37, 65: 2.42, 70: 2.47, 75: 2.51, 80: 2.55, 85: 2.58, 90: 2.61, 
    95: 2.64, 100: 2.67
}

def get_expected_putts(distance):
    xp = sorted(list(pga_putts_baseline.keys()))
    fp = [pga_putts_baseline[x] for x in xp]
    return float(np.interp(distance, xp, fp))

if 'current_user' not in st.session_state: st.session_state.current_user = None
if 'timezone' not in st.session_state: st.session_state.timezone = "UTC"
if 'page' not in st.session_state: st.session_state.page = "Login"

# Persistent Radio States
if 'driving_radio' not in st.session_state: st.session_state.driving_radio = "10 Shot"
if 'szl_radio' not in st.session_state: st.session_state.szl_radio = "Situational Practice 150-200"
if 'szm_radio' not in st.session_state: st.session_state.szm_radio = "Situational Practice 100-150"
if 'szs_radio' not in st.session_state: st.session_state.szs_radio = "Situational Practice 50-100"
if 'sg_radio' not in st.session_state: st.session_state.sg_radio = "Par 21 WB"
if 'putt_radio' not in st.session_state: st.session_state.putt_radio = "Pace"

def get_local_time_info():
    tz = pytz.timezone(st.session_state.timezone)
    local_time = datetime.datetime.now(tz)
    year, week_num, weekday = local_time.isocalendar()
    return local_time, year, week_num, (weekday == 7)

# ==========================================
# 4. DATA LOADER & UI HELPERS
# ==========================================
def load_all_logs(username):
    response = supabase.table("practice_logs").select("*").eq("user_name", username).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        def parse_json(x):
            if isinstance(x, dict): return x
            if isinstance(x, str):
                try: return json.loads(x)
                except: return {}
            return {}
        if 'raw_data' in df.columns:
            df['raw_data'] = df['raw_data'].apply(parse_json)
        return df
    return pd.DataFrame(columns=["id", "created_at", "user_name", "game_category", "game_name", "score_primary", "score_secondary", "raw_data", "week_number"])

def render_icon_grid(df_game, game_name):
    if df_game.empty:
        st.info("No practice sessions logged yet.")
        return
    df_game = df_game.sort_values('created_at', ascending=False).reset_index(drop=True)
    st.markdown("### 📜 Recent Sessions")
    for i, row in df_game.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            date_str = str(row['created_at'])[:10]
            p = row['score_primary']
            
            if row.get('game_category') == "Practice Rounds":
                raw = row.get('raw_data', {})
                gross = raw.get('gross_score', 0)
                tp = f"+{int(p)}" if p > 0 else ("E" if p == 0 else f"{int(p)}")
                score_display = f"{int(gross)} ({tp})"
            elif game_name == "Max SS/BS":
                score_display = f"{p:.0f} / {row['score_secondary']:.0f}"
            else:
                score_display = f"{p:.2f}"
            
            col1.write(f"**{date_str}**")
            col2.markdown(f"<div style='text-align: center; font-size: 1.5em; font-weight: 800; color: #0068C9;'>{score_display}</div>", unsafe_allow_html=True)
            with col3.popover("🗑️"):
                if st.button("Delete Permanent?", key=f"del_{row['id']}"):
                    supabase.table("practice_logs").delete().eq("id", row['id']).execute()
                    st.rerun()

# ==========================================
# 5. ROUTING: LOGIN GATE
# ==========================================
if st.session_state.current_user is None:
    st.markdown("<h1 style='text-align: center; font-size: 3.8em; margin-top: 5%;'>The Practice Club</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        u_in = st.text_input("Username", key="login_u_field").strip()
        tz_in = st.selectbox("Timezone", ["US/Eastern", "US/Central", "Europe/London", "UTC"], key="login_tz_field")
        if st.button("Authenticate & Enter", use_container_width=True, type="primary"):
            if u_in:
                st.session_state.current_user = u_in
                st.session_state.timezone = tz_in
                st.session_state.page = "Weekly Dashboard"
                st.rerun()

else:
    local_now, current_year, current_week, is_sunday = get_local_time_info()
    df_logs = load_all_logs(st.session_state.current_user)
    
    # SIDEBAR
    st.sidebar.title("👤 Profile")
    st.sidebar.write(f"**{st.session_state.current_user}**")
    if st.sidebar.button("Log Out", key="side_logout_btn"):
        st.session_state.current_user = None
        st.rerun()
    
    st.sidebar.divider()
    navs = ["Weekly Dashboard", "Practice Rounds", "Driving", "Scoring Zone Long", "Scoring Zone Mid", "Scoring Zone Short", "Short Game", "Putting", "Your Practice Trends"]
    for n in navs:
        if st.sidebar.button(n, use_container_width=True, key=f"nav_{n}", type="primary" if st.session_state.page == n else "secondary"):
            st.session_state.page = n
            st.rerun()

    # --- PAGE: WEEKLY DASHBOARD ---
    if st.session_state.page == "Weekly Dashboard":
        st.title("📊 Weekly Dashboard")
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'], errors='coerce')
        df_logs['Year_Filter'] = df_logs['created_at'].dt.isocalendar().year
        
        logged_weeks = sorted(df_logs['week_number'].unique().tolist(), reverse=True)
        if current_week not in logged_weeks: logged_weeks.insert(0, current_week)
        sel_w = st.selectbox("Select Week", logged_weeks, index=logged_weeks.index(current_week) if current_week in logged_weeks else 0, key="dashboard_w_sel")
        
        # Dashboard Filtering
        df_cw = df_logs[df_logs['week_number'].astype(int) == int(sel_w)].copy()
        
        struct = {
            "Practice Rounds": ["Straight up", "5m game", "10m game"],
            "Driving": ["10 Shot", "Max SS/BS"],
            "Scoring Zone Long": ["Situational Practice 150-200", "TM 150-200"],
            "Scoring Zone Mid": ["Situational Practice 100-150", "TM 100-150"],
            "Scoring Zone Short": ["Situational Practice 50-100", "TM 50-100"],
            "Short Game": ["Par 21 WB", "20 to 50", "6ft Game"],
            "Putting": ["Pace", "6-9-12", "2-8 Drill"]
        }
        
        done_games = df_cw['game_name'].tolist()
        done_cats = df_cw['game_category'].tolist()
        
        st.subheader(f"🎯 Week {sel_w} Checklist")
        for cat, games in struct.items():
            cat_icon = "✅" if cat in done_cats else "⏳"
            with st.expander(f"{cat_icon} **{cat}**"):
                for g in games:
                    g_icon = "✅" if g in done_games else "⭕"
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"{g_icon}  {g}")
                    if c2.button("Practice", key=f"go_{cat}_{g}"):
                        st.session_state.page = cat
                        if cat == "Practice Rounds": st.session_state.pr_game_select = g
                        st.rerun()

    # --- PAGE: PRACTICE ROUNDS (MASTER FORM) ---
    elif st.session_state.page == "Practice Rounds":
        st.title("⛳ Practice Rounds")
        if 'mode_pr' not in st.session_state: st.session_state.mode_pr = "grid"
        if 'pr_game_select' not in st.session_state: st.session_state.pr_game_select = "Straight up"
        if 'edit_pr_id' not in st.session_state: st.session_state.edit_pr_id = None
        if 'edit_pr_data' not in st.session_state: st.session_state.edit_pr_data = {}

        pr_game = st.selectbox("Game Type", ["Straight up", "5m game", "10m game"], key="pr_master_selector")
        st.session_state.pr_game_select = pr_game
        
        if pr_game == "Straight up": st.info("A normal 9 or 18 hole round.")
        elif pr_game == "5m game": st.info("Every GIR hit outside of 5m/17ft must be taken off green.")
        elif pr_game == "10m game": st.info("On odd holes, place drive 10m worse. Even holes, approach 10m worse.")

        if st.session_state.mode_pr == "grid":
            if st.button("➕ New Practice Round", type="primary", key="new_pr_trigger"):
                st.session_state.edit_pr_id = None
                st.session_state.edit_pr_data = {}
                st.session_state.mode_pr = "entry"
                st.rerun()
            
            df_pr = df_logs[(df_logs['game_category'] == "Practice Rounds") & (df_logs['game_name'] == pr_game)]
            if not df_pr.empty:
                st.write("### ✏️ Resume Round")
                options = ["-- Select --"] + df_pr.apply(lambda r: f"{str(r['created_at'])[:10]} (ID: {r['id']})", axis=1).tolist()
                sel_edit = st.selectbox("Resume:", options, key="edit_sel_picker")
                if sel_edit != "-- Select --":
                    eid = int(sel_edit.split("(ID: ")[1].replace(")", ""))
                    st.session_state.edit_pr_id = eid
                    st.session_state.edit_pr_data = df_pr[df_pr['id'] == eid].iloc[0]['raw_data']
                    st.session_state.mode_pr = "entry"
                    st.rerun()
            st.divider()
            render_icon_grid(df_pr, pr_game)
            
        else:
            if st.button("🔙 Back"):
                st.session_state.mode_pr = "grid"
                st.rerun()
            
            def gv(sec, k, d):
                if not st.session_state.edit_pr_data: return d
                if sec: return st.session_state.edit_pr_data.get(sec, {}).get(k, d)
                return st.session_state.edit_pr_data.get(k, d)

            t1, t2, t3, t4, t5 = st.tabs(["On-Course", "Driving", "Scoring", "Short Game", "Putting"])
            with t1:
                pr_h = st.radio("Holes", [9, 18], index=0 if gv(None, "holes", 9)==9 else 1)
                pr_gr = st.number_input("Gross Score", value=gv(None, "gross_score", 72))
                pr_tp = st.number_input("Score to Par", value=gv(None, "score_to_par", 0))
                pr_gir = st.number_input("GIR", value=gv(None, "gir", 9))
                pr_g5 = st.number_input("GIR Inside 5m", value=gv(None, "gir5", 4))
            with t2:
                pr_fw = st.number_input("Fairways Hit", value=gv("driving", "fw", 7))
                pr_tee = st.number_input("Tee Shots", value=gv("driving", "tee", 14))
            with t3:
                s1 = st.number_input("150-200 (To Par)", value=gv("scoring", "szl", 0))
                s2 = st.number_input("100-150 (To Par)", value=gv("scoring", "szm", 0))
                s3 = st.number_input("50-100 (To Par)", value=gv("scoring", "szs", 0))
            with t4:
                sg_t = st.number_input("Total SG Shots", value=gv("short_game", "tot", 8))
                sg_u = st.number_input("Up & Downs", value=gv("short_game", "ud", 4))
                sg_6 = st.number_input("Inside 6ft", value=gv("short_game", "s6", 3))
                sg_3 = st.number_input("Inside 3ft", value=gv("short_game", "s3", 1))
            with t5:
                p_putts = st.number_input("Total Putts", value=gv("putting", "pts", 30))
                p_sg = st.number_input("Strokes Gained Putting", value=float(gv("putting", "sg", 0.0)))
                p_lag_t = st.number_input("Total Lag Putts (18ft+)", value=gv("putting", "lt", 6))
                p_lag_s = st.number_input("Lags inside putter length", value=gv("putting", "ls", 5))

            if st.button("💾 Save Practice Round", type="primary", use_container_width=True):
                payload = {
                    "holes": pr_h, "gross_score": pr_gr, "score_to_par": pr_tp, "gir": pr_gir, "gir5": pr_g5,
                    "driving": {"fw": pr_fw, "tee": pr_tee},
                    "scoring": {"szl": s1, "szm": s2, "szs": s3},
                    "short_game": {"tot": sg_t, "ud": sg_u, "s6": sg_6, "s3": sg_3},
                    "putting": {"pts": p_putts, "sg": p_sg, "lt": p_lag_t, "ls": p_lag_s}
                }
                data = {"user_name": st.session_state.current_user, "game_category": "Practice Rounds", "game_name": pr_game, "score_primary": pr_tp, "raw_data": payload, "week_number": current_week}
                if st.session_state.edit_pr_id:
                    supabase.table("practice_logs").update(data).eq("id", st.session_state.edit_pr_id).execute()
                else:
                    supabase.table("practice_logs").insert(data).execute()
                st.session_state.mode_pr = "grid"
                st.rerun()


    # --- PAGE: DRIVING ---
    elif st.session_state.page == "Driving":
        st.title("🚀 Driving Combine")
        dg = st.radio("Select Drill:", ["10 Shot", "Max SS/BS"], horizontal=True, key="drv_rad_master")
        df_sub = df_logs[df_logs['game_name'] == dg]
        if st.button("➕ New Entry", key=f"new_drv_{dg}"):
            sc = st.number_input("Score", value=0.0)
            if st.button("Save", key="sav_drv_btn"):
                d = {"user_name": st.session_state.current_user, "game_category": "Driving", "game_name": dg, "score_primary": sc, "week_number": current_week}
                supabase.table("practice_logs").insert(d).execute()
                st.rerun()
        st.divider()
        render_icon_grid(df_sub, dg)

    # --- PAGE: SCORING ZONES ---
    elif st.session_state.page in ["Scoring Zone Long", "Scoring Zone Mid", "Scoring Zone Short"]:
        cat = st.session_state.page
        st.title(f"🎯 {cat}")
        dist = {"Scoring Zone Long": "150-200", "Scoring Zone Mid": "100-150", "Scoring Zone Short": "50-100"}[cat]
        sit_label = f"Situational Practice {dist}"
        tm_label = f"TM {dist}"
        st.write(f"*{dist} amount of random shots. 30% from non-fairway lies.*")
        sg = st.radio("Drill:", [sit_label, tm_label], horizontal=True, key=f"rad_{cat}")
        df_sub = df_logs[df_logs['game_name'] == sg]
        if st.button("➕ New Entry", key=f"new_{cat}"):
            sc = st.number_input("Average to Par", value=0.0)
            if st.button("Save", key=f"sav_{cat}"):
                d = {"user_name": st.session_state.current_user, "game_category": cat, "game_name": sg, "score_primary": sc, "week_number": current_week}
                supabase.table("practice_logs").insert(d).execute()
                st.rerun()
        st.divider()
        render_icon_grid(df_sub, sg)

    # --- PAGE: SHORT GAME ---
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
        sg_game = st.radio("Drill:", ["Par 21 WB", "20 to 50", "6ft Game"], horizontal=True, key="sg_combine_rad")
        df_sub = df_logs[df_logs['game_name'] == sg_game]
        if st.button("➕ New Entry", key=f"new_sg_{sg_game}"):
            sc = st.number_input("Score", value=0.0)
            if st.button("Save", key="sav_sg_btn"):
                d = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": sg_game, "score_primary": sc, "week_number": current_week}
                supabase.table("practice_logs").insert(d).execute()
                st.rerun()
        st.divider()
        render_icon_grid(df_sub, sg_game)

    # --- PAGE: PUTTING ---
    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
        pt_game = st.radio("Drill:", ["Pace", "6-9-12", "2-8 Drill"], horizontal=True, key="pt_combine_rad")
        df_sub = df_logs[df_logs['game_name'] == pt_game]
        if st.button("➕ New Entry", key=f"new_pt_{pt_game}"):
            sc = st.number_input("Score", value=0.0)
            if st.button("Save", key="sav_pt_btn"):
                d = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": pt_game, "score_primary": sc, "week_number": current_week}
                supabase.table("practice_logs").insert(d).execute()
                st.rerun()
        st.divider()
        render_icon_grid(df_sub, pt_game)


    # --- PAGE: YOUR PRACTICE TRENDS ---
    elif st.session_state.page == "Your Practice Trends":
        st.title("📈 Your Practice Trends")
        st.write("*Detailed analytics engine is initializing... Head back to Dashboard to see your weekly summary.*")
        
        # Sample placeholder chart logic
        if not df_logs.empty:
            chart_data = df_logs.groupby('week_number')['score_primary'].mean().reset_index()
            c = alt.Chart(chart_data).mark_line(point=True).encode(x='week_number:N', y='score_primary:Q')
            st.altair_chart(c, use_container_width=True)
        else:
            st.info("Log some practice to see trends!")

# ==========================================
# END OF SCRIPT
# ==========================================
