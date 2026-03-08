import streamlit as st
import pandas as pd
import altair as alt
import datetime
import pytz
import json
from supabase import create_client

# --- 1. APP CONFIG & PREMIUM CSS ---
st.set_page_config(page_title="Golf Practice Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Montserrat:wght@300;400;600&display=swap');
    
    /* Safely target text elements without overpowering Streamlit's UI classes */
    html, body, p, div, label, li, span, .stMarkdown, .stText {
        font-family: 'Montserrat', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        font-weight: 600 !important;
    }
    
    /* Re-enforce the Material Icons font specifically for UI elements */
    .material-symbols-rounded, .stIcon, [data-testid="stIconMaterial"], i, svg {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    /* Lock the charts from touch interactions */
    [data-testid="stArrowVegaLiteChart"], canvas { 
        pointer-events: none !important; 
    }
    
    /* Center align the numbers in the mobile matrices */
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
                
                # 2. Format Score based on the specific game
                if game_name == "Max SS/BS":
                    score_str = f"{row['score_primary']:.0f} / {row['score_secondary']:.0f}"
                elif game_name in ["20 to 50"]:
                    score_str = f"{row['score_primary']:.0f}%" # Whole number with percentage
                elif game_name in ["Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-8 Drill", "6-9-12"]: 
                    score_str = f"{row['score_primary']:.0f}" # Clean whole numbers
                else:
                    score_str = f"{row['score_primary']:.1f}" # Decimals for averages

                # 3. Render Date and Score dynamically based on light/dark mode
                st.markdown(f"""
                <div style='text-align: center; padding: 5px; margin-bottom: 10px;'>
                    <span style='color: gray; font-size: 0.9em;'>🗂️ {date_str}</span><br>
                    <b style='font-size: 1.6em; color: var(--text-color);'>{score_str}</b>
                </div>
                """, unsafe_allow_html=True)
                
                # 4. Action Buttons
                c1, c2 = st.columns(2)
                
                # 4a. The "View" Popover (Reads your JSON Locker!)
                with c1.popover("👁️ View", use_container_width=True):
                    st.markdown("**Session Data:**")
                    # Check if this specific game saved a raw_data matrix
                    if isinstance(row['raw_data'], list) and len(row['raw_data']) > 0:
                        df_view = pd.DataFrame(row['raw_data'])
                        st.dataframe(df_view, hide_index=True, use_container_width=True)
                    else:
                        st.write(f"**Score:** {score_str}")
                        st.caption("Manual entry game (no matrix data).")
                
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
        "Your practice trends"
    ]
    
    for opt in nav_options:
        if st.sidebar.button(opt, use_container_width=True, type="primary" if st.session_state.page == opt else "secondary"):
            st.session_state.page = opt
            st.rerun()

    # -- SUNDAY DEADLINE WARNING --
    if is_sunday:
        st.warning("⚠️ **Reminder: Today is Sunday!** Your Weekly Dashboard resets tonight at midnight.")

    # ==========================================
    # PAGE: WEEKLY DASHBOARD
    # ==========================================
    if st.session_state.page == "Weekly Dashboard":
        st.title(f"📊 Week {current_week} Dashboard")
        st.write("Track your practice completion and weekly highlights.")
        
        # 1. Filter data purely for the current week and year
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'])
        df_week = df_logs[
            (df_logs['created_at'].dt.isocalendar().week == current_week) & 
            (df_logs['created_at'].dt.isocalendar().year == current_year)
        ].copy()
        
        # 2. Define the exact Combine Categories and their Games (Maintains strict order)
        combine_structure = {
            "Driving": ["10 Shot", "Max SS/BS"],
            "Scoring Zone Long": ["On-Course 150-200", "TM 150-200"],
            "Scoring Zone Mid": ["On-Course 100-150", "TM 100-150"],
            "Scoring Zone Short": ["On-Course 50-100", "TM 50-100"],
            "Short Game": ["Par 21 WB", "20 to 50", "6ft Game"],
            "Putting": ["Pace", "6-9-12", "2-8 Drill"]
        }
        
        core_categories = list(combine_structure.keys())
        
        # Check completion
        completed_games_this_week = df_week['game_name'].dropna().unique().tolist()
        completed_cats_this_week = df_week['game_category'].dropna().unique().tolist()
        
        completion_count = len([c for c in core_categories if c in completed_cats_this_week])
        progress_pct = completion_count / len(core_categories)
        
        # 3. Render Progress Section
        st.subheader("🎯 Weekly Combine Checklist")
        st.progress(progress_pct, text=f"Combine Completion: {completion_count} / {len(core_categories)} Categories")
        
        st.write("<br>", unsafe_allow_html=True) # Spacer
        
        # Render visual accordion checklist with navigation buttons
        for cat, games in combine_structure.items():
            is_cat_complete = cat in completed_cats_this_week
            cat_icon = "✅" if is_cat_complete else "⏳"
            
            with st.expander(f"{cat_icon} **{cat}**"):
                for game in games:
                    is_game_complete = game in completed_games_this_week
                    game_icon = "✅" if is_game_complete else "⭕"
                    
                    # Layout: Game name on the left, Button on the right
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"{game_icon}  {game}")
                    
                    if col2.button("Practice ➡️", key=f"nav_{cat}_{game}", use_container_width=True):
                        # Route the user directly to the category page
                        st.session_state.page = cat
                        st.rerun()
            
        st.divider()
        
        # 4. Weekly Highlights / Recent Activity
        st.subheader("📝 This Week's Logged Sessions")
        
        if df_week.empty:
            st.info("No practice logged yet this week. Use the checklist above to start your combine!")
        else:
            # Sort newest first
            df_week = df_week.sort_values('created_at', ascending=False)
            
            # Format a clean, human-readable dataframe for viewing
            df_display = df_week[['created_at', 'game_category', 'game_name', 'score_primary', 'score_secondary']].copy()
            df_display['created_at'] = df_display['created_at'].dt.strftime('%A, %b %d')
            
            # Clean up the display column names
            df_display.rename(columns={
                'created_at': 'Date',
                'game_category': 'Category',
                'game_name': 'Drill',
                'score_primary': 'Score',
                'score_secondary': 'Secondary Score'
            }, inplace=True)
            
            # Fill NaN secondary scores with a dash so it looks premium
            df_display['Secondary Score'] = df_display['Secondary Score'].fillna("-")
            
            st.dataframe(df_display, hide_index=True, use_container_width=True)
            
            # 5. Quick Insights
            st.write("<br>", unsafe_allow_html=True)
            st.subheader("⚡ Weekly Insights")
            c1, c2 = st.columns(2)
            c1.metric("Total Sessions Logged", len(df_week))
            
            # Find the most practiced category this week
            top_cat = df_week['game_category'].mode()
            if not top_cat.empty:
                c2.metric("Most Practiced Category", top_cat.iloc[0])
            else:
                c2.metric("Most Practiced Category", "N/A")

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
            st.write("*Log your 150-200 yards/meter scoring zone scores when you practice on the course.*")
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
                # value=0 forces this to be a whole number (integer)
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1)
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
            st.write("*Log your 100-150 yards/meter scoring zone scores when you practice on the course.*")
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
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1, key="szm_score")
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
    # PAGE: SCORING ZONE SHORT
    # ==========================================
    elif st.session_state.page == "Scoring Zone Short":
        st.title("🎯 Scoring Zone Short (50-100)")
        
        if 'mode_szs_oc' not in st.session_state: st.session_state.mode_szs_oc = "grid"
        if 'mode_szs_tm' not in st.session_state: st.session_state.mode_szs_tm = "grid"

        tabs = st.tabs(["On-Course 50-100", "TM 50-100"])
        
        # --- TAB 1: ON-COURSE SHORT ---
        with tabs[0]:
            st.write("*Log your 50-100 yards/meter scoring zone scores when you practice on the course.*")
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
                total_score = c1.number_input("Total Score to Par (e.g., -2 or +3)", value=0, step=1, key="szs_score")
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
                    
    # ==========================================
    # PAGE: SHORT GAME
    # ==========================================
    elif st.session_state.page == "Short Game":
        st.title("🪤 Short Game Combine")
        
        if 'mode_sg_par21' not in st.session_state: st.session_state.mode_sg_par21 = "grid"
        if 'mode_sg_2050' not in st.session_state: st.session_state.mode_sg_2050 = "grid"
        if 'mode_sg_6ft' not in st.session_state: st.session_state.mode_sg_6ft = "grid"

        tabs = st.tabs(["Par 21 WB", "20 to 50", "6ft Game"])
        
        # --- TAB 1: PAR 21 WB ---
        with tabs[0]:
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
                
                if st.button("💾 Save Par 21 Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": "Par 21 WB", "score_primary": final_score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_sg_par21 = "grid"
                    st.rerun()

        # --- TAB 2: 20 TO 50 MATRIX ---
        with tabs[1]:
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
                st.caption("Tap cells to enter how many shots landed in each zone (0-5).")
                
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
                
                # Cumulative Math calculations (Assuming 20 total shots for the game)
                tot_3ft_only = edited_df["3ft"].sum()
                tot_6ft_only = edited_df["6ft"].sum()
                tot_10ft_only = edited_df["10ft"].sum()
                
                # Add inner circles to outer circles
                cum_3ft = tot_3ft_only
                cum_6ft = tot_3ft_only + tot_6ft_only
                cum_10ft = tot_3ft_only + tot_6ft_only + tot_10ft_only
                
                pct_3ft = (cum_3ft / 20.0) * 100
                pct_6ft = (cum_6ft / 20.0) * 100
                pct_10ft = (cum_10ft / 20.0) * 100
                
                # Final score is strictly the 6ft cumulative accuracy
                final_pct = pct_6ft 
                
                # Validation check warning to prevent bad math
                row_sums = edited_df["3ft"] + edited_df["6ft"] + edited_df["10ft"]
                if (row_sums > 5).any():
                    st.warning("⚠️ Careful! One of your yardage rows adds up to more than 5 shots. Please correct it to save.")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("3ft Accuracy", f"{pct_3ft:.0f}%")
                c2.metric("6ft Accuracy", f"{pct_6ft:.0f}%")
                c3.metric("10ft Accuracy", f"{pct_10ft:.0f}%")
                
                st.divider()
                st.metric("🎯 Final Combined Score (6ft Accuracy)", f"{final_pct:.0f}%")
                
                # Disable the save button if a row has more than 5 shots recorded
                if st.button("💾 Save 20 to 50 Log", type="primary", use_container_width=True, disabled=(row_sums > 5).any()):
                    raw_json = edited_df.to_dict(orient='records')
                    data = {
                        "user_name": st.session_state.current_user,
                        "game_category": "Short Game",
                        "game_name": "20 to 50",
                        "score_primary": final_pct,
                        "raw_data": raw_json,
                        "week_number": current_week
                    }
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    del st.session_state['df_2050_matrix']
                    st.session_state.mode_sg_2050 = "grid"
                    st.rerun()

        # --- TAB 3: 6FT GAME ---
        with tabs[2]:
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
                
                if st.button("💾 Save 6ft Game Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Short Game", "game_name": "6ft Game", "score_primary": holes_played, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_sg_6ft = "grid"
                    st.rerun()
                    
    # ==========================================
    # PAGE: PUTTING
    # ==========================================
    elif st.session_state.page == "Putting":
        st.title("⛳ Putting Combine")
        
        if 'mode_putt_pace' not in st.session_state: st.session_state.mode_putt_pace = "grid"
        if 'mode_putt_6912' not in st.session_state: st.session_state.mode_putt_6912 = "grid"
        if 'mode_putt_28' not in st.session_state: st.session_state.mode_putt_28 = "grid"

        tabs = st.tabs(["Pace (Lag)", "6-9-12", "2-8 Drill"])
        
        # --- TAB 1: PACE (LAG) ---
        with tabs[0]:
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
                
                if st.button("💾 Save Pace Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "Pace", "score_primary": score, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_pace = "grid"
                    st.rerun()

        # --- TAB 2: 6-9-12 ---
        with tabs[1]:
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
                
                if st.button("💾 Save 6-9-12 Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "6-9-12", "score_primary": total_putts, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_6912 = "grid"
                    st.rerun()

        # --- TAB 3: 2-8 DRILL ---
        with tabs[2]:
            st.write("*Ladder drill: Make a putt from 2ft, 3ft, 4ft, 5ft, 6ft, 7ft, and 8ft consecutively.*")
            st.caption("**Rules:** If you miss, you must start over at 2ft. Record the total number of putts it took to complete the ladder. *Note: You can randomise the order of distances to increase difficulty.*")
            
            if st.session_state.mode_putt_28 == "grid":
                if st.button("➕ New Entry", key="new_putt_28", type="primary"):
                    st.session_state.mode_putt_28 = "entry"
                    st.rerun()
                st.divider()
                df_putt_28 = df_logs[df_logs['game_name'] == "2-8 Drill"]
                render_icon_grid(df_putt_28, "2-8 Drill")
                
            elif st.session_state.mode_putt_28 == "entry":
                if st.button("🔙 Back to Previous Entries", key="back_putt_28"):
                    st.session_state.mode_putt_28 = "grid"
                    st.rerun()
                st.divider()
                
                attempts = st.number_input("Total Putts Hit to Complete Ladder", min_value=7, value=15, step=1)
                
                if st.button("💾 Save 2-8 Drill Log", type="primary", use_container_width=True):
                    data = {"user_name": st.session_state.current_user, "game_category": "Putting", "game_name": "2-8 Drill", "score_primary": attempts, "week_number": current_week}
                    supabase.table("practice_logs").insert(data).execute()
                    st.success("Saved!")
                    st.session_state.mode_putt_28 = "grid"
                    st.rerun()

    # ==========================================
    # PAGE: YOUR PRACTICE TRENDS
    # ==========================================
    elif st.session_state.page.lower() == "your practice trends":
        st.title("📈 Your Practice Trends")
        st.write("Track your long-term progress, historical averages, and Running Baselines.")
        
        # Double CSS Lock: Ensures no zooming/scrolling glitches with your finger
        st.markdown("""
            <style>
            [data-testid="stVegaLiteChart"], canvas { 
                pointer-events: none !important; 
            }
            </style>
        """, unsafe_allow_html=True)
        
        if df_logs.empty:
            st.info("No practice data logged yet. Head to the combine pages to log your first session!")
        else:
            analysis_mode = st.radio(
                "Choose Analysis Mode:", 
                ["🎯 Individual Drills (Absolute Scores)", "📈 Entire Category (Running Baseline)"], 
                horizontal=True
            )
            st.divider()
            
            # ==========================================
            # MODE A: INDIVIDUAL DRILLS
            # ==========================================
            if analysis_mode == "🎯 Individual Drills (Absolute Scores)":
                col_a, col_b = st.columns(2)
                available_games = sorted(df_logs['game_name'].unique().tolist())
                selected_game = col_a.selectbox("Select a Drill to Analyze", available_games)
                
                timeline = col_b.selectbox(
                    "Select Timeframe", 
                    ["Weekly Averages", "Monthly Averages", "6-Month Averages", "Yearly Averages"]
                )
                
                df_trend = df_logs[df_logs['game_name'] == selected_game].copy()
                df_trend['created_at'] = pd.to_datetime(df_trend['created_at'])
                
                lower_is_better_games = ["On-Course 150-200", "On-Course 100-150", "On-Course 50-100", 
                                         "TM 50-100", "Par 21 WB", "6ft Game", "6-9-12", "2-8 Drill"]
                is_lower_better = selected_game in lower_is_better_games
                
                if selected_game == "Max SS/BS":
                    pb_ss = df_trend['score_primary'].max()
                    pb_bs = df_trend['score_secondary'].max()
                    avg_ss = df_trend['score_primary'].mean()
                    avg_bs = df_trend['score_secondary'].mean()
                else:
                    pb = df_trend['score_primary'].min() if is_lower_better else df_trend['score_primary'].max()
                    avg = df_trend['score_primary'].mean()
                    
                # Chronological Sorting Engine
                if timeline == "Weekly Averages":
                    df_trend['Period_Sort'] = df_trend['created_at'].dt.to_period('W').dt.start_time
                    df_trend['Group'] = df_trend['created_at'].dt.strftime('Week %V, %Y')
                elif timeline == "Monthly Averages":
                    df_trend['Period_Sort'] = df_trend['created_at'].dt.to_period('M').dt.start_time
                    df_trend['Group'] = df_trend['created_at'].dt.strftime('%b %Y')
                elif timeline == "6-Month Averages":
                    df_trend['half'] = df_trend['created_at'].dt.month.apply(lambda m: "H1" if m <= 6 else "H2")
                    df_trend['Period_Sort'] = pd.to_datetime(df_trend['created_at'].dt.strftime('%Y') + df_trend['half'].apply(lambda x: '-01-01' if x == 'H1' else '-07-01'))
                    df_trend['Group'] = df_trend['created_at'].dt.strftime('%Y') + " " + df_trend['half']
                elif timeline == "Yearly Averages":
                    df_trend['Period_Sort'] = df_trend['created_at'].dt.to_period('Y').dt.start_time
                    df_trend['Group'] = df_trend['created_at'].dt.strftime('%Y')
                    
                df_trend = df_trend.sort_values('Period_Sort')
                    
                if selected_game == "Max SS/BS":
                    df_agg = df_trend.groupby(['Period_Sort', 'Group'], sort=False)[['score_primary', 'score_secondary']].max().reset_index()
                    df_chart = df_agg.copy()
                    
                    c1, c2 = st.columns(2)
                    c1.metric("🏆 All-Time Personal Best", f"{pb_ss:.0f} / {pb_bs:.0f}")
                    c2.metric("📊 All-Time Average", f"{avg_ss:.0f} / {avg_bs:.0f}")
                    
                    # Smart Zooming Line Chart for Swing Speed
                    ss_chart = alt.Chart(df_chart).mark_line(
                        point=alt.OverlayMarkDef(color="#FF4B4B", size=100, filled=True), 
                        color="#FF4B4B", strokeWidth=3
                    ).encode(
                        x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45)),
                        y=alt.Y('score_primary:Q', scale=alt.Scale(zero=False), title="Swing Speed (mph)"),
                        tooltip=[]
                    ).properties(height=250)
                    
                    st.write(f"### Swing Speed History ({timeline})")
                    st.altair_chart(ss_chart, use_container_width=True) 

                    # Smart Zooming Line Chart for Ball Speed
                    bs_chart = alt.Chart(df_chart).mark_line(
                        point=alt.OverlayMarkDef(color="#0068C9", size=100, filled=True), 
                        color="#0068C9", strokeWidth=3
                    ).encode(
                        x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45)),
                        y=alt.Y('score_secondary:Q', scale=alt.Scale(zero=False), title="Ball Speed (mph)"),
                        tooltip=[]
                    ).properties(height=250)
                    
                    st.write(f"### Ball Speed History ({timeline})")
                    st.altair_chart(bs_chart, use_container_width=True) 
                else:
                    df_agg = df_trend.groupby(['Period_Sort', 'Group'], sort=False)['score_primary'].mean().reset_index()
                    df_chart = df_agg.copy()
                    
                    if selected_game in ["20 to 50"]:
                        pb_str, avg_str = f"{pb:.0f}%", f"{avg:.0f}%"
                    elif selected_game in ["Par 21 WB", "6ft Game", "TM 50-100", "Pace", "2-8 Drill", "6-9-12"]:
                        pb_str, avg_str = f"{pb:.0f}", f"{avg:.0f}"
                    else:
                        pb_str, avg_str = f"{pb:.2f}", f"{avg:.2f}"
                        
                    c1, c2 = st.columns(2)
                    c1.metric("🏆 All-Time Personal Best", pb_str)
                    c2.metric("📊 All-Time Average", avg_str)
                    
                    # Smart Zooming Line Chart for General Drills
                    chart = alt.Chart(df_chart).mark_line(
                        point=alt.OverlayMarkDef(color="#0068C9", size=100, filled=True), 
                        color="#0068C9", strokeWidth=3
                    ).encode(
                        x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45)),
                        y=alt.Y('score_primary:Q', scale=alt.Scale(zero=False), title="Score"),
                        tooltip=[]
                    ).properties(height=300)
                    
                    st.write(f"### Performance History ({timeline})")
                    st.altair_chart(chart, use_container_width=True)

            # ==========================================
            # MODE B: ENTIRE CATEGORY (RUNNING BASELINE)
            # ==========================================
            elif analysis_mode == "📈 Entire Category (Running Baseline)":
                st.write("*This engine tracks 'Recent Form'. It calculates the percentage improvement for every drill in a category compared to the previous timeframe, showing your overall trend direction.*")
                
                col_a, col_b = st.columns(2)
                categories = sorted(df_logs['game_category'].dropna().unique().tolist())
                selected_cat = col_a.selectbox("Select Category", categories)
                
                timeline = col_b.selectbox(
                    "Select Timeframe", 
                    ["Weekly Averages", "Monthly Averages", "6-Month Averages", "Yearly Averages"],
                    key="cat_timeline"
                )
                
                df_cat = df_logs[df_logs['game_category'] == selected_cat].copy()
                df_cat['created_at'] = pd.to_datetime(df_cat['created_at'])
                
                # Chronological Sorting Engine
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
                
                df_agg = df_cat.groupby(['Period_Sort', 'Group', 'game_name'])['score_primary'].mean().reset_index()
                pivot = df_agg.pivot(index=['Period_Sort', 'Group'], columns='game_name', values='score_primary')
                pivot = pivot.sort_index()
                
                if len(pivot) < 2:
                    st.warning(f"⏳ **More data needed.** You only have one period of data for {selected_cat}. The Running Baseline requires at least two periods to calculate your momentum. Log another session next week!")
                else:
                    pct_diff = pivot.pct_change() * 100
                    
                    lower_is_better_games = ["On-Course 150-200", "On-Course 100-150", "On-Course 50-100", "TM 50-100", "Par 21 WB", "6ft Game", "6-9-12", "2-8 Drill"]
                    for col in pct_diff.columns:
                        if col in lower_is_better_games:
                            pct_diff[col] = pct_diff[col] * -1 
                            
                    category_momentum = pct_diff.mean(axis=1).dropna()
                    
                    chart_df = pd.DataFrame(category_momentum, columns=["Momentum Delta (%)"]).reset_index()
                    latest_momentum = category_momentum.iloc[-1]
                    
                    st.metric(
                        f"Current {selected_cat} Momentum", 
                        f"{latest_momentum:+.1f}%", 
                        delta=f"{latest_momentum:+.1f}% improvement vs previous period",
                        delta_color="normal"
                    )
                    
                    # Momentum uses Bar Charts because they safely originate from 0
                    mom_chart = alt.Chart(chart_df).mark_bar().encode(
                        x=alt.X('Group:N', axis=alt.Axis(title="", labelAngle=-45)),
                        y=alt.Y('Momentum Delta (%):Q', title="Momentum (%)"), 
                        color=alt.condition(
                            alt.datum['Momentum Delta (%)'] > 0,
                            alt.value("#0068C9"),  # Blue for improvement
                            alt.value("#FF4B4B")   # Red for regression
                        ),
                        tooltip=[]
                    ).properties(height=300)
                    
                    st.write(f"### {selected_cat} Running Baseline Chart")
                    st.caption("Blue bars mean you are improving. Red bars mean regression.")
                    st.altair_chart(mom_chart, use_container_width=True)
