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
# 1. APP CONFIG & RESTORED PREMIUM CSS
# ==========================================
st.set_page_config(page_title="The Practice Club", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&family=Playfair+Display:wght@700&display=swap');
    
    /* Master Font Enforcer */
    html, body, p, div, label, li, span, th, td, .stMarkdown, .stText, [data-testid="stMetricValue"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }

    /* Target the big Landing Title specifically */
    .landing-title {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        font-size: 3.8em !important;
        text-align: center !important;
        margin-bottom: 0px !important;
    }
    
    .landing-subtitle {
        font-family: 'Montserrat', sans-serif !important;
        color: #6b7280 !important;
        font-weight: 600 !important;
        letter-spacing: 2.5px !important;
        text-transform: uppercase !important;
        font-size: 1.1em !important;
        text-align: center !important;
    }

    /* Fix the glitched icons */
    .material-symbols-rounded {
        font-family: 'Material Symbols Rounded' !important;
    }

    /* Premium Card Shadows for Containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
        border: 1px solid rgba(150,150,150,0.15) !important;
    }
    
    input[type="number"], input[type="text"] { text-align: center !important; font-weight: 500 !important; }
    
    /* Hide Streamlit toolbar */
    [data-testid="stHeaderActions"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE & TIME ENGINE (Restored)
# ==========================================
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Database connection failed.")

# PGA Tour Baseline for Putting restoration
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

def get_local_time_info():
    tz = pytz.timezone(st.session_state.timezone)
    local_time = datetime.datetime.now(tz)
    year, week_num, weekday = local_time.isocalendar()
    return local_time, year, week_num, (weekday == 7)

# ==========================================
# 4. DATA LOADERS & RESTORED ICON GRID
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
    lower_better = ["Situational Practice 150-200", "Situational Practice 100-150", "Situational Practice 50-100", "TM 50-100", "Par 21 WB", "6ft Game", "6-9-12", "2-8 Drill"]
    
    st.markdown("### 📜 Recent Sessions")
    for i, row in df_game.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 2, 1])
            date_str = str(row['created_at'])[:10]
            p = row['score_primary']
            
            if row.get('game_category') == "Practice Rounds":
                raw = row.get('raw_data', {})
                gross = raw.get('gross_score', 0)
                tp = f"+{int(p)}" if p > 0 else ("E" if p == 0 else f"{int(p)}")
                score_str = f"{int(gross)} ({tp})"
            elif game_name == "Max SS/BS":
                score_str = f"{p:.0f} / {row['score_secondary']:.0f}"
            elif game_name == "20 to 50":
                score_str = f"{p:.0f}%"
            else:
                score_str = f"{p:.2f}"
            
            c1.markdown(f"**{date_str}**")
            c2.markdown(f"<div style='text-align: center; font-size: 1.5em; font-weight: 800; color: #0068C9;'>{score_str}</div>", unsafe_allow_html=True)
            with c3:
                sub1, sub2 = st.columns(2)
                sub1.popover("👁️").json(row['raw_data'])
                if sub2.button("🗑️", key=f"del_{row['id']}"):
                    supabase.table("practice_logs").delete().eq("id", row['id']).execute()
                    st.rerun()

