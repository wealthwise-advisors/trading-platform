import streamlit as st
# Set the page configuration
st.set_page_config(
    page_title="Backtest | WealthWise Advisors",
    # page_icon=r"E:\xampp\htdocs\rs\images\favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None
    }
)
import time
from login import login
from ew_backtest import ew_backtest


# Hide the Streamlit menu and footer
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stAppViewContainer"] > div:last-child {display: none;} /* Hides deploy button */
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

# def display_logo():
#     st.image(r"E:\xampp\htdocs\rs\images\logorg.png", width=150)

# Function for moving text with pip style
# def moving_text(message, delay=0.001):
#     text_placeholder = st.empty()
#     full_message = message + " "


#     # Reverse movement first
#     for i in range(len(full_message), 0, -1):
#         # text_placeholder.markdown(f"<h3 style='text-align: center;'>{full_message[:i]}{'|' if i > 0 else ''}</h3>", unsafe_allow_html=True)
#         time.sleep(delay)

#     # Forward movement
#     for i in range(len(full_message) + 1):
#         text_placeholder.markdown(f"<h3 style='text-align: center;'>{full_message[:i]}{'|' if i > 0 else ''}</h3>", unsafe_allow_html=True)
#         time.sleep(delay)

#     # Show the full message at the end
#     text_placeholder.markdown(f"<h3 style='text-align: center;'>{message}</h3>", unsafe_allow_html=True)

# Main app logic
try:
    if not st.session_state.logged_in:
        # display_logo()

        # # Columns for links
        # col1_, col2_, col3_, col4_ = st.columns([1, 1, 1, 6])
        # with col1_:
        #     st.markdown("[About SEDA Analysis](https://divyankm.github.io/Stock-Exchange-Data-Analysis/)", unsafe_allow_html=True)
        # with col2_:
        #     st.markdown("[Statistical Data](https://stats.rupeegoals.com/login)", unsafe_allow_html=True)
        # with col3_:
        #     st.markdown("[Rupee Goals](https://rupeegoals.com)", unsafe_allow_html=True)

        # Set login in progress state
        st.session_state.login_in_progress = True
        role = login()  # Call the login function

        # moving_text("In God we trust; all others bring data. — W. Edwards Deming.", delay=0.02)  
        # moving_text("Divine Insights are often found in the numbers; analyze with Faith.", delay=0.02)  
        st.session_state.login_in_progress = False  # Reset after login attempt

        if role:
            st.session_state.role = role

    else:
        # display_logo()

        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.rerun()
            st.success("You have been logged out.")

        # # Create tabs for main content
        # tab1 = st.tabs( ["EW Backtest"]) #, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs( #, "Breakout Analysis", "SuperTrend Analysis", "Mean Reversion Analysis", "ML Forecasting Models", "Discount Cash-Flow Analysis", "Pair Trade's", "Calender Spreads"])

        # with tab1:
        #     ew_backtest()

        # Creating a single tab properly
        tabs = st.tabs(["EW Backtest"])  # Returns a list of tab objects
        tab1 = tabs[0]  # Access the first tab directly

        with tab1:  # Correct way to use the 'with' statement
            ew_backtest()

        # Sidebar for guest users
        if st.session_state.role == "guest":
            st.sidebar.markdown("### Guest Access")
            st.sidebar.info("You are logged in as a guest user.")
            st.sidebar.markdown("**Settings and About pages are not available for guest users.**")

except Exception as e:
    st.error("An error occurred. Please try again later.")
    with open("error_log.txt", "a") as log_file:
        log_file.write(str(e) + "\n")