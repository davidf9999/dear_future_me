# /home/dfront/p/dir2ai_results/dear_future_me/tests/test_safety_plan.py
# Full file content
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.safety_plan.schemas import SafetyPlanCreate, SafetyPlanUpdate


# Helper to create a user and get token (can be moved to conftest.py if used widely)
# For now, duplicating from test_user_profile
async def register_and_login_get_token(client: TestClient, email_suffix: str) -> str:
    email = f"user_sp_{email_suffix}@example.com"  # Use a different prefix to avoid email clashes
    password = "testpassword123"

    # Register
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "is_active": True, "is_superuser": False, "is_verified": False},
    )
    assert response.status_code == 201, f"Registration failed: {response.text}"

    # Login
    login_data = {"username": email, "password": password}
    response = client.post("/auth/login", data=login_data)  # Using corrected /auth/login
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.demo_mode(False)  # Ensure registration is enabled
async def test_safety_plan_crud_flow(
    client: TestClient, db_session: AsyncSession
):  # db_session might not be needed directly if all ops via client
    token_suffix = uuid.uuid4().hex[:6]
    access_token = await register_and_login_get_token(client, token_suffix)
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Get safety plan initially - should be 404
    response = client.get("/me/safety-plan", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Safety plan not found for this user."

    # 2. Create safety plan
    # Updated data to use step_X fields
    plan_data_create = SafetyPlanCreate(
        step_1_warning_signs="Feeling overwhelmed, withdrawing from friends.",
        step_2_internal_coping="Deep breathing, listen to music, call a friend.",
        step_3_social_distractions="Call Friend X, Go to Park Y",
        step_4_help_sources="Sibling Z, Therapist T",
        step_5_professional_resources="Hotline 123, Clinic ABC",
        step_6_environment_risk_reduction="Remove items X, Y, Z",
    ).model_dump(exclude_unset=True)

    response = client.post("/me/safety-plan", json=plan_data_create, headers=headers)
    assert response.status_code == 201, response.text
    created_plan = response.json()
    # Assertions updated to use step_X fields
    assert created_plan["step_1_warning_signs"] == plan_data_create["step_1_warning_signs"]
    assert created_plan["step_2_internal_coping"] == plan_data_create["step_2_internal_coping"]
    assert "user_id" in created_plan
    plan_user_id = created_plan["user_id"]  # Will be the current user's ID

    # 3. Get safety plan - should now exist
    response = client.get("/me/safety-plan", headers=headers)
    assert response.status_code == 200
    read_plan = response.json()
    # Assertions updated to use step_X fields
    assert read_plan["step_1_warning_signs"] == plan_data_create["step_1_warning_signs"]
    assert read_plan["user_id"] == plan_user_id

    # 4. Try to create safety plan again - should be 409 Conflict
    response = client.post("/me/safety-plan", json=plan_data_create, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Safety plan already exists for this user."

    # 5. Update safety plan
    # Updated data to use step_X fields
    plan_data_update = SafetyPlanUpdate(
        step_1_warning_signs="Updated: Increased irritability.",
        step_6_environment_risk_reduction="Updated: Ensure someone is always present.",
    ).model_dump(exclude_unset=True)

    response = client.put("/me/safety-plan", json=plan_data_update, headers=headers)
    assert response.status_code == 200, response.text
    updated_plan = response.json()
    # Assertions updated to use step_X fields
    assert updated_plan["step_1_warning_signs"] == plan_data_update["step_1_warning_signs"]
    assert updated_plan["step_6_environment_risk_reduction"] == plan_data_update["step_6_environment_risk_reduction"]
    # Check that non-updated fields persist (using step_X names)
    assert updated_plan["step_2_internal_coping"] == plan_data_create["step_2_internal_coping"]
    assert updated_plan["user_id"] == plan_user_id

    # 6. Get safety plan again - should reflect updates
    response = client.get("/me/safety-plan", headers=headers)
    assert response.status_code == 200
    final_plan = response.json()
    # Assertions updated to use step_X fields
    assert final_plan["step_1_warning_signs"] == plan_data_update["step_1_warning_signs"]
    assert final_plan["step_6_environment_risk_reduction"] == plan_data_update["step_6_environment_risk_reduction"]


@pytest.mark.asyncio
async def test_safety_plan_unauthenticated_access(client: TestClient):
    # GET
    response = client.get("/me/safety-plan")
    assert response.status_code == 401  # Expect 401 Unauthorized

    # POST
    # Updated data to use step_X fields
    plan_data_create = {"step_1_warning_signs": "Test"}
    response = client.post("/me/safety-plan", json=plan_data_create)
    assert response.status_code == 401

    # PUT
    # Updated data to use step_X fields
    plan_data_update = {"step_1_warning_signs": "Test Update"}
    response = client.put("/me/safety-plan", json=plan_data_update)
    assert response.status_code == 401
