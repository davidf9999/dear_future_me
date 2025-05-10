# streamlit_app.py
import os
import sys

import streamlit as st
from dotenv import load_dotenv

# Add project root to sys.path to allow 'from app...' imports
# This is necessary if streamlit_app.py is in the project root
# and you're importing from the 'app' package.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now that sys.path is configured, we can import from 'app'
try:
    from app.clients.api_client import SyncAPI  # Using the synchronous client
    from app.core.settings import Settings, get_settings
except ImportError as e:
    st.error(
        f"Failed to import necessary modules. Ensure app structure is correct and all dependencies are installed. Error: {e}"
    )
    st.stop()


# --- App Configuration & Initialization ---
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))  # Load .env from project root

try:
    cfg: Settings = get_settings()
except Exception as e:
    st.error(f"Error loading application settings. Please check your .env file. Error: {e}")
    st.stop()

API_BASE_URL = os.getenv("DFM_API_URL", "http://localhost:8000")

# --- Language Strings (similar to cli.py, but for Streamlit UI elements) ---
UI_STRINGS_STREAMLIT = {
    "en": {
        "page_title": "Dear Future Me - Chat",
        "header": "Chat with your Future Self",
        "email_label": "Email",
        "password_label": "Password",
        "login_button": "Login",
        "register_button": "Register",
        "logout_button": "Logout",
        "chat_input_placeholder": "Type your message here...",
        "auth_error_login": "Login failed. Please check credentials.",
        "auth_error_generic": "Authentication error.",
        "reg_success": "Registration successful! Please log in.",
        "reg_error": "Registration failed. User might already exist or server error.",
        "logged_in_as": "Logged in as: {email}",
        "not_logged_in_sidebar_header": "Login / Register",
        "not_logged_in_main_message": "Please log in or register using the sidebar to start chatting.",
        "send_button": "Send",
        "welcome_message_user": "Hello!",
        "welcome_message_assistant": "Hello! How can I help you today?",
        "empty_credentials_warning": "Please enter both email and password.",
        "api_connection_error": "Could not connect to the API server. Please ensure it's running.",
        "chat_error": "Error getting response from AI.",
        "help_link_text": "Help / Readme",
    },
    "he": {
        "page_title": "אני מהעתיד - צ'אט",
        "header": "שוחח/י עם האני העתידי שלך",
        "email_label": "אימייל",
        "password_label": "סיסמה",
        "login_button": "התחבר",
        "register_button": "הירשם",
        "logout_button": "התנתק",
        "chat_input_placeholder": "הקלד/י את הודעתך כאן...",
        "auth_error_login": "ההתחברות נכשלה. אנא בדוק/בדקי פרטים.",
        "auth_error_generic": "שגיאת אימות.",
        "reg_success": "ההרשמה הצליחה! אנא התחבר/י.",
        "reg_error": "ההרשמה נכשלה. ייתכן שהמשתמש כבר קיים או שיש שגיאת שרת.",
        "logged_in_as": "מחובר/ת כ: {email}",
        "not_logged_in_sidebar_header": "התחברות / הרשמה",
        "not_logged_in_main_message": "אנא התחבר/י או הירשם/הירשמי דרך סרגל הצד כדי להתחיל לשוחח.",
        "send_button": "שלח",
        "welcome_message_user": "שלום!",
        "welcome_message_assistant": "שלום! איך אוכל לעזור לך היום?",
        "empty_credentials_warning": "אנא הזן/הזיני גם אימייל וגם סיסמה.",
        "api_connection_error": "לא ניתן להתחבר לשרת ה-API. אנא ודא/י שהוא פועל.",
        "chat_error": "שגיאה בקבלת תגובה מהבינה המלאכותית.",
        "help_link_text": "עזרה / קרא אותי",
    },
}

# --- Initialize Session State ---
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_language" not in st.session_state:
    st.session_state.current_language = cfg.APP_DEFAULT_LANGUAGE
if "api_client" not in st.session_state:
    try:
        st.session_state.api_client = SyncAPI(API_BASE_URL)
    except Exception as e:
        st.error(f"Failed to initialize API client: {e}")
        st.stop()

api: SyncAPI = st.session_state.api_client
STR = UI_STRINGS_STREAMLIT.get(st.session_state.current_language, UI_STRINGS_STREAMLIT["en"])

# --- Page Setup ---
st.set_page_config(page_title=STR["page_title"], layout="wide")  # Use "wide" for better chat layout
st.title(STR["header"])

