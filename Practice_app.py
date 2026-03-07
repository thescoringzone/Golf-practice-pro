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
    
    /* 1. BRING BACK THE PREMIUM FONTS GLOBALLY */
    html, body, [class*="css"], [class*="st-"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
    }
    
    /* 2. THE IRONCLAD ICON SHIELD */
    /* This forces all UI arrows, popovers, and sidebar toggles to stay as symbols */
    .material-symbols-rounded, 
    .stIcon, 
    [data-testid="stIconMaterial"], 
    span:has(> .material-symbols-rounded) {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    /* Center align the numbers in the mobile matrix */
    input[type="number"] { 
        text-align: center; 
    }
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
    # Sort by newest first
    df_game = df_game.sort_values('created_at', ascending=False).reset_index(drop=True)
    
    for i, (_, row) in enumerate(df_game.iterrows()):
        with cols[i % 4]:
            with st.container(border=True):
                # 1. Format Date
                try:
                    dt = datetime.datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                    date_str = dt.strftime("%b %d, %Y")
                except:
                    date_str = str(row['created_at'])[:10]
                
                # 2. Format Score
                if game_name == "Max SS/BS":
                    score_str = f"{row['score_primary']:.0f} / {row['score_secondary']:.0f}"
                else:
                    score_str = f"{row['score_primary']:.1f}"

                # 3. Render Date and Score (Fixed color for Dark Mode)
                st.markdown(f"""
                <div style='text-align: center; padding: 5px; margin-bottom: 10px;'>
                    <span style='color: gray; font-size: 0.9em;'>🗂️ {date_str}</span><br>
                    <b style='font-size: 1.6em; color: var(--text-color);'>{score_str}</b>
                </div>
                """, unsafe_allow_html=True)
                
                # 4. Action Buttons
                c1, c2 = st.columns(2)
                
                if c1.button("👁️ View", key=f"view_{row['id']}", use_container_width=True):
                    st.toast("Data expansion module coming in Part 4!", icon="⏳")
                
                # 5. Safe Delete Feature
                with c2.popover("🗑️ Del", use_container_width=True):
                    st.markdown("**Delete this record?**")
                    st.caption("This cannot be undone.")
                    
                    if st.button("Yes", key=f"confirm_del_{row['id']}", type="primary", use_container_width=True):
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
    # ==========================================
    # PAGE: SCORING ZONE LONG
    # ==========================================
    elif st.session_state.page == "Scoring Zone Long":
        st.title("🎯 Scoring Zone Long (150-200)")
        
        if 'mode_szl_oc' not in st.session_state: st.session_state.mode_szl_oc = "grid"
        if 'mode_szl_tm' not in st.session_state: st.session_state.mode_szl_tm = "grid"

        tabs = st.tabs(["On-Course 150-200", "TM 150-200"])
        
        # --- TAB 1: ON-COURSE LONG ---
        with tabs[0]:
            st.write("*Log your on-course 150-200 yards/meter scoring zone scores when you practice on the course.*")
            st.caption("**Rules:** 5m from target (not pin) is a birdie, 10m is a par. Outside of 10m is bogey. Penalty shot is double.")
            if st.session_state.mode_szl_oc == "grid":
                if st.button("➕ New Entry", key="new_szl_oc", type="primary"):
                    st.session_state.mode_szl_oc = "entry"
                    st.rerun()
                st.divider()
                df_szl_oc = df_logs[df_logs['game_name'] == "On-Course 150-200"]
                render_icon_grid(df_szl_oc, "On-Course 150-200")
                
            elif st.session_state.mode_szl_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szl_oc"):
                    st.session_state.mode_szl_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0.0, step=1.0)
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1)
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")
                
                if st.button("💾 Save On-Course Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Long", "game_name": "On-Course 150-200", "score_primary": final_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szl_oc = "grid"
                    st.rerun()

        # --- TAB 2: TM LONG ---
        with tabs[1]:
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
                
                if st.button("💾 Save TM Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Long", "game_name": "TM 150-200", "score_primary": sg_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szl_tm = "grid"
                    st.rerun()

    # ==========================================
    # PAGE: SCORING ZONE MID
    # ==========================================
    elif st.session_state.page == "Scoring Zone Mid":
        st.title("🎯 Scoring Zone Mid (100-150)")
        
        if 'mode_szm_oc' not in st.session_state: st.session_state.mode_szm_oc = "grid"
        if 'mode_szm_tm' not in st.session_state: st.session_state.mode_szm_tm = "grid"

        tabs = st.tabs(["On-Course 100-150", "TM 100-150"])
        
        # --- TAB 1: ON-COURSE MID ---
        with tabs[0]:
            st.write("*Log your on-course 100-150 yards/meter scoring zone scores when you practice on the course.*")
            st.caption("**Rules:** 4m from target (not pin) is a birdie, 8m is a par. Outside of 8m is bogey. Penalty shot is double.")
            if st.session_state.mode_szm_oc == "grid":
                if st.button("➕ New Entry", key="new_szm_oc", type="primary"):
                    st.session_state.mode_szm_oc = "entry"
                    st.rerun()
                st.divider()
                df_szm_oc = df_logs[df_logs['game_name'] == "On-Course 100-150"]
                render_icon_grid(df_szm_oc, "On-Course 100-150")
                
            elif st.session_state.mode_szm_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szm_oc"):
                    st.session_state.mode_szm_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0.0, step=1.0, key="szm_score")
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1, key="szm_shots")
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")
                
                if st.button("💾 Save On-Course Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Mid", "game_name": "On-Course 100-150", "score_primary": final_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szm_oc = "grid"
                    st.rerun()

        # --- TAB 2: TM MID ---
        with tabs[1]:
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
                
                if st.button("💾 Save TM Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Mid", "game_name": "TM 100-150", "score_primary": sg_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szm_tm = "grid"
                    st.rerun()

    # ==========================================
    # PAGE: SCORING Zone SHORT
    # ==========================================
    elif st.session_state.page == "Scoring Zone Short":
        st.title("🎯 Scoring Zone Short (50-100)")
        
        if 'mode_szs_oc' not in st.session_state: st.session_state.mode_szs_oc = "grid"
        if 'mode_szs_tm' not in st.session_state: st.session_state.mode_szs_tm = "grid"

        tabs = st.tabs(["On-Course 50-100", "TM 50-100"])
        
        # --- TAB 1: ON-COURSE SHORT ---
        with tabs[0]:
            st.write("*Log your on-course 50-100 yards/meter scoring zone scores when you practice on the course.*")
            st.caption("**Rules:** 3m from target (not pin) is a birdie, 6m is a par. Outside of 6m is bogey. Penalty shot is double.")
            if st.session_state.mode_szs_oc == "grid":
                if st.button("➕ New Entry", key="new_szs_oc", type="primary"):
                    st.session_state.mode_szs_oc = "entry"
                    st.rerun()
                st.divider()
                df_szs_oc = df_logs[df_logs['game_name'] == "On-Course 50-100"]
                render_icon_grid(df_szs_oc, "On-Course 50-100")
                
            elif st.session_state.mode_szs_oc == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_szs_oc"):
                    st.session_state.mode_szs_oc = "grid"
                    st.rerun()
                st.divider()
                
                c1, c2 = st.columns(2)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0.0, step=1.0, key="szs_score")
                total_shots = c2.number_input("Number of Shots Recorded", min_value=1, value=10, step=1, key="szs_shots")
                
                final_score = total_score / total_shots
                st.metric("📊 Final Average per Shot", f"{final_score:.2f}")
                
                if st.button("💾 Save On-Course Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Short", "game_name": "On-Course 50-100", "score_primary": final_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_szs_oc = "grid"
                    st.rerun()

        # --- TAB 2: TM SHORT ---
        with tabs[1]:
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
                
                if st.button("💾 Save TM Ladder Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Scoring Zone Short", "game_name": "TM 50-100", "score_primary": total_attempts, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Ladder complete and saved!")
                    st.session_state.mode_szs_tm = "grid"
                    st.rerun()
                    
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
    elif st.session_state.page == "Stock Market Analytics":
        st.title("📈 Stock Market Analytics")
        st.write("Long-term trend analysis and Personal Bests.")
