import streamlit as st

# Define user roles and their credentials
USER_ROLES = {
    "admin": ["a", "a"],
    "guest": ["guest", "guest"]
}

# Initialize session state for logged-in status
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

def login():
    # # Add logo and heading
    # st.image(r"E:\xampp\htdocs\rs\images\logors.png", width=150   )  # Replace with your logo path
    # st.header("Analysis Platform")  # Main heading

    st.title("Backtest Platform Login")  # Main title of the app


    # Create a container for the login form
    with st.form(key='login_form'):
        # Custom CSS for the input fields
        st.markdown(
            """
            <style>
            .stTextInput, .stPasswordInput {
                width: 150px;  /* Adjust the width here */
                padding: 5px;  /* Adjust padding */
                border: 1px solid #ccc;  /* Change border color */
                border-radius: 5px;  /* Rounded corners */
            }
            .stTextInput:hover, .stPasswordInput:hover {
                border: 1px solid #aaa;  /* Change border color on hover */
            }
            .stTextInput:focus, .stPasswordInput:focus {
                border: 1px solid #007bff;  /* Change border color on focus */
                outline: none;  /* Remove default outline */
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Input fields for username and password
        username = st.text_input("Username", key="username") # placeholder="guest"
        password = st.text_input("Password", type="password", key="password") #, placeholder="guest"

        # Submit button
        submit_button = st.form_submit_button("Login")

    # Validate login on button click
    if submit_button:
        for role, (user, pwd) in USER_ROLES.items():
            if username == user and password == pwd:
                st.session_state.logged_in = True
                st.session_state.role = role
                st.rerun() #https://discuss.streamlit.io/t/session-state-changes-only-after-clicking-button-twice/75997
                st.success(f"Logged in as {role}!")
                break
        else:
            st.error("Invalid username or password.")

# Call the login function
if not st.session_state.logged_in:
    login()
else:
    st.success(f"Welcome back, {st.session_state.role}!")