# --- Apply RTL styling if current language is Hebrew ---
if st.session_state.current_language == "he":
    st.markdown(
        """
        <style>
        /* Make main content area RTL */
        div[data-testid="stAppViewContainer"] > section[data-testid="stVerticalBlock"] > div.block-container {
            direction: rtl;
            text-align: right;
        }
        /* Make sidebar *content* RTL, but sidebar itself still opens from left */
        .stSidebar section[data-testid="stSidebarUserContent"] {
            direction: rtl;
            text-align: right;
        }
        /* Ensure text inputs, text areas, and chat inputs are RTL for text entry */
        div[data-testid="stTextInput"] input, 
        div[data-testid="stTextArea"] textarea, /* For multiline inputs if any */
        div[data-testid="stChatInput"] textarea {
            direction: rtl;
            text-align: right;
        }
        /* Specific for chat messages to ensure they align right */
        div[data-testid="stChatMessage"] {
            direction: rtl;
            text-align: right;
        }
        /* Ensure standard text elements within the main content and sidebar also align right */
        div[data-testid="stAppViewContainer"] div[data-testid="stMarkdownContainer"],
        .stSidebar div[data-testid="stMarkdownContainer"] {
            text-align: right; /* Markdown content */
        }
        /* Target labels of widgets like st.text_input in the sidebar */
        .stSidebar div[data-testid="stWidgetLabel"] label {
            direction: rtl; /* Ensure label text flows RTL */
            text-align: right; /* Align label text to the right */
            width: 100%; /* Make label take full width to allow text-align to work */
        }
        /* You might need to add more specific selectors if some elements still misbehave */
        </style>
    """,
        unsafe_allow_html=True,
    )

# --- Language Selection (Optional UI Element) ---
# lang_options = {"English": "en", "עברית (Hebrew)": "he"}
# selected_lang_display = st.sidebar.selectbox(
#     "Language / שפה",
#     options=list(lang_options.keys()),
#     index=list(lang_options.values()).index(st.session_state.current_language)
# )
# if lang_options[selected_lang_display] != st.session_state.current_language:
#     st.session_state.current_language = lang_options[selected_lang_display]
#     STR = UI_STRINGS_STREAMLIT.get(st.session_state.current_language, UI_STRINGS_STREAMLIT["en"])
#     st.rerun()


# --- Authentication Section in Sidebar ---
with st.sidebar:
    if not st.session_state.auth_token:
        st.subheader(STR["not_logged_in_sidebar_header"])
        email_input = st.text_input(STR["email_label"], key="auth_email_streamlit")
        password_input = st.text_input(STR["password_label"], type="password", key="auth_password_streamlit")

        col1, col2 = st.columns(2)
        if col1.button(STR["login_button"], key="login_btn_streamlit", use_container_width=True):
            if email_input and password_input:
                try:
                    token = api.login(email_input, password_input)
                    st.session_state.auth_token = token
                    st.session_state.user_email = email_input
                    # api._token is managed internally by SyncAPI after login
                    st.session_state.messages = []  # Clear messages on new login
                    st.rerun()
                except Exception as e:
                    st.error(f"{STR['auth_error_login']} {e}")
            else:
                st.warning(STR["empty_credentials_warning"])

        if col2.button(STR["register_button"], key="register_btn_streamlit", use_container_width=True):
            if email_input and password_input:
                try:
                    api.register(email_input, password_input, first_name="Streamlit", last_name="User")
                    st.success(STR["reg_success"])
                except Exception as e:
                    st.error(f"{STR['reg_error']} {e}")
            else:
                st.warning(STR["empty_credentials_warning"])
    else:
        st.success(STR["logged_in_as"].format(email=st.session_state.user_email))
        if st.button(STR["logout_button"], key="logout_btn_streamlit", use_container_width=True):
            st.session_state.auth_token = None
            st.session_state.user_email = None
            api._token = None  # Explicitly clear token in shared API client instance
            st.session_state.messages = []
            st.rerun()

    st.sidebar.markdown("---")  # Separator
    # Add a link to the README on GitHub (replace with your actual repo URL)
    # Uncomment if the repo will be public
    # readme_url = (
    #     "https://github.com/dfront/dear_future_me/blob/main/README.md"  # FIXME: Update with your actual repo URL
    # )
    # st.sidebar.markdown(f"[{STR.get('help_link_text', 'Help / Readme')}]({readme_url})")


# --- Chat Section (Main Area) ---
if st.session_state.auth_token:
    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input(STR["chat_input_placeholder"], key="chat_prompt_input"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            try:
                assistant_response = api.chat(prompt)  # SyncAPI.chat is synchronous
                message_placeholder.markdown(assistant_response)
            except Exception as e:
                st.error(f"{STR['chat_error']}: {e}")
                assistant_response = f"Sorry, I encountered an error: {e}"  # Provide error to user
                message_placeholder.markdown(assistant_response)

            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
else:
    st.info(STR["not_logged_in_main_message"])

# --- To run this app: streamlit run streamlit_app.py ---
# Ensure the FastAPI server (app.main:app) is running separately.
