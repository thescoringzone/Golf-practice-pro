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
    
    /* Master Font Enforcer */
    html, body, p, div, label, li, span, th, td, .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, [data-testid="stMetricValue"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    
    .material-symbols-rounded, .stIcon, [data-testid="stIconMaterial"], i, svg {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    [data-testid="stVegaLiteChart"], canvas { 
        pointer-events: none !important; 
    }
    
    input[type="number"], input[type="text"] { 
        text-align: center !important; 
        font-weight: 500 !important;
    }

    /* Fix for overlapping text in the Dashboard expanders */
    [data-testid="stExpander"] div[role="button"] p {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    
    /* Premium Card Shadows for Containers and Grids */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
        border: 1px solid rgba(150,150,150,0.15) !important;
    }
    
    /* Subtle button hover effects */
    .stButton > button {
        border-radius: 8px !important;
        transition: all 0.2s ease;
        font-weight: 600 !important;
    }

    /* Hide the Streamlit top-right developer toolbar */
    [data-testid="stHeaderActions"] {
        display: none !important;
    }
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

if 'driving_radio' not in st.session_state: st.session_state.driving_radio = "10 Shot"
if 'szl_radio' not in st.session_state: st.session_state.szl_radio = "Situational Practice 150-200"
if 'szm_radio' not in st.session_state: st.session_state.szm_radio = "Situational Practice 100-150"
if 'szs_radio' not in st.session_state: st.session_state.szs_radio = "Situational Practice 50-100"
if 'sg_radio' not in st.session_state: st.session_state.sg_radio = "Par 21 WB"
if 'putt_radio' not in st.session_state: st.session_state.putt_radio = "Pace"
if 'pr_game_select' not in st.session_state: st.session_state.pr_game_select = "Straight up"

def get_local_time_info():
    tz = pytz.timezone(st.session_state.timezone)
    local_time = datetime.datetime.now(tz)
    year, week_num, weekday = local_time.isocalendar()
    is_sunday = (weekday == 7)
    return local_time, year, week_num, is_sunday

# ==========================================
# 4. DATA LOADER & ICON GRID HELPER
# ==========================================
def load_all_logs(username):
    response = supabase.table("practice_logs").select("*").eq("user_name", username).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        
        if 'raw_data' in df.columns:
            df['raw_data'] = df['raw_data'].apply(lambda x: x if isinstance(x, dict) else (json.loads(x) if isinstance(x, str) else {}))
            
        # --- CREATIVE WORKAROUND: THE AUTO-TRANSLATOR ---
        # 1. Fix old Practice Round categories 
        if 'game_category' in df.columns:
            df['game_category'] = df['game_category'].replace({"On-Course": "Practice Rounds"})
            
        # 2. Broadly sweep and rename legacy games
        if 'game_name' in df.columns:
            # This fixes the old Situational games
            df['game_name'] = df['game_name'].apply(lambda x: str(x).replace('On-Course', 'Situational Practice') if isinstance(x, str) else x)
            # This instantly converts your old 2-8 Drill data into 2-7 Drill data
            df['game_name'] = df['game_name'].replace({"2-8 Drill": "2-7 Drill"})
            
        return df
    else:
        return pd.DataFrame(columns=[
            "id", "created_at", "user_name", "game_category", "game_name", 
            "score_primary", "score_secondary", "raw_data", "week_number"
        ])

def render_icon_grid(df_game, game_name):
    if df_game.empty:
        st.info("No practice sessions logged yet. Click 'New Entry' to start.")
        return

    df_game = df_game.sort_values('created_at', ascending=False).reset_index(drop=True)
    lower_is_better = ["Situational Practice 150-200", "Situational Practice 100-150", "Situational Practice 50-100", "TM 50-100", "Par 21 WB", "6ft Game", "6-9-12", "2-7 Drill"]

    st.markdown("### 📜 Recent Sessions")
    
    for i, row in df_game.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            try:
                dt = datetime.datetime.fromisoformat(str(row['created_at']).replace('Z', '+00:00'))
                date_str = dt.strftime("%b %d, %Y")
            except:
                date_str = str(row['created_at'])[:10]
                
            score_val = row['score_primary']
            score_str = ""
            delta_str = ""
            delta_color = "gray"
            
            if i < len(df_game) - 1:
                prev_score = df_game.iloc[i+1]['score_primary']
                diff = score_val - prev_score
                
                if game_name != "Max SS/BS" and row.get('game_category') != "Practice Rounds":
                    if diff > 0:
                        delta_str = f"📈 +{diff:.1f}" if game_name not in ["20 to 50", "Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-8 Drill", "6-9-12"] else f"📈 +{int(diff)}"
                        delta_color = "#dc3545" if game_name in lower_is_better else "#28a745"
                    elif diff < 0:
                        delta_str = f"📉 {diff:.1f}" if game_name not in ["20 to 50", "Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-8 Drill", "6-9-12"] else f"📉 {int(diff)}"
                        delta_color = "#28a745" if game_name in lower_is_better else "#dc3545"
                    else:
                        delta_str = "➖ Even"
                        delta_color = "gray"

            if game_name == "Max SS/BS": 
                score_str = f"{row['score_primary']:.0f} / {row['score_secondary']:.0f}"
            elif game_name in ["20 to 50"]: 
                score_str = f"{row['score_primary']:.0f}%" 
                if delta_str and "Even" not in delta_str: delta_str += "%"
            elif game_name in ["Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-7 Drill", "6-9-12", "Green Reading"]: 
                score_str = f"{row['score_primary']:.0f}" 
            elif row.get('game_category') == "Practice Rounds":
                raw = row.get('raw_data', {})
                gross = raw.get('gross_score', 0) if isinstance(raw, dict) else 0
                to_par_str = f"+{int(score_val)}" if score_val > 0 else ("E" if score_val == 0 else f"{int(score_val)}")
                score_str = f"{int(gross)} ({to_par_str})"
            else: 
                score_str = f"{row['score_primary']:.2f}" 

            col1.markdown(f"**{date_str}**<br><span style='color:{delta_color}; font-weight: 600; font-size:0.9em;'>{delta_str}</span>", unsafe_allow_html=True)
            col2.markdown(f"<div style='text-align: center; font-size: 1.5em; font-weight: 800; color: #0068C9;'>{score_str}</div>", unsafe_allow_html=True)
            
            with col3:
                action_c1, action_c2 = st.columns(2)
                with action_c1.popover("👁️"):
                    st.markdown("**Session Data:**")
                    if isinstance(row.get('raw_data'), list) and len(row.get('raw_data', [])) > 0:
                        df_view = pd.DataFrame(row['raw_data'])
                        st.dataframe(df_view, hide_index=True, use_container_width=True)
                    elif isinstance(row.get('raw_data'), dict) and len(row.get('raw_data', {})) > 0:
                        st.json(row['raw_data'])
                    else:
                        st.write(f"**Score:** {score_str}")
                        st.caption("Manual entry game.")
                
                with action_c2.popover("🗑️"):
                    st.markdown("**Delete?**")
                    if st.button("Yes", key=f"del_{row['id']}", type="primary", use_container_width=True):
                        supabase.table("practice_logs").delete().eq("id", row['id']).execute()
                        st.rerun()

def render_on_course_performance(category):
    st.write(f"*These statistics are automatically aggregated from your logged **Practice Rounds**.*")
    
    # Pull all practice rounds
    pr_df = df_logs[df_logs['game_category'] == "Practice Rounds"]
    
    if pr_df.empty: 
        st.info("No Practice Rounds logged yet. Head over to the Practice Rounds page to log your first round!")
        if st.button("➡️ Go to Practice Rounds", key=f"go_pr_empty_{category}", type="primary"):
            st.session_state.page = "Practice Rounds"
            st.rerun()
        return
        
    # Safely extract the raw data dicts
    raw_list = [r for r in pr_df['raw_data'].tolist() if isinstance(r, dict)]
    if not raw_list: return
    
    st.write("<br>", unsafe_allow_html=True)
    
    if category == "Driving":
        fw = sum(r.get('driving', {}).get('fairways_hit', 0) for r in raw_list)
        tee = sum(r.get('driving', {}).get('tee_shots', 0) for r in raw_list)
        acc = (fw / tee * 100) if tee > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Fairways Hit", fw)
        c2.metric("Total Tee Shots", tee)
        c3.metric("FW Accuracy", f"{acc:.0f}%")
        
    elif category == "Scoring Zone Long":
        s = sum(r.get('scoring_zone', {}).get('szl_score', 0) for r in raw_list)
        n = sum(r.get('scoring_zone', {}).get('szl_shots', 0) for r in raw_list)
        avg = s/n if n > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Total Score to Par (150-200)", f"{'+' if s>0 else ''}{s}")
        c2.metric("Avg Strokes vs Par", f"{'+' if avg>0 else ''}{avg:.2f}")

    elif category == "Scoring Zone Mid":
        s = sum(r.get('scoring_zone', {}).get('szm_score', 0) for r in raw_list)
        n = sum(r.get('scoring_zone', {}).get('szm_shots', 0) for r in raw_list)
        avg = s/n if n > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Total Score to Par (100-150)", f"{'+' if s>0 else ''}{s}")
        c2.metric("Avg Strokes vs Par", f"{'+' if avg>0 else ''}{avg:.2f}")

    elif category == "Scoring Zone Short":
        s = sum(r.get('scoring_zone', {}).get('szs_score', 0) for r in raw_list)
        n = sum(r.get('scoring_zone', {}).get('szs_shots', 0) for r in raw_list)
        avg = s/n if n > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Total Score to Par (50-100)", f"{'+' if s>0 else ''}{s}")
        c2.metric("Avg Strokes vs Par", f"{'+' if avg>0 else ''}{avg:.2f}")

    elif category == "Short Game":
        tot = sum(r.get('short_game', {}).get('total_shots', 0) for r in raw_list)
        ud = sum(r.get('short_game', {}).get('up_and_downs', 0) for r in raw_list)
        in6 = sum(r.get('short_game', {}).get('inside_6ft', 0) for r in raw_list)
        in3 = sum(r.get('short_game', {}).get('inside_3ft', 0) for r in raw_list)
        
        scr_pct = (ud / tot * 100) if tot > 0 else 0
        in6_pct = (in6 / tot * 100) if tot > 0 else 0
        in3_pct = (in3 / tot * 100) if tot > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Scrambling (Up & Down)", f"{scr_pct:.0f}%")
        c2.metric("Shots Inside 6ft", f"{in6_pct:.0f}%")
        c3.metric("Shots Inside 3ft", f"{in3_pct:.0f}%")

    elif category == "Putting":
        normalized_putts_list = []
        sgp = 0.0
        lt = 0
        ls = 0
        
        for r in raw_list:
            putts = r.get('putting', {}).get('total_putts', 0)
            if putts > 0:
                # Check if it was a 9 or 18 hole round (default to 18 just in case)
                holes = r.get('holes_played', 18) 
                
                # Normalize 9-hole rounds to 18-hole equivalents
                if holes == 9:
                    normalized_putts_list.append(putts * 2)
                else:
                    normalized_putts_list.append(putts)
                
                sgp += r.get('putting', {}).get('sg_putting', 0.0)
                lt += r.get('putting', {}).get('lag_putts_total', 0)
                ls += r.get('putting', {}).get('lag_putts_success', 0)
                
        rounds = len(normalized_putts_list)
        avg_putts_18 = sum(normalized_putts_list) / rounds if rounds > 0 else 0
        lag_pct = (ls / lt * 100) if lt > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg SG Putting (per round)", f"{(sgp/rounds):+.2f}" if rounds > 0 else "0.00")
        c2.metric("Avg Putts (per 18)", f"{avg_putts_18:.1f}")
        c3.metric("Lag Putting Success", f"{lag_pct:.0f}%")
        
    st.divider()
    if st.button("➕ Log More On-Course Data", key=f"nav_to_pr_{category}", type="primary"):
        st.session_state.page = "Practice Rounds"
        st.session_state.mode_pr = "entry"
        st.rerun()

# ==========================================
# 5. ROUTING: LOGIN GATE
# ==========================================
if st.session_state.page == "Login" or not st.session_state.current_user:
    st.markdown("<h1 style='text-align: center; font-size: 3.8em; font-weight: 800; margin-top: 5%; letter-spacing: -1px;'>The Practice Club</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #6b7280; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase; font-size: 1.1em;'>Tour Pro Edition</h3>", unsafe_allow_html=True)
    st.write("<br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            username_input = st.text_input("Player Username", placeholder="Enter username...", key="login_username").strip()
            common_tzs = ["US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "Europe/London", "Asia/Hong_Kong", "Australia/Sydney", "UTC"]
            selected_tz = st.selectbox("Your Local Timezone (For Weekly Reset)", common_tzs, index=0)
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("Authenticate & Enter", use_container_width=True, type="primary"):
                if username_input:
                    st.session_state.current_user = username_input
                    st.session_state.timezone = selected_tz
                    st.session_state.page = "Weekly Dashboard"
                    st.rerun()

# ==========================================
# 6. ROUTING: SECURE PLATFORM & SIDEBAR
# ==========================================
else:
    local_now, current_year, current_week, is_sunday = get_local_time_info()
    df_logs = load_all_logs(st.session_state.current_user)
    
    # -- SIDEBAR NAVIGATION --
    st.sidebar.title("👤 Player Profile")
    st.sidebar.write(f"**{st.session_state.current_user}**")
    st.sidebar.caption(f"Timezone: {st.session_state.timezone}")
    st.sidebar.caption(f"🗓️ **Week {current_week} of {current_year}**")
    
    if st.sidebar.button("Log Out", key="sidebar_logout_btn"):
        st.session_state.current_user = None
        st.session_state.page = "Login"
        st.rerun()
        
    st.sidebar.divider()
    st.sidebar.header("🧭 Navigation")
    
    nav_options = [
        "Weekly Dashboard", 
        "Practice Rounds", 
        "Driving", 
        "Scoring Zone Long", 
        "Scoring Zone Mid", 
        "Scoring Zone Short", 
        "Short Game", 
        "Putting", 
        "Your Practice Trends"
    ]
    
    for opt in nav_options:
        if st.sidebar.button(opt, key=f"nav_side_{opt}", use_container_width=True, type="primary" if st.session_state.page == opt else "secondary"):
            st.session_state.page = opt
            st.rerun()

    # --- SUNDAY WARNING ---
    if is_sunday:
        st.warning("⚠️ **Reminder: Today is Sunday!** Your Weekly Dashboard resets tonight at midnight.")

    # ==========================================
    # PAGE: WEEKLY DASHBOARD
    # ==========================================
    elif st.session_state.page == "Weekly Dashboard":
        st.title("📊 Weekly Dashboard")
        st.write("Track your practice completion and download your weekly reports.")
        
        # --- CREATIVE WORKAROUND: DYNAMIC TIME ENGINE ---
        # We ignore Supabase's saved 'week_number' entirely to avoid timezone bugs.
        # We force Pandas to calculate the True Week directly from the calendar date on the fly.
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'], errors='coerce', utc=True)
        df_logs['True_Week'] = df_logs['created_at'].dt.isocalendar().week.fillna(current_week).astype(int)
        df_logs['True_Year'] = df_logs['created_at'].dt.isocalendar().year.fillna(current_year).astype(int)
        
        logged_weeks = sorted(df_logs['True_Week'].unique().tolist(), reverse=True)
        if current_week not in logged_weeks:
            logged_weeks.insert(0, current_week)
            
        col_w1, col_w2 = st.columns([1, 3])
        selected_week = col_w1.selectbox("📅 Select Week to View", logged_weeks, index=logged_weeks.index(current_week), key="dash_week_selector")
        
        # Now we filter strictly by our bulletproof dynamic columns
        df_cw = df_logs[(df_logs['True_Week'] == selected_week) & (df_logs['True_Year'] == current_year)].copy()
        
        lw_week = selected_week - 1 if selected_week > 1 else 52
        lw_year = current_year if selected_week > 1 else current_year - 1
        df_lw = df_logs[(df_logs['True_Week'] == lw_week) & (df_logs['True_Year'] == lw_year)].copy()
        
        combine_structure = {
            "Practice Rounds": ["Straight up", "5m game", "10m game"],
            "Driving": ["10 Shot", "BS/SS"],
            "Scoring Zone Long": ["Situational Practice 150-200", "TM 150-200"],
            "Scoring Zone Mid": ["Situational Practice 100-150", "TM 100-150"],
            "Scoring Zone Short": ["Situational Practice 50-100", "TM 50-100"],
            "Short Game": ["Par 21wb", "20 to 50", "6ft Game"],
            "Putting": ["Pace", "6-9-12", "2-7 Drill", "Green Reading"]
        }

        completed_games = df_cw['game_name'].dropna().unique().tolist()
        completed_cats = df_cw['game_category'].dropna().unique().tolist()

        # Fuzzy Logic: Count categories that have ANY data logged
        completion_count = len([c for c in combine_structure.keys() if c in completed_cats])
        progress_pct = completion_count / len(combine_structure.keys())

        st.subheader(f"🎯 Week {selected_week} Combine Checklist")
        st.progress(progress_pct, text=f"Combine Completion: {completion_count} / {len(combine_structure.keys())} Categories")
        st.write("<br>", unsafe_allow_html=True)
        
        for cat, games in combine_structure.items():
            # Creative Workaround: If the category exists AT ALL in this week's data, it gets a check!
            is_cat_complete = cat in completed_cats
            
            with st.expander(f"{'✅' if is_cat_complete else '⏳'} **{cat}**"):
                for game in games:
                    # Creative Workaround: Substring matching to avoid invisible spacing errors
                    is_game_complete = any(game in str(cg) for cg in completed_games)
                    
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"{'✅' if is_game_complete else '⭕'} {game}")
                    if c2.button("➡️", key=f"nav_{cat}_{game}"):
                        st.session_state.page = cat
                        if cat == "Practice Rounds": st.session_state.pr_game_select = game
                        st.rerun()
                
        st.divider()
        
        st.subheader(f"📝 Week {selected_week} Logged Sessions")
        if df_cw.empty:
            st.info("No practice logged for this week.")
        else:
            df_cw_sort = df_cw.sort_values('created_at', ascending=False)
            
            def format_dashboard_score(row):
                gn = row.get('game_name', '')
                cat = row.get('game_category', '')
                p = row.get('score_primary', 0)
                if pd.isna(p): p = 0
                
                if cat == "Practice Rounds":
                    raw = row.get('raw_data', {})
                    if not isinstance(raw, dict): raw = {}
                    gross = raw.get('gross_score', 0)
                    to_par_str = f"+{int(p)}" if p > 0 else ("E" if p == 0 else f"{int(p)}")
                    return f"{int(gross)} ({to_par_str})"

                s = row.get('score_secondary', 0)
                if pd.isna(s): s = 0
                
                if gn == "Max SS/BS": return f"{p:.0f} / {s:.0f}"
                elif gn in ["20 to 50"]: return f"{p:.0f}%"
                elif gn in ["Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-7 Drill", "6-9-12", "Green Reading"]: return f"{p:.0f}"
                else: return f"{p:.2f}"
                
            df_display = df_cw_sort.copy()
            df_display['Score'] = df_display.apply(format_dashboard_score, axis=1)
            
            df_clean = df_display[['game_name', 'Score']]
            st.dataframe(df_clean, hide_index=True, use_container_width=True)
            
        st.divider()

        st.subheader("🧠 Weekly Reflections")
        st.write("*Jot down your thoughts. They will be formatted onto the right-side of your PDF report.*")
        col_ref1, col_ref2 = st.columns(2)
        learnings_input = col_ref1.text_area(f"Learnings for Week {selected_week}", placeholder="What did you figure out? What needs work?", height=120)
        successes_input = col_ref2.text_area(f"Successes for Week {selected_week}", placeholder="What went really well? Any PBs?", height=120)

        st.divider()

        # ==========================================
        # THE CADDIE REPORT (LANDSCAPE PDF)
        # ==========================================
        st.subheader("📄 Your Weekly Caddie Report")
        st.write(f"*Download your 1-page Landscape PDF summary for Week {selected_week}.*")
        
        report_data = []
        # UPDATED: Changed "Par 21 WB" to "Par 21wb"
        lower_is_better_games = ["Situational Practice 150-200", "Situational Practice 100-150", "Situational Practice 50-100", "TM 50-100", "Par 21wb", "6ft Game", "6-9-12", "2-7 Drill"]

        for cat, games in combine_structure.items():
            for game in games:
                cw_game = df_cw[df_cw['game_name'] == game]
                lw_game = df_lw[df_lw['game_name'] == game]
                
                if cw_game.empty:
                    report_data.append([cat, game, "-", "-", "-"])
                    continue
                    
                if cat == "Practice Rounds":
                    cw_avg = cw_game['score_primary'].mean()
                    cw_best = cw_game['score_primary'].min() 
                    
                    avg_str = f"{'+' if cw_avg > 0 else ''}{cw_avg:.1f}" if cw_avg != 0 else "E"
                    best_str = f"{'+' if cw_best > 0 else ''}{cw_best:.0f}" if cw_best != 0 else "E"
                    
                    pct_str = "-"
                    if not lw_game.empty:
                        lw_avg = lw_game['score_primary'].mean()
                        diff = cw_avg - lw_avg
                        pct_str = f"{-diff:+.1f} strks" 
                    report_data.append([cat, game, avg_str, best_str, pct_str])

                # UPDATED: Changed "Max SS/BS" to "BS/SS"
                elif game == "BS/SS":
                    cw_avg_ss, cw_avg_bs = cw_game['score_primary'].mean(), cw_game['score_secondary'].mean()
                    cw_best_ss, cw_best_bs = cw_game['score_primary'].max(), cw_game['score_secondary'].max()
                    avg_str, best_str = f"{cw_avg_ss:.0f}/{cw_avg_bs:.0f}", f"{cw_best_ss:.0f}/{cw_best_bs:.0f}"
                    pct_str = "-"
                    if not lw_game.empty:
                        lw_avg_ss = lw_game['score_primary'].mean()
                        denom_ss = lw_avg_ss if lw_avg_ss > 0 else 1.0
                        pct = ((cw_avg_ss - lw_avg_ss) / denom_ss) * 100
                        pct_str = f"{pct:+.1f}% (SS)"
                    report_data.append([cat, game, avg_str, best_str, pct_str])
                else:
                    cw_avg = cw_game['score_primary'].mean()
                    is_lower_better = game in lower_is_better_games
                    cw_best = cw_game['score_primary'].min() if is_lower_better else cw_game['score_primary'].max()
                    
                    if game in ["20 to 50"]: avg_str, best_str = f"{cw_avg:.0f}%", f"{cw_best:.0f}%"
                    # UPDATED: Changed "Par 21 WB" to "Par 21wb"
                    elif game in ["Par 21wb", "6ft Game", "TM 50-100", "Pace", "2-7 Drill", "6-9-12", "Green Reading"]: avg_str, best_str = f"{cw_avg:.0f}", f"{cw_best:.0f}"
                    else: avg_str, best_str = f"{cw_avg:.2f}", f"{cw_best:.2f}"
                        
                    pct_str = "-"
                    if not lw_game.empty:
                        lw_avg = lw_game['score_primary'].mean()
                        denom = abs(lw_avg) if lw_avg != 0 else 1.0 
                        pct = ((cw_avg - lw_avg) / denom) * 100
                        if is_lower_better: pct = -pct 
                        pct_str = f"{pct:+.1f}%"
                    report_data.append([cat, game, avg_str, best_str, pct_str])
                    
        df_report = pd.DataFrame(report_data, columns=["Category", "Drill", "Weekly Avg", "Weekly Best", "% Change"])

        def generate_pdf_report(df, week, year, username, l_text, s_text):
            class PDF(FPDF):
                def header(self):
                    self.set_y(8) 
                    self.set_font("Helvetica", "B", 18)
                    self.set_text_color(41, 55, 70) 
                    self.cell(0, 7, "THE PRACTICE CLUB", ln=True, align="C")
                    self.set_font("Helvetica", "I", 10)
                    self.set_text_color(100, 100, 100) 
                    self.cell(0, 5, f"Tour Pro Edition | Player: {username} | Week {week}, {year}", ln=True, align="C")
                    self.ln(3) 
                    
            pdf = PDF(orientation="L", unit="mm", format="A4")
            pdf.set_margins(10, 8, 10) 
            pdf.set_auto_page_break(auto=False)
            pdf.add_page()
            
            start_y = pdf.get_y()
            
            col_widths = [60, 30, 30, 30]
            headers = ["Drill", "Avg", "Best", "% Change"]
            current_category = ""
            
            for _, row in df.iterrows():
                pdf.set_x(10)
                if row["Category"] != current_category:
                    current_category = row["Category"]
                    pdf.ln(1.5) 
                    pdf.set_x(10)
                    
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_fill_color(41, 55, 70)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(150, 5.5, f"  {current_category.upper()}", border=1, ln=True, fill=True)
                    
                    pdf.set_x(10)
                    pdf.set_font("Helvetica", "B", 7)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_text_color(0, 0, 0)
                    for i in range(len(headers)):
                        pdf.cell(col_widths[i], 5, headers[i], border=1, align="C", fill=True)
                    pdf.ln()
                
                pdf.set_x(10)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(col_widths[0], 5, f"  {str(row['Drill'])}", border=1)
                pdf.cell(col_widths[1], 5, str(row['Weekly Avg']), border=1, align="C")
                pdf.cell(col_widths[2], 5, str(row['Weekly Best']), border=1, align="C")
                
                pct = str(row["% Change"])
                if "+" in pct: pdf.set_text_color(34, 139, 34)
                elif "-" in pct and pct != "-": pdf.set_text_color(220, 53, 69)
                pdf.cell(col_widths[3], 5, pct, border=1, align="C")
                pdf.set_text_color(0, 0, 0) 
                pdf.ln()

            table_end_y = pdf.get_y() 

            right_x = 165
            box_width = 120
            
            total_available_height = table_end_y - start_y
            box_height = max(20, (total_available_height - 18) / 2) 
            
            pdf.set_xy(right_x, start_y)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(41, 55, 70)
            pdf.cell(box_width, 7, "Learnings of the week", ln=1)
            
            box1_y = pdf.get_y()
            pdf.rect(right_x, box1_y, box_width, box_height)
            
            original_l_margin = pdf.l_margin
            pdf.set_left_margin(right_x + 2)
            pdf.set_xy(right_x + 2, box1_y + 2)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(box_width - 4, 4.5, str(l_text).strip() if l_text else "")
            
            pdf.set_left_margin(original_l_margin) 
            success_start_y = box1_y + box_height + 4 
            
            pdf.set_xy(right_x, success_start_y)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(41, 55, 70)
            pdf.cell(box_width, 7, "Successes of the week", ln=1)
            
            box2_y = pdf.get_y()
            pdf.rect(right_x, box2_y, box_width, box_height)
            
            pdf.set_left_margin(right_x + 2)
            pdf.set_xy(right_x + 2, box2_y + 2)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(box_width - 4, 4.5, str(s_text).strip() if s_text else "")
            
            pdf.set_left_margin(original_l_margin) 

            pdf.set_y(195)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 10, "The Practice Club - Tour Pro Edition", align="C")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                pdf.output(tmp.name)
                with open(tmp.name, "rb") as f:
                    return f.read()

        pdf_bytes = generate_pdf_report(df_report, selected_week, current_year, st.session_state.current_user, learnings_input, successes_input)
        st.download_button(
            label=f"📄 Download Week {selected_week} Landscape Report",
            data=pdf_bytes,
            file_name=f"The_Practice_Club_Week_{selected_week}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

    # ==========================================
    # PAGE: PRACTICE ROUNDS (THE MASTER FORM)
    # ==========================================
    elif st.session_state.page == "Practice Rounds":
        st.title("⛳ Practice Rounds")
        
        if 'mode_pr' not in st.session_state: st.session_state.mode_pr = "grid"
        if 'pr_game_select' not in st.session_state: st.session_state.pr_game_select = "Straight up"
        if 'edit_pr_id' not in st.session_state: st.session_state.edit_pr_id = None
        if 'edit_pr_data' not in st.session_state: st.session_state.edit_pr_data = {}
        
        st.subheader("1. Select Your Game Format")
        game_options = ["Straight up", "5m game", "10m game"]
        default_idx = game_options.index(st.session_state.pr_game_select) if st.session_state.pr_game_select in game_options else 0
        
        pr_game = st.selectbox("Game Type", game_options, index=default_idx, label_visibility="collapsed", key="pr_game_selector_main")
        st.session_state.pr_game_select = pr_game
        
        if pr_game == "Straight up":
            st.info("**Straight up:** A normal 9 or 18 hole round.")
        elif pr_game == "5m game":
            st.info("**5m game:** Every GIR hit outside of 5m/17ft must be taken off the green for a short game shot at least 3 paces off the green. Short game shots should alternate between fairway shot, first-cut shots, bunker shots, and rough-shots.")
        elif pr_game == "10m game":
            st.info("**10m game:** On all odd holes, place your drive in a position 10m worse than the original position, either through rough/bunker lies or distance from the hole. On all even holes, place your approach shot in a position 10m worse than the original position in-line with the hole.")

        if st.session_state.mode_pr == "grid":
            if st.button("➕ Log New Practice Round", key="new_pr_btn", type="primary"):
                st.session_state.edit_pr_id = None
                st.session_state.edit_pr_data = {}
                st.session_state.mode_pr = "entry"
                st.rerun()
                
            st.divider()
            
            df_pr = df_logs[(df_logs['game_category'] == "Practice Rounds") & (df_logs['game_name'] == pr_game)]
            
            if not df_pr.empty:
                st.write("### ✏️ Resume or Edit a Past Round")
                st.caption("Select a previously saved round to finish entering your stats.")
                edit_opts = df_pr.apply(lambda row: f"{str(row['created_at'])[:10]} | Score to Par: {row['score_primary']} (ID: {row['id']})", axis=1).tolist()
                selected_edit = st.selectbox("Select a round:", ["-- Select a round --"] + edit_opts, label_visibility="collapsed", key="pr_edit_selector")
                
                if selected_edit != "-- Select a round --":
                    edit_id = int(selected_edit.split("(ID: ")[1].replace(")", ""))
                    edit_row = df_pr[df_pr['id'] == edit_id].iloc[0]
                    
                    st.session_state.edit_pr_id = edit_id
                    st.session_state.edit_pr_data = edit_row['raw_data']
                    st.session_state.mode_pr = "entry"
                    st.rerun()
            st.divider()
            
            render_icon_grid(df_pr, pr_game)
            
        elif st.session_state.mode_pr == "entry":
            if st.button("🔙 Back to Previous Entries", key="back_pr_btn"):
                st.session_state.mode_pr = "grid"
                st.session_state.edit_pr_id = None
                st.session_state.edit_pr_data = {}
                st.rerun()
            st.divider()
            
            def get_val(section, key, default):
                if not st.session_state.get('edit_pr_data'): return default
                if section: return st.session_state.edit_pr_data.get(section, {}).get(key, default)
                return st.session_state.edit_pr_data.get(key, default)
            
            if st.session_state.edit_pr_id:
                st.info("✏️ **EDIT MODE:** You are currently updating an existing round. Hit save when you are finished.")
            
            st.subheader("2. Post-Round Debrief Data")
            
            tab_oc, tab_drv, tab_sz, tab_sg, tab_putt = st.tabs([
                "🚩 On-Course", "🚀 Driving", "🎯 Scoring Zone", "🪤 Short Game", "⛳ Putting"
            ])
            
            with tab_oc:
                st.write("### Round Overview")
                c1, c2, c3 = st.columns(3)
                pr_holes = c1.radio("Holes Played", [9, 18], index=0 if get_val(None, "holes_played", 9) == 9 else 1, horizontal=True)
                pr_gross = c2.number_input("Gross Score", min_value=20, max_value=150, value=get_val(None, "gross_score", 72), step=1)
                pr_to_par = c3.number_input("Score to Par (e.g., -2 or +3)", value=get_val(None, "score_to_par", 0), step=1)
                
                st.write("### Approach Accuracy")
                c4, c5 = st.columns(2)
                pr_gir_total = c4.number_input("Total GIR Hit", min_value=0, max_value=18, value=get_val(None, "gir_total", 9), step=1)
                pr_gir_5m = c5.number_input("GIR Inside 5m", min_value=0, max_value=18, value=get_val(None, "gir_inside_5m", 4), step=1)

            with tab_drv:
                st.write("### Tee Shot Accuracy")
                c1, c2 = st.columns(2)
                pr_fw_hit = c1.number_input("Fairways Hit", min_value=0, max_value=18, value=get_val("driving", "fairways_hit", 7), step=1)
                pr_tee_shots = c2.number_input("Total Tee Shots Hit", min_value=1, max_value=18, value=get_val("driving", "tee_shots", 14), step=1)

            with tab_sz:
                st.write("### Approach Shot Breakdown")
                
                st.markdown("**150-200 Yards**")
                col_l1, col_l2 = st.columns(2)
                pr_szl_score = col_l1.number_input("Score to Par (150-200)", value=get_val("scoring_zone", "szl_score", 0), step=1, key="pr_szl_s")
                pr_szl_shots = col_l2.number_input("Shots Recorded (150-200)", min_value=0, value=get_val("scoring_zone", "szl_shots", 5), step=1, key="pr_szl_n")
                
                st.markdown("**100-150 Yards**")
                col_m1, col_m2 = st.columns(2)
                pr_szm_score = col_m1.number_input("Score to Par (100-150)", value=get_val("scoring_zone", "szm_score", 0), step=1, key="pr_szm_s")
                pr_szm_shots = col_m2.number_input("Shots Recorded (100-150)", min_value=0, value=get_val("scoring_zone", "szm_shots", 5), step=1, key="pr_szm_n")
                
                st.markdown("**50-100 Yards**")
                col_s1, col_s2 = st.columns(2)
                pr_szs_score = col_s1.number_input("Score to Par (50-100)", value=get_val("scoring_zone", "szs_score", 0), step=1, key="pr_szs_s")
                pr_szs_shots = col_s2.number_input("Shots Recorded (50-100)", min_value=0, value=get_val("scoring_zone", "szs_shots", 5), step=1, key="pr_szs_n")

            with tab_sg:
                st.write("### Around the Green")
                c1, c2 = st.columns(2)
                pr_sg_total = c1.number_input("Total Short Game Shots Taken", min_value=0, value=get_val("short_game", "total_shots", 8), step=1)
                pr_sg_updown = c2.number_input("Successful Up & Downs", min_value=0, value=get_val("short_game", "up_and_downs", 4), step=1)
                
                st.write("### Proximity")
                c3, c4 = st.columns(2)
                pr_sg_6ft = c3.number_input("Shots Inside 6ft", min_value=0, value=get_val("short_game", "inside_6ft", 3), step=1)
                pr_sg_3ft = c4.number_input("Shots Inside 3ft", min_value=0, value=get_val("short_game", "inside_3ft", 1), step=1)

            with tab_putt:
                st.write("### Putting Performance")
                putt_mode = st.radio("Input Method:", ["Hole-by-Hole Calculator", "Manual Tour Data Entry"], horizontal=True, key="putt_mode_radio")

                pr_total_putts = 0
                pr_sg_putting = 0.0
                putting_holes_data = []

                if putt_mode == "Manual Tour Data Entry":
                    col_m1, col_m2 = st.columns(2)
                    pr_total_putts = col_m1.number_input("Total Putts", min_value=0, max_value=100, value=get_val("putting", "total_putts", 30), step=1)
                    pr_sg_putting = col_m2.number_input("Total SG Putting", value=float(get_val("putting", "sg_putting", 0.0)), step=0.1)
                else:
                    metric_cols = st.columns(2)
                    m_putts = metric_cols[0].empty()
                    m_sg = metric_cols[1].empty()
                    st.caption("Slide to select distance, tap to select putts (0 = Not Played).")

                    saved_holes = get_val("putting", "hole_by_hole_data", [])
                    if not isinstance(saved_holes, list):
                        saved_holes = []
                    while len(saved_holes) < 18:
                        saved_holes.append({"Distance (ft)": 0, "Putts": 0})

                    with st.expander("⛳ Front 9", expanded=True):
                        for i in range(9):
                            with st.container(border=True):
                                st.markdown(f"**Hole {i+1}**")
                                c1, c2 = st.columns([3, 2])
                                dist = c1.slider(f"Hole {i+1} Dist", 0, 100, int(saved_holes[i].get("Distance (ft)", 0)), key=f"dist_pr_{i}", label_visibility="collapsed")
                                putts = c2.radio(f"Hole {i+1} Putts", [0, 1, 2, 3, 4], index=int(saved_holes[i].get("Putts", 0)), horizontal=True, key=f"putts_pr_{i}", label_visibility="collapsed")
                                putting_holes_data.append({"Hole": f"Hole {i+1}", "Distance (ft)": dist, "Putts": putts})
                    
                    if pr_holes == 18:
                        with st.expander("⛳ Back 9", expanded=False):
                            for i in range(9, 18):
                                with st.container(border=True):
                                    st.markdown(f"**Hole {i+1}**")
                                    c1, c2 = st.columns([3, 2])
                                    dist = c1.slider(f"Hole {i+1} Dist", 0, 100, int(saved_holes[i].get("Distance (ft)", 0)), key=f"dist_pr_{i}", label_visibility="collapsed")
                                    putts = c2.radio(f"Hole {i+1} Putts", [0, 1, 2, 3, 4], index=int(saved_holes[i].get("Putts", 0)), horizontal=True, key=f"putts_pr_{i}", label_visibility="collapsed")
                                    putting_holes_data.append({"Hole": f"Hole {i+1}", "Distance (ft)": dist, "Putts": putts})

                    for row in putting_holes_data:
                        d = row["Distance (ft)"]
                        p = row["Putts"]
                        if p > 0: 
                            pr_total_putts += p
                        if d > 0 and p > 0: 
                            pr_sg_putting += (get_expected_putts(d) - p)
                            
                    m_putts.metric("Total Putts", pr_total_putts)
                    m_sg.metric("Total SG Putting", f"{pr_sg_putting:+.2f}")

                st.divider()
                st.write("**Lag Putting (18ft+)**")
                c1, c2 = st.columns(2)
                pr_lag_total = c1.number_input("Total Lag Putts Taken", min_value=0, value=get_val("putting", "lag_putts_total", 6), step=1)
                pr_lag_success = c2.number_input("Lag Putts Finished Inside 1 Putter Length", min_value=0, value=get_val("putting", "lag_putts_success", 5), step=1)

            st.divider()
            
            today_date = get_local_time_info()[0].date()
            monday_date = today_date - datetime.timedelta(days=today_date.weekday())
            pr_session_date = st.date_input("Date of Round", value=today_date, min_value=monday_date, max_value=today_date, key="date_pr_master")
            st.write("<br>", unsafe_allow_html=True)
            
            if st.button("💾 Save Practice Round", type="primary", use_container_width=True):
                pr_raw_data = {
                    "holes_played": pr_holes,
                    "gross_score": pr_gross,
                    "score_to_par": pr_to_par,
                    "gir_total": pr_gir_total,
                    "gir_inside_5m": pr_gir_5m,
                    "driving": {"fairways_hit": pr_fw_hit, "tee_shots": pr_tee_shots},
                    "scoring_zone": {
                        "szl_score": pr_szl_score, "szl_shots": pr_szl_shots,
                        "szm_score": pr_szm_score, "szm_shots": pr_szm_shots,
                        "szs_score": pr_szs_score, "szs_shots": pr_szs_shots
                    },
                    "short_game": {
                        "total_shots": pr_sg_total,
                        "up_and_downs": pr_sg_updown,
                        "inside_6ft": pr_sg_6ft,
                        "inside_3ft": pr_sg_3ft
                    },
                    "putting": {
                        "sg_putting": round(pr_sg_putting, 2),
                        "total_putts": pr_total_putts,
                        "lag_putts_total": pr_lag_total,
                        "lag_putts_success": pr_lag_success,
                        "hole_by_hole_data": putting_holes_data
                    }
                }
                
                data = {
                    "user_name": st.session_state.current_user, 
                    "game_category": "Practice Rounds", 
                    "game_name": pr_game, 
                    "score_primary": pr_to_par, 
                    "raw_data": pr_raw_data, 
                    "week_number": current_week, 
                    "created_at": f"{pr_session_date}T12:00:00Z"
                }
                
                if st.session_state.edit_pr_id:
                    supabase.table("practice_logs").update(data).eq("id", st.session_state.edit_pr_id).execute()
                    st.success(f"Round Updated Successfully!")
                else:
                    supabase.table("practice_logs").insert(data).execute()
                    st.success(f"{pr_game} Practice Round Successfully Logged!")
                    
                st.session_state.mode_pr = "grid"
                st.session_state.edit_pr_id = None
                st.session_state.edit_pr_data = {}
                st.rerun()

    # ==========================================
    # PAGE: DRIVING
    # ==========================================
    elif st.session_state.page == "Driving":
        st.title("🚀 Driving Combine")
        
        if 'mode_10shot' not in st.session_state: st.session_state.mode_10shot = "grid"
        if 'mode_ssbs' not in st.session_state: st.session_state.mode_ssbs = "grid"

        # FIX: Bug-free radio menu with On-Course Stats at the end
        drill_opts = ["10 Shot", "Max SS/BS", "On-Course Stats"]
        if st.session_state.get('driving_radio') not in drill_opts: st.session_state.driving_radio = "10 Shot"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.driving_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.driving_radio = selected_game
        
        if selected_game == "10 Shot":
            st.subheader("The 10 Shot Game")
            st.write("*Hit 10 shots. Carry distance (yds/m) minus offline total (ft). Average is your final score.*")
            
            if st.session_state.mode_10shot == "grid":
                if st.button("➕ New Entry", key="new_10shot", type="primary"):
                    st.session_state.mode_10shot = "entry"
                    st.rerun()
                st.divider()
                df_10 = df_logs[df_logs['game_name'] == "10 Shot"]
                render_icon_grid(df_10, "10 Shot")
                
            elif st.session_state.mode_10shot == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_10shot"):
                    st.session_state.mode_10shot = "grid"
                    st.rerun()
                
                st.divider()
                st.write("### New 10 Shot Log")
                st.caption("Tap a cell below to edit your distances.")
                
                if 'df_10shot_matrix' not in st.session_state:
                    st.session_state.df_10shot_matrix = pd.DataFrame({
                        "Shot": [f"Shot {i+1}" for i in range(10)],
                        "Carry (yds/m)": [0.0] * 10,
                        "Offline (ft)": [0.0] * 10
                    })
                
                edited_df = st.data_editor(
                    st.session_state.df_10shot_matrix,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Shot": st.column_config.TextColumn("Shot", disabled=True),
                        "Carry (yds/m)": st.column_config.NumberColumn("Carry (yds/m)", step=1.0),
                        "Offline (ft)": st.column_config.NumberColumn("Offline (ft)", step=1.0)
                    }
                )
                
                edited_df['Score'] = edited_df['Carry (yds/m)'] - edited_df['Offline (ft)']
                final_score = edited_df['Score'].mean()
                
                st.divider()
                st.metric("🎯 Final Average Score", f"{final_score:.1f}")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_10shot")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save 10 Shot Game", type="primary", use_container_width=True):
                    raw_json = edited_df.to_dict(orient='records')
                    data = {"user_name": st.session_state.current_user, "game_category": "Driving", "game_name": "10 Shot", "score_primary": final_score, "raw_data": raw_json, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    del st.session_state['df_10shot_matrix']
                    st.session_state.mode_10shot = "grid"
                    st.rerun()

        elif selected_game == "Max SS/BS":
            st.subheader("Speed Limits (SS/BS)")
            st.write("*Your Max Swing Speed and Ball Speed (in mph) with your Driver today. **On-course measurements are highly preferred**, but range measurements can be used if needed.*")
            
            if st.session_state.mode_ssbs == "grid":
                if st.button("➕ New Entry", key="new_ssbs", type="primary"):
                    st.session_state.mode_ssbs = "entry"
                    st.rerun()
                st.divider()
                df_ssbs = df_logs[df_logs['game_name'] == "Max SS/BS"]
                render_icon_grid(df_ssbs, "Max SS/BS")
                
            elif st.session_state.mode_ssbs == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_ssbs"):
                    st.session_state.mode_ssbs = "grid"
                    st.rerun()
                
                st.divider()
                c1, c2 = st.columns(2)
                ss = c1.number_input("Max Swing Speed (mph)", min_value=0.0, step=1.0, value=110.0)
                bs = c2.number_input("Max Ball Speed (mph)", min_value=0.0, step=1.0, value=160.0)
                
                st.divider()
                st.metric("⚡ Final Speed Score (SS/BS)", f"{ss:.0f} / {bs:.0f}")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_ssbs")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save Speed Limits", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Driving", "game_name": "Max SS/BS", "score_primary": ss, "score_secondary": bs, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Speeds locked in!")
                    st.session_state.mode_ssbs = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Driving")

    # ==========================================
    # PAGE: SCORING ZONE LONG
    # ==========================================
    elif st.session_state.page == "Scoring Zone Long":
        st.title("🎯 Scoring Zone Long (150-200)")
        
        if 'mode_szl_oc' not in st.session_state: st.session_state.mode_szl_oc = "grid"
        if 'mode_szl_tm' not in st.session_state: st.session_state.mode_szl_tm = "grid"

        drill_opts = ["Situational Practice 150-200", "TM 150-200", "On-Course Stats"]
        if st.session_state.get('szl_radio') not in drill_opts: st.session_state.szl_radio = "Situational Practice 150-200"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.szl_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.szl_radio = selected_game
        
        if selected_game == "Situational Practice 150-200":
            st.write("*Choose random situational shots between 150-200 yards/meters. At least 30% of shots must be from non-fairway lies including fairway bunkers, first-cut, and/or rough shots.*")
            st.caption("**Rules:** 5m from target (not pin) is a birdie, 10m is a par. Outside of 10m is bogey. Penalty shot is double.")
            
            if st.session_state.mode_szl_oc == "grid":
                if st.button("➕ New Entry", key="new_szl_oc", type="primary"):
                    st.session_state.mode_szl_oc = "entry"
                    st.rerun()
                st.divider()
                df_szl_oc = df_logs[df_logs['game_name'] == "Situational Practice 150-200"]
                render_icon_grid(df_szl_oc, "Situational Practice 150-200")
                
            elif st.session_state.mode_szl_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szl_oc"):
                    st.session_state.mode_szl_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1)
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1)
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szl_oc")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save Situational Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Long", "game_name": "Situational Practice 150-200", "score_primary": final_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szl_oc = "grid"
                    st.rerun()

        elif selected_game == "TM 150-200":
            st.write("*Launch monitor: Randomised systematic game from 150-200 with all pin locations/green shapes. 10 shot game. Record Strokes Gained.*")
            
            if st.session_state.mode_szl_tm == "grid":
                if st.button("➕ New Entry", key="new_szl_tm", type="primary"):
                    st.session_state.mode_szl_tm = "entry"
                    st.rerun()
                st.divider()
                df_szl_tm = df_logs[df_logs['game_name'] == "TM 150-200"]
                render_icon_grid(df_szl_tm, "TM 150-200")
                
            elif st.session_state.mode_szl_tm == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szl_tm"):
                    st.session_state.mode_szl_tm = "grid"
                    st.rerun()
                st.divider()
                
                sg_score = st.number_input("Final Strokes Gained Score", value=0.0, step=0.1)

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szl_tm")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save TM Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Long", "game_name": "TM 150-200", "score_primary": sg_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szl_tm = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Scoring Zone Long")

    # ==========================================
    # PAGE: SCORING ZONE MID
    # ==========================================
    elif st.session_state.page == "Scoring Zone Mid":
        st.title("🎯 Scoring Zone Mid (100-150)")
        
        if 'mode_szm_oc' not in st.session_state: st.session_state.mode_szm_oc = "grid"
        if 'mode_szm_tm' not in st.session_state: st.session_state.mode_szm_tm = "grid"

        drill_opts = ["Situational Practice 100-150", "TM 100-150", "On-Course Stats"]
        if st.session_state.get('szm_radio') not in drill_opts: st.session_state.szm_radio = "Situational Practice 100-150"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.szm_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.szm_radio = selected_game
        
        if selected_game == "Situational Practice 100-150":
            st.write("*Choose random situational shots between 100-150 yards/meters. At least 30% of shots must be from non-fairway lies including fairway bunkers, first-cut, and/or rough shots.*")
            st.caption("**Rules:** 4m from target (not pin) is a birdie, 8m is a par. Outside of 8m is bogey. Penalty shot is double.")
            
            if st.session_state.mode_szm_oc == "grid":
                if st.button("➕ New Entry", key="new_szm_oc", type="primary"):
                    st.session_state.mode_szm_oc = "entry"
                    st.rerun()
                st.divider()
                df_szm_oc = df_logs[df_logs['game_name'] == "Situational Practice 100-150"]
                render_icon_grid(df_szm_oc, "Situational Practice 100-150")
                
            elif st.session_state.mode_szm_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szm_oc"):
                    st.session_state.mode_szm_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1, key="szm_score")
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1, key="szm_shots")
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szm_oc")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save Situational Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Mid", "game_name": "Situational Practice 100-150", "score_primary": final_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szm_oc = "grid"
                    st.rerun()

        elif selected_game == "TM 100-150":
            st.write("*Launch monitor: Randomised systematic game from 100-150 with all pin locations/green shapes. 10 shot game. Record Strokes Gained.*")
            
            if st.session_state.mode_szm_tm == "grid":
                if st.button("➕ New Entry", key="new_szm_tm", type="primary"):
                    st.session_state.mode_szm_tm = "entry"
                    st.rerun()
                st.divider()
                df_szm_tm = df_logs[df_logs['game_name'] == "TM 100-150"]
                render_icon_grid(df_szm_tm, "TM 100-150")
                
            elif st.session_state.mode_szm_tm == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szm_tm"):
                    st.session_state.mode_szm_tm = "grid"
                    st.rerun()
                st.divider()
                
                sg_score = st.number_input("Final Strokes Gained Score", value=0.0, step=0.1, key="szm_sg")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szm_tm")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save TM Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Mid", "game_name": "TM 100-150", "score_primary": sg_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szm_tm = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Scoring Zone Mid")

    # ==========================================
    # PAGE: SCORING ZONE SHORT
    # ==========================================
    elif st.session_state.page == "Scoring Zone Short":
        st.title("🎯 Scoring Zone Short (50-100)")
        
        if 'mode_szs_oc' not in st.session_state: st.session_state.mode_szs_oc = "grid"
        if 'mode_szs_tm' not in st.session_state: st.session_state.mode_szs_tm = "grid"

        drill_opts = ["Situational Practice 50-100", "TM 50-100", "On-Course Stats"]
        if st.session_state.get('szs_radio') not in drill_opts: st.session_state.szs_radio = "Situational Practice 50-100"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.szs_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.szs_radio = selected_game
        
        if selected_game == "Situational Practice 50-100":
            st.write("*Choose random situational shots between 50-100 yards/meters. At least 30% of shots must be from non-fairway lies including fairway bunkers, first-cut, and/or rough shots.*")
            st.caption("**Rules:** 3m from target (not pin) is a birdie, 6m is a par. Outside of 6m is bogey. Penalty shot is double.")
            
            if st.session_state.mode_szs_oc == "grid":
                if st.button("➕ New Entry", key="new_szs_oc", type="primary"):
                    st.session_state.mode_szs_oc = "entry"
                    st.rerun()
                st.divider()
                df_szs_oc = df_logs[df_logs['game_name'] == "Situational Practice 50-100"]
                render_icon_grid(df_szs_oc, "Situational Practice 50-100")
                
            elif st.session_state.mode_szs_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szs_oc"):
                    st.session_state.mode_szs_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1, key="szs_score")
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1, key="szs_shots")
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szs_oc")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save Situational Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Short", "game_name": "Situational Practice 50-100", "score_primary": final_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szs_oc = "grid"
                    st.rerun()

        elif selected_game == "TM 50-100":
            st.write("*Launch monitor: Hit each shot from 50-100 in 5yd/m increments, max 2yd/m off in carry. You can only progress if you complete the current yardage.*")
            
            if st.session_state.mode_szs_tm == "grid":
                if st.button("➕ New Entry", key="new_szs_tm", type="primary"):
                    st.session_state.mode_szs_tm = "entry"
                    st.rerun()
                st.divider()
                df_szs_tm = df_logs[df_logs['game_name'] == "TM 50-100"]
                render_icon_grid(df_szs_tm, "TM 50-100")
                
            elif st.session_state.mode_szs_tm == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szs_tm"):
                    st.session_state.mode_szs_tm = "grid"
                    st.rerun()
                st.divider()
                
                total_attempts = st.number_input("Total Shots Taken to Complete", min_value=11, value=15, step=1)

                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_szs_tm")
                st.write("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Save TM Ladder Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Short", "game_name": "TM 50-100", "score_primary": total_attempts, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Ladder complete and saved!")
                    st.session_state.mode_szs_tm = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Scoring Zone Short")

    # ==========================================
    # PAGE: SHORT GAME
    # ==========================================
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
        
        if 'mode_sg_par21' not in st.session_state: st.session_state.mode_sg_par21 = "grid"
        if 'mode_sg_2050' not in st.session_state: st.session_state.mode_sg_2050 = "grid"
        if 'mode_sg_6ft' not in st.session_state: st.session_state.mode_sg_6ft = "grid"

        drill_opts = ["Par 21 WB", "20 to 50", "6ft Game", "On-Course Stats"]
        if st.session_state.get('sg_radio') not in drill_opts: st.session_state.sg_radio = "Par 21 WB"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.sg_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.sg_radio = selected_game
        
        if selected_game == "Par 21 WB":
            st.write("*A 9 hole short game course, with 3 easy, 3 medium, and 3 hard shots all from green-side up to 50 yards.*")
            st.caption("**Rules:** Drop 2 balls per hole. Play the worst ball amongst the 2 and hole out. Par is 2 per hole. Tour average is 21. If too advanced, use 1 ball.")
            
            if st.session_state.mode_sg_par21 == "grid":
                if st.button("➕ New Entry", key="new_sg_par21", type="primary"):
                    st.session_state.mode_sg_par21 = "entry"
                    st.rerun()
                st.divider()
                df_sg_par21 = df_logs[df_logs['game_name'] == "Par 21 WB"]
                render_icon_grid(df_sg_par21, "Par 21 WB")
                
            elif st.session_state.mode_sg_par21 == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_sg_par21"):
                    st.session_state.mode_sg_par21 = "grid"
                    st.rerun()
                st.divider()
                
                final_score = st.number_input("Final Strokes Taken", min_value=9, value=21, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_sg_par21")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save Par 21 Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": "Par 21 WB", "score_primary": final_score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_sg_par21 = "grid"
                    st.rerun()

        elif selected_game == "20 to 50":
            st.write("*5 balls from 20 yards. Record how many end up within 3ft, 6ft, 10ft. Repeat from 30, 40, and 50 yards.*")
            st.caption("**Rules:** See your final percentage. Randomise order and lies to vary difficulty. Max 5 total successful shots logged per yardage row.")
            
            if st.session_state.mode_sg_2050 == "grid":
                if st.button("➕ New Entry", key="new_sg_2050", type="primary"):
                    st.session_state.mode_sg_2050 = "entry"
                    st.rerun()
                st.divider()
                df_sg_2050 = df_logs[df_logs['game_name'] == "20 to 50"]
                render_icon_grid(df_sg_2050, "20 to 50")
                
            elif st.session_state.mode_sg_2050 == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_sg_2050"):
                    st.session_state.mode_sg_2050 = "grid"
                    st.rerun()
                st.divider()
                st.write("### 20 to 50 Tracker")
                
                if 'df_2050_matrix' not in st.session_state:
                    st.session_state.df_2050_matrix = pd.DataFrame({
                        "Yardage": ["20", "30", "40", "50"],
                        "3ft": [0, 0, 0, 0],
                        "6ft": [0, 0, 0, 0],
                        "10ft": [0, 0, 0, 0]
                    })
                    
                edited_df = st.data_editor(
                    st.session_state.df_2050_matrix,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Yardage": st.column_config.TextColumn("Yardage", disabled=True),
                        "3ft": st.column_config.NumberColumn("3ft", min_value=0, max_value=5, step=1),
                        "6ft": st.column_config.NumberColumn("6ft", min_value=0, max_value=5, step=1),
                        "10ft": st.column_config.NumberColumn("10ft", min_value=0, max_value=5, step=1)
                    }
                )
                
                cum_3ft = edited_df["3ft"].sum()
                cum_6ft = cum_3ft + edited_df["6ft"].sum()
                cum_10ft = cum_6ft + edited_df["10ft"].sum()
                
                pct_3ft = (cum_3ft / 20.0) * 100
                pct_6ft = (cum_6ft / 20.0) * 100
                pct_10ft = (cum_10ft / 20.0) * 100
                
                row_sums = edited_df["3ft"] + edited_df["6ft"] + edited_df["10ft"]
                if (row_sums > 5).any(): 
                    st.warning("⚠️ Careful! One of your yardage rows adds up to more than 5 shots.")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("3ft Accuracy", f"{pct_3ft:.0f}%")
                c2.metric("6ft Accuracy", f"{pct_6ft:.0f}%")
                c3.metric("10ft Accuracy", f"{pct_10ft:.0f}%")
                
                st.divider()
                st.metric("🎯 Final Combined Score (6ft Accuracy)", f"{pct_6ft:.0f}%")
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_sg_2050")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save 20 to 50 Log", type="primary", use_container_width=True, disabled=(row_sums > 5).any()):
                    raw_json = edited_df.to_dict(orient='records')
                    data = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": "20 to 50", "score_primary": pct_6ft, "raw_data": raw_json, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    del st.session_state['df_2050_matrix']
                    st.session_state.mode_sg_2050 = "grid"
                    st.rerun()

        elif selected_game == "6ft Game":
            st.write("*You have 2 lives. Choose random shots within 20 yards. Chip within 6ft = survive. Outside 6ft = lose 1 life.*")
            st.caption("**Rules:** Within 3ft = regain 1 life. Hole out = regain 2 lives. Randomise lies and pins. Record total holes played when you lose all lives.")
            
            if st.session_state.mode_sg_6ft == "grid":
                if st.button("➕ New Entry", key="new_sg_6ft", type="primary"):
                    st.session_state.mode_sg_6ft = "entry"
                    st.rerun()
                st.divider()
                df_sg_6ft = df_logs[df_logs['game_name'] == "6ft Game"]
                render_icon_grid(df_sg_6ft, "6ft Game")
                
            elif st.session_state.mode_sg_6ft == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_sg_6ft"):
                    st.session_state.mode_sg_6ft = "grid"
                    st.rerun()
                st.divider()
                
                holes_played = st.number_input("Total Holes Played (Survived)", min_value=0, value=9, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_sg_6ft")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save 6ft Game Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": "6ft Game", "score_primary": holes_played, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_sg_6ft = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Short Game")

    # ==========================================
    # PAGE: PUTTING
    # ==========================================
    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
        
        if 'mode_putt_pace' not in st.session_state: st.session_state.mode_putt_pace = "grid"
        if 'mode_putt_6912' not in st.session_state: st.session_state.mode_putt_6912 = "grid"
        if 'mode_putt_27' not in st.session_state: st.session_state.mode_putt_27 = "grid"
        if 'mode_putt_gr' not in st.session_state: st.session_state.mode_putt_gr = "grid"

        drill_opts = ["Pace", "6-9-12", "2-7 Drill", "Green Reading", "On-Course Stats"]
        if st.session_state.get('putt_radio') not in drill_opts: st.session_state.putt_radio = "Pace"
        
        selected_game = st.radio("Select Drill:", drill_opts, index=drill_opts.index(st.session_state.putt_radio), horizontal=True, label_visibility="collapsed")
        st.session_state.putt_radio = selected_game
        
        if selected_game == "Pace":
            st.write("*You have 3 lives. Hit random putts from 20-50ft. You lose a life if your putt finishes outside one putter length.*")
            st.caption("**Rules:** Count your consecutive putts inside a putter length. A miss costs a life and resets your streak to 0. Record your highest streak from the 3 lives.")
            
            if st.session_state.mode_putt_pace == "grid":
                if st.button("➕ New Entry", key="new_putt_pace", type="primary"):
                    st.session_state.mode_putt_pace = "entry"
                    st.rerun()
                st.divider()
                df_putt_pace = df_logs[df_logs['game_name'] == "Pace"]
                render_icon_grid(df_putt_pace, "Pace")
                
            elif st.session_state.mode_putt_pace == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_putt_pace"):
                    st.session_state.mode_putt_pace = "grid"
                    st.rerun()
                st.divider()
                
                score = st.number_input("Best Streak (Max Consecutive Putts)", min_value=0, value=5, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_putt_pace")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save Pace Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "Pace", "score_primary": score, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_pace = "grid"
                    st.rerun()

        elif selected_game == "6-9-12":
            st.write("*Hit randomised putts in order: 6ft, 9ft, 12ft, 6ft, 9ft, 12ft... until you hole at least 50ft of putts.*")
            st.caption("**Rules:** Keep track of the total distance holed. Record the total number of putts it took to reach or exceed 50ft.")
            
            if st.session_state.mode_putt_6912 == "grid":
                if st.button("➕ New Entry", key="new_putt_6912", type="primary"):
                    st.session_state.mode_putt_6912 = "entry"
                    st.rerun()
                st.divider()
                df_putt_6912 = df_logs[df_logs['game_name'] == "6-9-12"]
                render_icon_grid(df_putt_6912, "6-9-12")
                
            elif st.session_state.mode_putt_6912 == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_putt_6912"):
                    st.session_state.mode_putt_6912 = "grid"
                    st.rerun()
                st.divider()
                
                total_putts = st.number_input("Total Putts Taken to Reach 50ft", min_value=5, value=15, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_putt_6912")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save 6-9-12 Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "6-9-12", "score_primary": total_putts, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_6912 = "grid"
                    st.rerun()

        elif selected_game == "2-7 Drill":
            st.write("*Ladder drill: Make a putt from 2ft, 3ft, 4ft, 5ft, 6ft, and 7ft consecutively.*")
            st.caption("**Rules:** If you miss, you must start over at 2ft. Record the total number of **tries** it took to successfully complete the ladder. (1 try = completing it flawlessly on the first go). *Note: You can randomise the order of distances to increase difficulty.*")
            
            if st.session_state.mode_putt_27 == "grid":
                if st.button("➕ New Entry", key="new_putt_27", type="primary"):
                    st.session_state.mode_putt_27 = "entry"
                    st.rerun()
                st.divider()
                df_putt_27 = df_logs[df_logs['game_name'] == "2-7 Drill"]
                render_icon_grid(df_putt_27, "2-7 Drill")
                
            elif st.session_state.mode_putt_27 == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_putt_27"):
                    st.session_state.mode_putt_27 = "grid"
                    st.rerun()
                st.divider()
                
                # UPDATED: Changed label, and set min_value to 1
                attempts = st.number_input("Total Tries to Complete Ladder", min_value=1, value=3, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_putt_27")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save 2-7 Drill Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "2-7 Drill", "score_primary": attempts, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_27 = "grid"
                    st.rerun()

        elif selected_game == "Green Reading":
            st.write("*Find a random putt within 10ft. Read the line, place a tee, and test using a start-line aid (like a Perfect Putter).*")
            st.caption("**Rules:** You have 3 lives. Every missed read costs a life. Record the total number of correct reads you achieved.")
            
            if st.session_state.mode_putt_gr == "grid":
                if st.button("➕ New Entry", key="new_putt_gr", type="primary"):
                    st.session_state.mode_putt_gr = "entry"
                    st.rerun()
                st.divider()
                df_putt_gr = df_logs[df_logs['game_name'] == "Green Reading"]
                render_icon_grid(df_putt_gr, "Green Reading")
                
            elif st.session_state.mode_putt_gr == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_putt_gr"):
                    st.session_state.mode_putt_gr = "grid"
                    st.rerun()
                st.divider()
                
                correct_reads = st.number_input("Total Correct Reads", min_value=0, value=5, step=1)
                
                today_date = get_local_time_info()[0].date()
                monday_date = today_date - datetime.timedelta(days=today_date.weekday())
                session_date = st.date_input("Date of Session", value=today_date, min_value=monday_date, max_value=today_date, key="date_putt_gr")
                st.write("<br>", unsafe_allow_html=True)

                if st.button("💾 Save Green Reading Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "Green Reading", "score_primary": correct_reads, "week_number": current_week, "created_at": f"{session_date}T12:00:00Z"}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_gr = "grid"
                    st.rerun()
                    
        elif selected_game == "On-Course Stats":
            render_on_course_performance("Putting")

    # ==========================================
    # PAGE: YOUR PRACTICE TRENDS
    # ==========================================
    elif st.session_state.page.lower() == "your practice trends":
        st.title("📈 Your Practice Trends")
        st.write("Track your overall category momentum and individual drill performance in one unified view.")
        
        if df_logs.empty:
            st.info("No practice data logged yet. Head to the combine pages to log your first session!")
        else:
            # --- UI: TOP CONTROLS ---
            col_a, col_b = st.columns(2)
            categories = sorted(df_logs['game_category'].dropna().unique().tolist())
            selected_cat = col_a.selectbox("Select Category to Analyze", categories)
            timeline = col_b.selectbox("Select Timeframe", ["Weekly Averages", "Monthly Averages", "6-Month Averages", "Yearly Averages"])
            
            # --- DATA PREP ---
            df_cat = df_logs[df_logs['game_category'] == selected_cat].copy()
            # 1. Get the current user's dynamic timezone (defaults to UTC just in case)
            # Note: Ensure 'timezone' matches the exact name you used in your login page session state!
            user_tz = st.session_state.get('timezone', 'UTC')

            # 2. Parse as UTC, 3. Convert to User's Timezone, 4. Strip the timezone tag for Streamlit
            df_cat['created_at'] = (
            pd.to_datetime(df_cat['created_at'], utc=True, errors='coerce')
            .dt.tz_convert(user_tz)
            .dt.tz_localize(None)
            )

            # Clean up: Drop any rows that had garbage data instead of real dates
            df_cat = df_cat.dropna(subset=['created_at'])
            
            if timeline == "Weekly Averages":
                df_cat['Period_Sort'] = df_cat['created_at'].dt.to_period('W').dt.start_time
                df_cat['Group'] = df_cat['created_at'].dt.strftime('Week %V, %Y')
            elif timeline == "Monthly Averages":
                df_cat['Period_Sort'] = df_cat['created_at'].dt.to_period('M').dt.start_time
                df_cat['Group'] = df_cat['created_at'].dt.strftime('%b %Y')
            elif timeline == "6-Month Averages":
                df_cat['half'] = df_cat['created_at'].dt.month.apply(lambda m: "H1" if m <= 6 else "H2")
                df_cat['Period_Sort'] = pd.to_datetime(df_cat['created_at'].dt.strftime('%Y') + df_cat['half'].apply(lambda x: '-01-01' if x == 'H1' else '-07-01'))
                df_cat['Group'] = df_cat['created_at'].dt.strftime('%Y') + " " + df_cat['half']
            elif timeline == "Yearly Averages":
                df_cat['Period_Sort'] = df_cat['created_at'].dt.to_period('Y').dt.start_time
                df_cat['Group'] = df_cat['created_at'].dt.strftime('%Y')
                
            lower_is_better_games = ["Situational Practice 150-200", "Situational Practice 100-150", "Situational Practice 50-100", "TM 50-100", "Par 21 WB", "6ft Game", "6-9-12", "2-8 Drill", "Straight up", "5m game", "10m game"]

            st.divider()

            # ==========================================
            # 1. MACRO VIEW: OVERALL CATEGORY MOMENTUM
            # ==========================================
            st.subheader(f"🚀 {selected_cat} Overall Momentum")
            st.write("*Your 'Running Baseline'. Shows overall percentage improvement or regression across all drills in this category compared to the previous period.*")
            
            df_agg_mom = df_cat.groupby(['Period_Sort', 'Group', 'game_name'])['score_primary'].mean().reset_index()
            pivot = df_agg_mom.pivot(index=['Period_Sort', 'Group'], columns='game_name', values='score_primary')
            pivot = pivot.sort_index()
            
            if len(pivot) < 2:
                st.info(f"⏳ **More data needed for Momentum.** You only have one period of data for {selected_cat}. Log another session next period to see your baseline trend!")
            else:
                diff = pivot.diff()
                denom = pivot.shift(1).replace(0, 1).abs()
                pct_diff = (diff / denom) * 100
                
                for col in pct_diff.columns:
                    if col in lower_is_better_games:
                        pct_diff[col] = pct_diff[col] * -1 
                        
                category_momentum = pct_diff.mean(axis=1).dropna()
                
                if not category_momentum.empty:
                    chart_df = pd.DataFrame(category_momentum, columns=["Momentum Delta (%)"]).reset_index()
                    latest_momentum = category_momentum.iloc[-1]
                    
                    st.metric(f"Current {selected_cat} Momentum", f"{latest_momentum:+.1f}%", delta=f"{latest_momentum:+.1f}% vs previous period", delta_color="normal")
                    
                    mom_chart = alt.Chart(chart_df).mark_bar().encode(
                        x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45), sort=None),
                        y=alt.Y('Momentum Delta (%):Q', title="Momentum (%)"), 
                        color=alt.condition(alt.datum['Momentum Delta (%)'] > 0, alt.value("#0068C9"), alt.value("#FF4B4B")),
                        tooltip=[alt.Tooltip('Group:N', title='Period'), alt.Tooltip('Momentum Delta (%):Q', format='+.1f')]
                    ).properties(height=250)
                    
                    st.altair_chart(mom_chart, use_container_width=True)

            st.divider()

            # ==========================================
            # 2. MICRO VIEW: INDIVIDUAL DRILL BREAKDOWN
            # ==========================================
            st.subheader(f"🎯 Individual Drill Breakdown")
            
            games_in_cat = sorted(df_cat['game_name'].unique().tolist())
            
            # Create a dynamic 2-column grid
            cols = st.columns(2)
            
            for idx, game in enumerate(games_in_cat):
                col = cols[idx % 2] # Alternates between left (0) and right (1) column
                
                with col:
                    with st.container(border=True):
                        st.markdown(f"#### {game}")
                        df_game = df_cat[df_cat['game_name'] == game].copy()
                        df_game = df_game.sort_values('Period_Sort')
                        
                        is_lower_better = game in lower_is_better_games
                        
                        if game == "Max SS/BS":
                            df_agg = df_game.groupby(['Period_Sort', 'Group'], sort=False)[['score_primary', 'score_secondary']].max().reset_index()
                            pb_ss, pb_bs = df_game['score_primary'].max(), df_game['score_secondary'].max()
                            avg_ss, avg_bs = df_game['score_primary'].mean(), df_game['score_secondary'].mean()
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Personal Best", f"{pb_ss:.0f}/{pb_bs:.0f}")
                            c2.metric("All-Time Avg", f"{avg_ss:.0f}/{avg_bs:.0f}")
                            
                            # Swing Speed line
                            ss_chart = alt.Chart(df_agg).mark_line(
                                point=alt.OverlayMarkDef(color="#FF4B4B", size=60, filled=True), color="#FF4B4B", strokeWidth=2
                            ).encode(
                                x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45), sort=None),
                                y=alt.Y('score_primary:Q', scale=alt.Scale(zero=False), title="Swing Speed"),
                                tooltip=[alt.Tooltip('Group:N'), alt.Tooltip('score_primary:Q', title='SS')]
                            ).properties(height=150)
                            
                            # Ball Speed line
                            bs_chart = alt.Chart(df_agg).mark_line(
                                point=alt.OverlayMarkDef(color="#0068C9", size=60, filled=True), color="#0068C9", strokeWidth=2
                            ).encode(
                                x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45), sort=None),
                                y=alt.Y('score_secondary:Q', scale=alt.Scale(zero=False), title="Ball Speed"),
                                tooltip=[alt.Tooltip('Group:N'), alt.Tooltip('score_secondary:Q', title='BS')]
                            ).properties(height=150)
                            
                            st.altair_chart(ss_chart, use_container_width=True)
                            st.altair_chart(bs_chart, use_container_width=True)

                        else:
                            df_agg = df_game.groupby(['Period_Sort', 'Group'], sort=False)['score_primary'].mean().reset_index()
                            pb = df_game['score_primary'].min() if is_lower_better else df_game['score_primary'].max()
                            avg = df_game['score_primary'].mean()
                            
                            if game in ["20 to 50"]: pb_str, avg_str = f"{pb:.0f}%", f"{avg:.0f}%"
                            elif game in ["Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-7 Drill", "6-9-12", "Green Reading"]: pb_str, avg_str = f"{pb:.0f}", f"{avg:.1f}"
                            elif selected_cat == "Practice Rounds": pb_str, avg_str = f"{'+' if pb>0 else ''}{pb:.0f}", f"{'+' if avg>0 else ''}{avg:.1f}"
                            else: pb_str, avg_str = f"{pb:.2f}", f"{avg:.2f}"
                                
                            c1, c2 = st.columns(2)
                            c1.metric("Personal Best", pb_str)
                            c2.metric("All-Time Avg", avg_str)
                            
                            chart = alt.Chart(df_agg).mark_line(
                                point=alt.OverlayMarkDef(color="#0068C9", size=60, filled=True), color="#0068C9", strokeWidth=2
                            ).encode(
                                x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45), sort=None),
                                y=alt.Y('score_primary:Q', scale=alt.Scale(zero=False), title="Score"),
                                tooltip=[alt.Tooltip('Group:N'), alt.Tooltip('score_primary:Q', title='Avg Score', format='.1f')]
                            ).properties(height=180)
                            
                            st.altair_chart(chart, use_container_width=True)
