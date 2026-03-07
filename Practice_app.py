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
    if response.data:
        return pd.DataFrame(response.data)
    else:
        # If the database is empty, build an empty shell with the correct columns
        return pd.DataFrame(columns=[
            "id", "created_at", "user_name", "game_category", "game_name", 
            "score_primary", "score_secondary", "raw_data", "week_number"
        ])
    
   # --- 4.5 HELPER: MACBOOK ICON GRID ---
def render_icon_grid(df_game, game_name):
    if df_game.empty:
        st.info("No practice sessions logged yet. Click 'New Entry' to start.")
        return

    cols = st.columns(4)
    # Sort by newest first so your latest practice is always first
    df_game = df_game.sort_values('created_at', ascending=False).reset_index(drop=True)
    
    for i, (_, row) in enumerate(df_game.iterrows()):
        with cols[i % 4]:
            with st.container(border=True):
                # 1. Format the Date beautifully
                try:
                    dt = datetime.datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                    date_str = dt.strftime("%b %d, %Y")
                except:
                    date_str = str(row['created_at'])[:10]
                
                # 2. Format the Score depending on the game rules
                if game_name == "Max SS/BS":
                    score_str = f"{row['score_primary']:.0f} / {row['score_secondary']:.0f}"
                else:
                    score_str = f"{row['score_primary']:.1f}"

                # 3. Render the specific Date and Score vividly on the icon
                st.markdown(f"""
                <div style='text-align: center; padding: 5px; margin-bottom: 10px;'>
                    <span style='color: gray; font-size: 0.9em;'>🗂️ {date_str}</span><br>
                    <b style='font-size: 1.6em; color: #111;'>{score_str}</b>
                </div>
                """, unsafe_allow_html=True)
                
                # 4. Action Buttons (View & Delete)
                c1, c2 = st.columns(2)
                
                if c1.button("👁️ View", key=f"view_{row['id']}", use_container_width=True):
                    st.toast("Data expansion module coming in Part 4!", icon="⏳")
                
                # 5. The Safe Delete Feature (Floating Popover)
                with c2.popover("🗑️ Del", use_container_width=True):
                    st.markdown("**Delete this record?**")
                    st.caption("This cannot be undone.")
                    
                    if st.button("Yes, Delete", key=f"confirm_del_{row['id']}", type="primary", use_container_width=True):
                        # Safely remove it from the database
                        supabase.table("practice_logs").delete().eq("id", row['id']).execute()
                        st.success("Record deleted!")
                        st.rerun()

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
        
        # State managers to flip between "Grid" view and "New Entry" view
        if 'mode_10shot' not in st.session_state: st.session_state.mode_10shot = "grid"
        if 'mode_ssbs' not in st.session_state: st.session_state.mode_ssbs = "grid"

        game_tabs = st.tabs(["10 Shot Game", "Max SS/BS"])
        
        # --- TAB 1: 10 SHOT GAME ---
        with game_tabs[0]:
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
                
                # Create a temporary dataframe for the sleek mobile spreadsheet
                if 'df_10shot_matrix' not in st.session_state:
                    st.session_state.df_10shot_matrix = pd.DataFrame({
                        "Shot": [f"Shot {i+1}" for i in range(10)],
                        "Carry (yds/m)": [0.0] * 10,
                        "Offline (ft)": [0.0] * 10
                    })
                
                # Render the interactive mobile-friendly spreadsheet
                edited_df = st.data_editor(
                    st.session_state.df_10shot_matrix,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Shot": st.column_config.TextColumn("Shot", disabled=True), # Lock the Shot column
                        "Carry (yds/m)": st.column_config.NumberColumn("Carry (yds/m)", step=1.0),
                        "Offline (ft)": st.column_config.NumberColumn("Offline (ft)", step=1.0)
                    }
                )
                
                # The Math: (Carry - Offline). Average of all 10.
                edited_df['Score'] = edited_df['Carry (yds/m)'] - edited_df['Offline (ft)']
                final_score = edited_df['Score'].mean()
                
                st.divider()
                st.metric("🎯 Final Average Score", f"{final_score:.1f}")
                
                if st.button("💾 Save 10 Shot Game", type="primary", use_container_width=True):
                    # Convert the dataframe back into a JSON-friendly list of dictionaries
                    raw_json = edited_df.to_dict(orient='records')
                    
                    data = {
                        "user_name": st.session_state.current_user,
                        "game_category": "Driving",
                        "game_name": "10 Shot",
                        "score_primary": final_score,
                        "raw_data": raw_json,
                        "week_number": current_week
                    }
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved to your database!")
                    
                    # Clear the matrix for the next time
                    del st.session_state['df_10shot_matrix']
                    st.session_state.mode_10shot = "grid"
                    st.rerun()

        # --- TAB 2: MAX SS/BS ---
        with game_tabs[1]:
            st.subheader("Speed Limits (SS/BS)")
            st.write("*Your Max Swing Speed and Ball Speed (in mph) with your Driver today.*")
            
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
                st.write("### New Speed Log")
                c1, c2 = st.columns(2)
                ss = c1.number_input("Max Swing Speed (mph)", min_value=0.0, step=1.0, value=110.0)
                bs = c2.number_input("Max Ball Speed (mph)", min_value=0.0, step=1.0, value=160.0)
                
                st.divider()
                # Visualized as SS/BS, just like you wanted
                st.metric("⚡ Final Speed Score (SS/BS)", f"{ss:.0f} / {bs:.0f}")
                
                if st.button("💾 Save Speed Limits", type="primary", use_container_width=True):
                    data = {
                        "user_name": st.session_state.current_user,
                        "game_category": "Driving",
                        "game_name": "Max SS/BS",
                        "score_primary": ss,           # Stored separately so Stock Market charts work!
                        "score_secondary": bs,         # Stored separately so Stock Market charts work!
                        "week_number": current_week
                    }
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Speeds locked in!")
                    st.session_state.mode_ssbs = "grid"
                    st.rerun()
                    
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
