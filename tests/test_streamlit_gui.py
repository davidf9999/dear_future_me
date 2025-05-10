# tests/test_streamlit_gui.py
from unittest.mock import MagicMock, patch

import pytest

# Before importing AppTest, make sure Streamlit is installed.
# If running tests in an environment where Streamlit isn't globally available
# but is in your venv, this should be fine.
try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("Streamlit not installed, skipping Streamlit GUI tests", allow_module_level=True)

# Define the path to your Streamlit app file relative to the project root
# Assuming your tests are run from the project root.
STREAMLIT_APP_FILE = "streamlit_app.py"


# Helper to create a mock Settings object for Streamlit tests
def create_streamlit_mock_settings(lang: str = "en", **kwargs):
    from app.core.settings import (
        Settings,  # Local import to avoid issues if settings not fully loaded
    )

    return Settings(APP_DEFAULT_LANGUAGE=lang, **kwargs)  # Provide other necessary defaults if any


def test_initial_app_render_and_login_attempt_failure():
    """
    Tests if the app renders the login form initially and
    handles a failed login attempt by showing an error.
    """
    # Patch the SyncAPI client that the Streamlit app will try to import and use.
    # We want to control its behavior without making real API calls.
    mock_sync_api_instance = MagicMock()
    mock_sync_api_instance.login.side_effect = Exception("Mocked API Login Failed")  # Simulate login failure

    # Mock get_settings to control the language for the Streamlit app run
    # For this test, let's assume we want to test with English UI strings
    mock_settings_en = create_streamlit_mock_settings(lang="en")

    # The path to patch is where SyncAPI is *imported* in streamlit_app.py
    # This assumes: from app.clients.api_client import SyncAPI
    with (
        patch("app.clients.api_client.SyncAPI", return_value=mock_sync_api_instance) as mock_sync_api_class,
        patch("app.core.settings.get_settings", return_value=mock_settings_en),
    ):  # Patch the original source of get_settings
        at = AppTest.from_file(STREAMLIT_APP_FILE).run()

        # Check initial state (not logged in)
        assert at.session_state.auth_token is None
        assert len(at.sidebar.button) > 0  # Check if login/register buttons are in sidebar
        assert len(at.text_input) > 0  # Check if email/password inputs are there

        # Find specific widgets by key (keys are from your streamlit_app.py)
        email_input = at.text_input(key="auth_email_streamlit")
        password_input = at.text_input(key="auth_password_streamlit")
        login_button = at.button(key="login_btn_streamlit")

        assert email_input is not None
        assert password_input is not None
        assert login_button is not None

        # Simulate user input and button click
        email_input.input("test@example.com")
        password_input.input("wrongpassword")
        login_button.click()
        at.run()  # Re-run the script to process the interaction

        # Assertions after failed login attempt
        assert mock_sync_api_instance.login.called_once_with("test@example.com", "wrongpassword")
        assert at.session_state.auth_token is None  # Still not logged in
        assert len(at.sidebar.error) == 1  # Expecting one error message in the sidebar
        # You can get more specific about the error message text if needed:
        # assert "Login failed" in at.sidebar.error[0].value # Accessing the text of the error

        # Ensure our mocked instance is what's in session_state
        # and that the constructor of the *mocked class* was called at least once.
        assert at.session_state.api_client is mock_sync_api_instance
        mock_sync_api_class.assert_called()  # Check it was called, not necessarily once due to AppTest reruns


def test_successful_login_updates_ui_and_state():
    """
    Tests if a successful login updates the session state and UI.
    """
    mock_sync_api_instance = MagicMock()
    mock_sync_api_instance.login.return_value = "fake_auth_token"  # Simulate successful login

    # Mock get_settings to control the language for the Streamlit app run
    # Let's test with English UI strings for this assertion
    mock_settings_en = create_streamlit_mock_settings(lang="en")

    with (
        patch("app.clients.api_client.SyncAPI", return_value=mock_sync_api_instance),
        patch("app.core.settings.get_settings", return_value=mock_settings_en),
    ):  # Patch the original source of get_settings
        at = AppTest.from_file(STREAMLIT_APP_FILE).run()

        # Simulate login
        at.text_input(key="auth_email_streamlit").input("user@example.com")
        at.text_input(key="auth_password_streamlit").input("correctpassword")
        at.button(key="login_btn_streamlit").click()
        at.run()

        # Assertions after successful login
        assert mock_sync_api_instance.login.called_once_with("user@example.com", "correctpassword")
        assert at.session_state.auth_token == "fake_auth_token"
        assert at.session_state.user_email == "user@example.com"
        assert len(at.sidebar.success) == 1  # Success message "Logged in as..."
        assert at.sidebar.success[0].value.startswith(
            "Logged in as: user@example.com"
        )  # Ensure this matches the expected string from UI_STRINGS_STREAMLIT["en"]
        # Check if the logout button exists in the sidebar
        logout_button = at.sidebar.button(key="logout_btn_streamlit")
        assert logout_button is not None  # If the button doesn't exist, the line above would raise an error

        # Check that the main chat input is now available (or some other indicator of being logged in)
        # This depends on your UI structure when logged in.
        # For example, if the "Please log in..." message disappears:
        assert len(at.info) == 0  # Assuming the "Please log in..." is an st.info


# Add more tests for registration, chat interaction, logout, language changes etc.
# For chat:
# mock_sync_api_instance.chat.return_value = "Mocked AI response"
# ... simulate sending a message ...
# assert "Mocked AI response" in at.chat_message[1].markdown[0].value (adjust indices as needed)
