# tests/test_user_profile.py
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserProfileCreate, UserProfileUpdate


# Helper to create a user and get token (can be moved to conftest.py if used widely)
async def register_and_login_get_token(client: TestClient, email_suffix: str) -> str:
    email = f"user_{email_suffix}@example.com"
    password = "testpassword123"

    # Register
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "is_active": True, "is_superuser": False, "is_verified": False},
    )
    assert response.status_code == 201, f"Registration failed: {response.text}"

    # Login
    login_data = {"username": email, "password": password}
    # Corrected login URL from /auth/jwt/login to /auth/login
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.demo_mode(False)  # Ensure registration is enabled
async def test_user_profile_crud_flow(client: TestClient, db_session: AsyncSession):
    token_suffix = uuid.uuid4().hex[:6]
    access_token = await register_and_login_get_token(client, token_suffix)
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Get profile initially - should be 404
    response = client.get("/me/profile", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found for this user."

    # 2. Create profile
    profile_data_create = UserProfileCreate(
        name="Test User Alpha", future_me_persona_summary="To be awesome.", therapeutic_setting="Online"
    ).model_dump(exclude_unset=True)

    response = client.post("/me/profile", json=profile_data_create, headers=headers)
    assert response.status_code == 201, response.text
    created_profile = response.json()
    assert created_profile["name"] == "Test User Alpha"
    assert created_profile["future_me_persona_summary"] == "To be awesome."
    assert created_profile["therapeutic_setting"] == "Online"
    assert "user_id" in created_profile
    profile_user_id = created_profile["user_id"]

    # 3. Get profile - should now exist
    response = client.get("/me/profile", headers=headers)
    assert response.status_code == 200
    read_profile = response.json()
    assert read_profile["name"] == "Test User Alpha"
    assert read_profile["user_id"] == profile_user_id

    # 4. Try to create profile again - should be 409 Conflict
    response = client.post("/me/profile", json=profile_data_create, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Profile already exists for this user."

    # 5. Update profile
    profile_data_update = UserProfileUpdate(
        name="Test User Alpha Updated",
        future_me_persona_summary="To be even more awesome!",
        gender_identity_pronouns="they/them",  # New field
    ).model_dump(exclude_unset=True)

    response = client.put("/me/profile", json=profile_data_update, headers=headers)
    assert response.status_code == 200, response.text
    updated_profile = response.json()
    assert updated_profile["name"] == "Test User Alpha Updated"
    assert updated_profile["future_me_persona_summary"] == "To be even more awesome!"
    assert updated_profile["gender_identity_pronouns"] == "they/them"
    assert updated_profile["therapeutic_setting"] == "Online"  # Field from create should persist if not updated
    assert updated_profile["user_id"] == profile_user_id

    # 6. Get profile again - should reflect updates
    response = client.get("/me/profile", headers=headers)
    assert response.status_code == 200
    final_profile = response.json()
    assert final_profile["name"] == "Test User Alpha Updated"
    assert final_profile["gender_identity_pronouns"] == "they/them"


@pytest.mark.asyncio
async def test_get_profile_unauthenticated(client: TestClient):
    response = client.get("/me/profile")
    assert response.status_code == 401  # Or 403, depending on fastapi-users default


@pytest.mark.asyncio
async def test_post_profile_unauthenticated(client: TestClient):
    profile_data = {"name": "No Auth User"}
    response = client.post("/me/profile", json=profile_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_profile_unauthenticated(client: TestClient):
    profile_data = {"name": "No Auth User Update"}
    response = client.put("/me/profile", json=profile_data)
    assert response.status_code == 401
