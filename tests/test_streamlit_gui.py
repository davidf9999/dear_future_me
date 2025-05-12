# # /home/dfront/code/dear_future_me/tests/test_streamlit_gui.py
# import os
# from typing import Literal
# from unittest.mock import MagicMock # Removed 'patch' as we'll use monkeypatch more directly

# import pytest
# from app.clients.api_client import SyncAPI # Import for spec

# try:
#     from streamlit.testing.v1 import AppTest
# except ImportError:
#     pytest.skip("Streamlit not installed, skipping Streamlit GUI tests", allow_module_level=True)

# STREAMLIT_APP_FILE = "frontend/streamlit_app.py" # Correct filename

# def create_streamlit_mock_settings(lang: Literal["en", "he"] = "en", **kwargs):
#     from app.core.settings import Settings
#     default_settings = {
#         "DATABASE_URL": "sqlite+aiosqlite:///./test_streamlit.db",
#         "SECRET_KEY": "testsecret_streamlit",
#         "OPENAI_API_KEY": "fake_key_streamlit",
#         "CHROMA_DB_PATH": "./data/test/chroma_streamlit",
#         "DEMO_USER_EMAIL": "streamlit@example.com",
#         "DEMO_USER_PASSWORD": "password",
#         "SKIP_AUTH": False,
#         "ACCESS_TOKEN_EXPIRE_MINUTES": 60,
#         "DFM_API_URL": "http://testhost:1234",
#         "DFM_API_HOST": "localhost",
#         "DFM_API_PORT": 8000,
#         "STREAMLIT_SERVER_PORT": 8501,
#         "DEMO_MODE": False,
#         "DEBUG_SQL": False,
#         "STREAMLIT_DEBUG": False,
#         "MAX_MESSAGE_LENGTH": 1000,
#         "ASR_TIMEOUT_SECONDS": 15.0,
#         "CHROMA_NAMESPACE_THEORY": "theory_test_st",
#         "CHROMA_NAMESPACE_PLAN": "plan_test_st",
#         "CHROMA_NAMESPACE_SESSION": "session_test_st",
#         "CHROMA_NAMESPACE_FUTURE": "future_test_st",
#         "LLM_MODEL": "gpt-3.5-turbo",
#         "LLM_TEMPERATURE": 0.7,
#     }
#     final_settings = {**default_settings, "APP_DEFAULT_LANGUAGE": lang, **kwargs}
#     return Settings(**final_settings)

# @pytest.fixture
# def mock_sync_api_instance_fixture():
#     return MagicMock(spec=SyncAPI)

# def test_initial_app_render_and_login_attempt_failure(monkeypatch, mock_sync_api_instance_fixture):
#     mock_sync_api_instance_fixture.login.side_effect = Exception("Mocked API Login Failed")

#     # Create the settings object we want the script to use
#     mock_settings_for_test = create_streamlit_mock_settings(lang="en", SKIP_AUTH=False)

#     # --- Key Change: Directly set the 'cfg' object in the target module ---
#     # This ensures that when frontend.streamlit_app is imported by AppTest,
#     # its module-level 'cfg' variable is already our mock_settings_for_test.
#     monkeypatch.setattr("frontend.streamlit_app.cfg", mock_settings_for_test)

#     # Mock load_dotenv as it's called at the module level too
#     monkeypatch.setattr("frontend.streamlit_app.load_dotenv", lambda *args, **kwargs: None)

#     # Mock the SyncAPI class so that when the script instantiates it, it gets our mock
#     monkeypatch.setattr("frontend.streamlit_app.SyncAPI", lambda *args, **kwargs: mock_sync_api_instance_fixture)

#     at = AppTest.from_file(STREAMLIT_APP_FILE, default_timeout=10).run()

#     # Use attribute access for session state, and check existence first if unsure
#     assert hasattr(at.session_state, "auth_token"), "auth_token not in session_state"
#     assert at.session_state.auth_token is None, \
#         f"Auth token was '{at.session_state.auth_token}', expected None. cfg.SKIP_AUTH was {mock_settings_for_test.SKIP_AUTH}"

#     email_input = at.sidebar.text_input(key="auth_email_streamlit")
#     password_input = at.sidebar.text_input(key="auth_password_streamlit")
#     login_button = at.sidebar.button(key="login_btn_streamlit")

#     assert email_input.value == ""
#     assert password_input.value == ""
#     assert len(login_button) == 1

#     email_input.input("test@example.com").run()
#     password_input.input("wrongpassword").run()
#     login_button.click().run()

#     mock_sync_api_instance_fixture.login.assert_called_once_with("test@example.com", "wrongpassword")
#     assert at.session_state.auth_token is None # Still None after failed login
#     assert len(at.sidebar.error) == 1
#     assert at.session_state.api_client is mock_sync_api_instance_fixture


# def test_successful_login_updates_ui_and_state(monkeypatch, mock_sync_api_instance_fixture):
#     def mock_login_success_effect(email, password):
#         mock_sync_api_instance_fixture.token = "fake_auth_token"
#     mock_sync_api_instance_fixture.login.side_effect = mock_login_success_effect

#     mock_settings_for_test = create_streamlit_mock_settings(lang="en", SKIP_AUTH=False)

#     # --- Key Change: Directly set the 'cfg' object in the target module ---
#     monkeypatch.setattr("frontend.streamlit_app.cfg", mock_settings_for_test)
#     monkeypatch.setattr("frontend.streamlit_app.load_dotenv", lambda *args, **kwargs: None)
#     monkeypatch.setattr("frontend.streamlit_app.SyncAPI", lambda *args, **kwargs: mock_sync_api_instance_fixture)

#     at = AppTest.from_file(STREAMLIT_APP_FILE, default_timeout=10).run()

#     email_input = at.sidebar.text_input(key="auth_email_streamlit")
#     password_input = at.sidebar.text_input(key="auth_password_streamlit")
#     login_button = at.sidebar.button(key="login_btn_streamlit")

#     email_input.input("user@example.com").run()
#     password_input.input("correctpassword").run()
#     login_button.click().run()

#     mock_sync_api_instance_fixture.login.assert_called_once_with("user@example.com", "correctpassword")
#     assert at.session_state.auth_token == "fake_auth_token"
#     assert at.session_state.user_email == "user@example.com"
#     assert len(at.sidebar.success) == 1
#     assert at.sidebar.success[0].value == "Logged in as: user@example.com"
#     assert len(at.sidebar.button(key="logout_btn_streamlit")) == 1

#     with pytest.raises(KeyError):
#         at.sidebar.text_input(key="auth_email_streamlit")

#     assert at.session_state.api_client is mock_sync_api_instance_fixture
