# /home/dfront/code/dear_future_me/tests/test_safety_plan.py
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
    plan_data_create = SafetyPlanCreate(
        warning_signs="Feeling overwhelmed, withdrawing from friends.",
        coping_strategies="Deep breathing, listen to music, call a friend.",
        emergency_contacts="Friend: 123-456-7890, Sibling: 098-765-4321",
        professional_help_contacts="Therapist Dr. Smith: 555-1212, Crisis Line: 988",
        safe_environment_notes="Remove sharp objects, ensure someone is with me.",
        reasons_for_living="My family, my pets, future goals.",
    ).model_dump(exclude_unset=True)

    response = client.post("/me/safety-plan", json=plan_data_create, headers=headers)
    assert response.status_code == 201, response.text
    created_plan = response.json()
    assert created_plan["warning_signs"] == plan_data_create["warning_signs"]
    assert created_plan["coping_strategies"] == plan_data_create["coping_strategies"]
    assert "user_id" in created_plan
    plan_user_id = created_plan["user_id"]  # Will be the current user's ID

    # 3. Get safety plan - should now exist
    response = client.get("/me/safety-plan", headers=headers)
    assert response.status_code == 200
    read_plan = response.json()
    assert read_plan["warning_signs"] == plan_data_create["warning_signs"]
    assert read_plan["user_id"] == plan_user_id

    # 4. Try to create safety plan again - should be 409 Conflict
    response = client.post("/me/safety-plan", json=plan_data_create, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Safety plan already exists for this user."

    # 5. Update safety plan
    plan_data_update = SafetyPlanUpdate(
        warning_signs="Updated: Increased irritability.",
        reasons_for_living="Updated: My family, my pets, future goals, and making a difference.",
    ).model_dump(exclude_unset=True)

    response = client.put("/me/safety-plan", json=plan_data_update, headers=headers)
    assert response.status_code == 200, response.text
    updated_plan = response.json()
    assert updated_plan["warning_signs"] == plan_data_update["warning_signs"]
    assert updated_plan["reasons_for_living"] == plan_data_update["reasons_for_living"]
    # Check that non-updated fields persist
    assert updated_plan["coping_strategies"] == plan_data_create["coping_strategies"]
    assert updated_plan["user_id"] == plan_user_id

    # 6. Get safety plan again - should reflect updates
    response = client.get("/me/safety-plan", headers=headers)
    assert response.status_code == 200
    final_plan = response.json()
    assert final_plan["warning_signs"] == plan_data_update["warning_signs"]
    assert final_plan["reasons_for_living"] == plan_data_update["reasons_for_living"]


@pytest.mark.asyncio
async def test_safety_plan_unauthenticated_access(client: TestClient):
    # GET
    response = client.get("/me/safety-plan")
    assert response.status_code == 401  # Expect 401 Unauthorized

    # POST
    plan_data_create = {"warning_signs": "Test"}
    response = client.post("/me/safety-plan", json=plan_data_create)
    assert response.status_code == 401

    # PUT
    plan_data_update = {"warning_signs": "Test Update"}
    response = client.put("/me/safety-plan", json=plan_data_update)
    assert response.status_code == 401
