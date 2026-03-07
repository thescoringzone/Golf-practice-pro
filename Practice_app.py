import streamlit as st
import pandas as pd
import datetime
import pytz
import json
from supabase import create_client

# --- 1. APP CONFIG & PREMIUM CSS ---
st.set_page_config(page_title="Golf Practice Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Montserrat:wght@300;400;600&display=swap');
    
    html, body, [class*="css"], [class*="st-"], .stMarkdown, .stText {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
    }
    
    /* MacBook Style Icon Cards for Previous Entries */
    .mac-icon {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
    }
    .mac-icon:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        border-color: #007bff;
    }
    .icon-date { font-size: 0.85em; color: #666; margin-bottom: 5px; }
    .icon-score { font-size: 1.4em; font-weight: bold; color: #111; }
    
    /* Number Input alignment */
    input[type="number"] { text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Database connection failed. Please check your Streamlit secrets.")

# --- 3. GLOBAL STATE & TIME ENGINE ---
if 'current_user' not in st.session_state: st.session_state.current_user = None
if 'timezone' not in st.session_state: st.session_state.timezone = "UTC"
if 'page' not in st.session_state: st.session_state.page = "Login"

def get_local_time_info():
    """Calculates the current week number and checks if today is Sunday based on user timezone."""
    tz = pytz.timezone(st.session_state.timezone)
    local_time = datetime.datetime.now(tz)
    # isocalendar returns (year, week_number, weekday 1-7 where 7 is Sunday)
    year, week_num, weekday = local_time.isocalendar()
    is_sunday = (weekday == 7)
    return local_time, year, week_num, is_sunday

# --- 4. DATA LOADER ---
def load_all_logs(username):
    response = supabase.table("practice_logs").select("*").eq("user_name", username).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

# --- 5. ROUTING: LOGIN GATE ---
if st.session_state.page == "Login" or not st.session_state.current_user:
    st.markdown("<h1 style='text-align: center; font-size: 4em; margin-top: 5%;'>Golf Practice Pro</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Elite Combine & Analytics</h3>", unsafe_allow_html=True)
    st.write("<br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            username_input = st.text_input("Player Username", placeholder="Enter username...").strip()
            
            # Common timezones for easy selection
            common_tzs = ["US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "Europe/London", "Asia/Hong_Kong", "Australia/Sydney", "UTC"]
            selected_tz = st.selectbox("Your Local Timezone (For Weekly Reset)", common_tzs, index=0)
            
            if st.button("Authenticate & Enter", use_container_width=True, type="primary"):
                if username_input:
                    st.session_state.current_user = username_input
                    st.session_state.timezone = selected_tz
                    st.session_state.page = "Weekly Dashboard"
                    st.rerun()

# --- 6. ROUTING: SECURE PLATFORM ---
else:
    # Calculate Time Data
    local_now, current_year, current_week, is_sunday = get_local_time_info()
    
    # Load User Data
    df_logs = load_all_logs(st.session_state.current_user)
    
    # -- SIDEBAR NAVIGATION --
    st.sidebar.title("👤 Player Profile")
    st.sidebar.write(f"**{st.session_state.current_user}**")
    st.sidebar.caption(f"Timezone: {st.session_state.timezone}")
    st.sidebar.caption(f"🗓️ **Week {current_week} of {current_year}**")
    
    if st.sidebar.button("Log Out"):
        st.session_state.current_user = None
        st.session_state.page = "Login"
        st.rerun()
        
    st.sidebar.divider()
    st.sidebar.header("🧭 Navigation")
    
    nav_options = [
        "Weekly Dashboard", 
        "Driving", 
        "Scoring Zone Long", 
        "Scoring Zone Mid", 
        "Scoring Zone Short", 
        "Short Game", 
        "Putting", 
        "Stock Market Analytics"
    ]
    
    for opt in nav_options:
        if st.sidebar.button(opt, use_container_width=True, type="primary" if st.session_state.page == opt else "secondary"):
            st.session_state.page = opt
            st.rerun()

    # -- SUNDAY DEADLINE WARNING --
    if is_sunday:
        st.warning("⚠️ **Reminder: Today is Sunday!** Your Weekly Dashboard resets tonight at midnight. Finish your weekly combine!")

    # ==========================================
    # PAGE: WEEKLY DASHBOARD
    # ==========================================
    if st.session_state.page == "Weekly Dashboard":
        st.title(f"📊 Week {current_week} Dashboard")
        st.write("Your active practice session progress for this week.")
        
        # We will build out the visual grid of the week's practice here in Part 3.
        st.info("Dashboard module loading... Data from your logged games will aggregate here.")

    # ==========================================
    # PAGE: DRIVING
    # ==========================================
    elif st.session_state.page == "Driving":
        st.title("🚀 Driving Combine")
        
        game_tabs = st.tabs(["10 Shot Game", "Max SS/BS"])
        
        with game_tabs[0]:
            st.subheader("The 10 Shot Game")
            st.write("*Hit 10 shots. Carry distance (yds/m) minus offline total (ft). Average is your final score.*")
            # We will insert the 10-row matrix and MacBook icons here in Part 2.
            st.info("Matrix interface loading...")
            
        with game_tabs[1]:
            st.subheader("Speed Limits (SS/BS)")
            st.write("*Your Max Swing Speed and Ball Speed (in mph) with your Driver today.*")
            # We will insert the dual-input manual entry here in Part 2.
            st.info("Speed logging interface loading...")

    # ==========================================
    # OTHER PAGES (Placeholders for Part 2 & 3)
    # ==========================================
    elif st.session_state.page == "Scoring Zone Long":
        st.title("🎯 Scoring Zone Long (150-200)")
    elif st.session_state.page == "Scoring Zone Mid":
        st.title("🎯 Scoring Zone Mid (100-150)")
    elif st.session_state.page == "Scoring Zone Short":
        st.title("🎯 Scoring Zone Short (50-100)")
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
    elif st.session_state.page == "Stock Market Analytics":
        st.title("📈 Stock Market Analytics")
        st.write("Long-term trend analysis and Personal Bests.")