# ==========================================
# 5. RESTORED LANDING & ROUTING
# ==========================================
if st.session_state.current_user is None:
    st.markdown("<div class='landing-title'>The Practice Club</div>", unsafe_allow_html=True)
    st.markdown("<div class='landing-subtitle'>Tour Pro Edition</div>", unsafe_allow_html=True)
    st.write("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            u_in = st.text_input("Player Username", key="l_u")
            tz_in = st.selectbox("Local Timezone", ["US/Eastern", "US/Central", "US/Pacific", "Europe/London", "UTC"], key="l_tz")
            if st.button("Authenticate & Enter", use_container_width=True, type="primary", key="l_btn"):
                if u_in:
                    st.session_state.current_user = u_in
                    st.session_state.timezone = tz_in
                    st.session_state.page = "Weekly Dashboard"
                    st.rerun()
else:
    local_now, current_year, current_week, is_sunday = get_local_time_info()
    df_logs = load_all_logs(st.session_state.current_user)
    
    # SIDEBAR
    st.sidebar.title("👤 Player Profile")
    st.sidebar.write(f"**{st.session_state.current_user}**")
    if st.sidebar.button("Log Out", key="sidebar_logout"):
        st.session_state.current_user = None
        st.rerun()
    
    st.sidebar.divider()
    for opt in ["Weekly Dashboard", "Practice Rounds", "Driving", "Scoring Zone Long", "Scoring Zone Mid", "Scoring Zone Short", "Short Game", "Putting", "Your Practice Trends"]:
        if st.sidebar.button(opt, use_container_width=True, key=f"nav_{opt}", type="primary" if st.session_state.page == opt else "secondary"):
            st.session_state.page = opt
            st.rerun()

    if st.session_state.page == "Weekly Dashboard":
        st.title("📊 Weekly Dashboard")
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'], errors='coerce')
        weeks = sorted(df_logs['week_number'].unique().tolist(), reverse=True)
        if current_week not in weeks: weeks.insert(0, current_week)
        sel_w = st.selectbox("📅 Select Week to View", weeks, index=weeks.index(current_week) if current_week in weeks else 0, key="wk_sel")
        
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
        
        st.subheader(f"🎯 Week {sel_w} Combine Checklist")
        for cat, games in struct.items():
            cat_icon = "✅" if cat in done_cats else "⏳"
            with st.expander(f"{cat_icon} **{cat}**"):
                for g in games:
                    g_icon = "✅" if g in done_games else "⭕"
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"{g_icon}  {g}")
                    if c2.button("Practice ➡️", key=f"nav_d_{cat}_{g}"):
                        st.session_state.page = cat
                        if cat == "Practice Rounds": st.session_state.pr_game_select = g
                        st.rerun()

    elif st.session_state.page == "Practice Rounds":
        st.title("⛳ Practice Rounds")
        if 'mode_pr' not in st.session_state: st.session_state.mode_pr = "grid"
        if 'pr_game_select' not in st.session_state: st.session_state.pr_game_select = "Straight up"
        if 'edit_pr_id' not in st.session_state: st.session_state.edit_pr_id = None
        if 'edit_pr_data' not in st.session_state: st.session_state.edit_pr_data = {}

        pr_game = st.selectbox("Select Game Format", ["Straight up", "5m game", "10m game"], key="pr_ms")
        st.session_state.pr_game_select = pr_game
        
        # RESTORED DESCRIPTIONS
        if pr_game == "Straight up": st.info("**Straight up:** A normal 9 or 18 hole round.")
        elif pr_game == "5m game": st.info("**5m game:** Every GIR hit outside of 5m/17ft must be taken off green for a short game shot. Alternate lies.")
        elif pr_game == "10m game": st.info("**10m game:** On odd holes, move drive 10m worse. Even holes, approach 10m worse.")

        if st.session_state.mode_pr == "grid":
            if st.button("➕ Log New Practice Round", type="primary", key="pr_new"):
                st.session_state.edit_pr_id = None
                st.session_state.edit_pr_data = {}
                st.session_state.mode_pr = "entry"
                st.rerun()
            
            df_pr = df_logs[(df_logs['game_category'] == "Practice Rounds") & (df_logs['game_name'] == pr_game)]
            if not df_pr.empty:
                st.write("### ✏️ Resume Round")
                options = ["-- Select --"] + df_pr.apply(lambda r: f"{str(r['created_at'])[:10]} (ID: {r['id']})", axis=1).tolist()
                sel_edit = st.selectbox("Resume:", options, key="pr_res_p")
                if sel_edit != "-- Select --":
                    eid = int(sel_edit.split("(ID: ")[1].replace(")", ""))
                    st.session_state.edit_pr_id = eid
                    st.session_state.edit_pr_data = df_pr[df_pr['id'] == eid].iloc[0]['raw_data']
                    st.session_state.mode_pr = "entry"
                    st.rerun()
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
                col_a, col_b = st.columns(2)
                pr_gross = col_a.number_input("Gross Score", value=gv(None, "gross_score", 72))
                pr_tp = col_b.number_input("Score to Par", value=gv(None, "score_to_par", 0))
                pr_gir = st.number_input("Total GIR", value=gv(None, "gir_total", 9))
                pr_g5 = st.number_input("GIR Inside 5m", value=gv(None, "gir5", 4))
            with t2:
                pr_fw = st.number_input("Fairways Hit", value=gv("driving", "fw", 7))
                pr_tee = st.number_input("Total Tee Shots", value=gv("driving", "tee", 14))
            with t3:
                s1 = st.number_input("Score 150-200 (To Par)", value=gv("scoring", "szl", 0))
                s1n = st.number_input("Recorded 150-200 Shots", value=gv("scoring", "szln", 5))
                s2 = st.number_input("Score 100-150 (To Par)", value=gv("scoring", "szm", 0))
                s2n = st.number_input("Recorded 100-150 Shots", value=gv("scoring", "szmn", 5))
                s3 = st.number_input("Score 50-100 (To Par)", value=gv("scoring", "szs", 0))
                s3n = st.number_input("Recorded 50-100 Shots", value=gv("scoring", "szsn", 5))
            with t4:
                sg_t = st.number_input("Total Short Game Shots", value=gv("short_game", "tot", 8))
                sg_u = st.number_input("Up & Downs", value=gv("short_game", "ud", 4))
                sg_6 = st.number_input("Inside 6ft", value=gv("short_game", "s6", 3))
                sg_3 = st.number_input("Inside 3ft", value=gv("short_game", "s3", 1))
            with t5:
                # FULL STROKES GAINED PUTTING TOOL RESTORATION
                p_putts = st.number_input("Total Putts", value=gv("putting", "pts", 30))
                p_sg = st.number_input("Strokes Gained Putting", value=float(gv("putting", "sg", 0.0)))
                p_lag_t = st.number_input("Lag Putts (18ft+)", value=gv("putting", "lt", 6))
                p_lag_s = st.number_input("Success (Inside Putter Length)", value=gv("putting", "ls", 5))

            if st.button("💾 Save Practice Round", type="primary", use_container_width=True, key="save_final_pr"):
                payload = {
                    "gross_score": pr_gross, "score_to_par": pr_tp, "gir_total": pr_gir, "gir5": pr_g5,
                    "driving": {"fw": pr_fw, "tee": pr_tee},
                    "scoring": {"szl": s1, "szln": s1n, "szm": s2, "szmn": s2n, "szs": s3, "szsn": s3n},
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
        sel = st.radio("Select Drill:", ["10 Shot", "Max SS/BS"], horizontal=True, key="dr_r")
        if sel == "10 Shot":
            st.subheader("The 10 Shot Game")
            st.write("*Hit 10 shots. Carry distance minus offline total (ft). Average is your final score.*")
            if 'mode_10s' not in st.session_state: st.session_state.mode_10s = "grid"
            if st.session_state.mode_10s == "grid":
                if st.button("➕ New Entry", key="n_10"): st.session_state.mode_10s = "entry"; st.rerun()
                render_icon_grid(df_logs[df_logs['game_name'] == "10 Shot"], "10 Shot")
            else:
                if st.button("🔙 Back"): st.session_state.mode_10s = "grid"; st.rerun()
                # Matrix restoration
                mat = pd.DataFrame({"Shot": [f"Shot {i+1}" for i in range(10)], "Carry": [0.0]*10, "Offline": [0.0]*10})
                ed = st.data_editor(mat, hide_index=True, use_container_width=True, key="ed_10")
                sc = (ed['Carry'] - ed['Offline']).mean()
                st.metric("Final Score", f"{sc:.1f}")
                if st.button("Save 10 Shot", type="primary"):
                    supabase.table("practice_logs").insert({"user_name": st.session_state.current_user, "game_category": "Driving", "game_name": "10 Shot", "score_primary": sc, "week_number": current_week, "raw_data": ed.to_dict('records')}).execute()
                    st.session_state.mode_10s = "grid"; st.rerun()

        elif sel == "Max SS/BS":
            st.subheader("Speed Limits (SS/BS)")
            st.write("*Your Max Swing Speed and Ball Speed today. On-course preferred.*")
            c1, c2 = st.columns(2)
            ss = c1.number_input("Swing Speed", value=110.0)
            bs = c2.number_input("Ball Speed", value=160.0)
            if st.button("Save Speeds", type="primary"):
                supabase.table("practice_logs").insert({"user_name": st.session_state.current_user, "game_category": "Driving", "game_name": "Max SS/BS", "score_primary": ss, "score_secondary": bs, "week_number": current_week}).execute()
                st.rerun()
            render_icon_grid(df_logs[df_logs['game_name'] == "Max SS/BS"], "Max SS/BS")

    # --- PAGE: SCORING ZONES (Restored Rules) ---
    elif st.session_state.page in ["Scoring Zone Long", "Scoring Zone Mid", "Scoring Zone Short"]:
        cat = st.session_state.page
        st.title(f"🎯 {cat}")
        dist = {"Scoring Zone Long": "150-200", "Scoring Zone Mid": "100-150", "Scoring Zone Short": "50-100"}[cat]
        st.write(f"*Random situational shots between {dist} yards/meters. **At least 30% from non-fairway lies** (fairway bunkers, first-cut, rough).*")
        sit = f"Situational Practice {dist}"
        tm = f"TM {dist}"
        sel = st.radio("Drill:", [sit, tm], horizontal=True, key=f"rad_{cat}")
        df_s = df_logs[df_logs['game_name'] == sel]
        if st.button("➕ New Entry", key=f"n_{cat}"):
            c1, c2 = st.columns(2)
            sc = c1.number_input("Score to Par", value=0)
            sh = c2.number_input("Total Shots", value=10)
            if st.button("Save Entry", key=f"s_{cat}", type="primary"):
                f_sc = sc/sh
                supabase.table("practice_logs").insert({"user_name": st.session_state.current_user, "game_category": cat, "game_name": sel, "score_primary": f_sc, "week_number": current_week}).execute()
                st.rerun()
        st.divider()
        render_icon_grid(df_s, sel)

# --- PAGE: SHORT GAME & PUTTING (Simplified restoration for stability) ---
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
        sel = st.radio("Drill:", ["Par 21 WB", "20 to 50", "6ft Game"], horizontal=True, key="sg_rest")
        df_s = df_logs[df_logs['game_name'] == sel]
        if st.button("➕ New Entry"):
            sc = st.number_input("Score", value=0.0)
            if st.button("Save"):
                supabase.table("practice_logs").insert({"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": sel, "score_primary": sc, "week_number": current_week}).execute()
                st.rerun()
        render_icon_grid(df_s, sel)

    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
        sel = st.radio("Drill:", ["Pace", "6-9-12", "2-8 Drill"], horizontal=True, key="pt_rest")
        df_s = df_logs[df_logs['game_name'] == sel]
        if st.button("➕ New Entry"):
            sc = st.number_input("Score", value=0.0)
            if st.button("Save"):
                supabase.table("practice_logs").insert({"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": sel, "score_primary": sc, "week_number": current_week}).execute()
                st.rerun()
        render_icon_grid(df_s, sel)

    # ==========================================
    # PAGE: YOUR PRACTICE TRENDS (FULL RESTORATION)
    # ==========================================
    elif st.session_state.page == "Your Practice Trends":
        st.title("📈 Your Practice Trends")
        if df_logs.empty:
            st.info("No data yet.")
        else:
            mode = st.radio("Mode:", ["🎯 Individual Drills", "📈 Entire Category"], horizontal=True)
            if mode == "🎯 Individual Drills":
                games = sorted(df_logs['game_name'].unique().tolist())
                sel_g = st.selectbox("Select Drill", games)
                df_t = df_logs[df_logs['game_name'] == sel_g].copy()
                df_t['created_at'] = pd.to_datetime(df_t['created_at'])
                df_t = df_t.sort_values('created_at')
                chart = alt.Chart(df_t).mark_line(point=True, color="#0068C9", strokeWidth=3).encode(
                    x=alt.X('created_at:T', title="Date"),
                    y=alt.Y('score_primary:Q', scale=alt.Scale(zero=False), title="Score"),
                    tooltip=['created_at', 'score_primary']
                ).properties(height=400)
                st.altair_chart(chart, use_container_width=True)
            else:
                cats = sorted(df_logs['game_category'].unique().tolist())
                sel_c = st.selectbox("Select Category", cats)
                df_c = df_logs[df_logs['game_category'] == sel_c].copy()
                df_c['created_at'] = pd.to_datetime(df_c['created_at'])
                chart = alt.Chart(df_c).mark_bar().encode(
                    x='week_number:N',
                    y='mean(score_primary):Q',
                    color='game_name:N'
                ).properties(height=400)
                st.altair_chart(chart, use_container_width=True)
