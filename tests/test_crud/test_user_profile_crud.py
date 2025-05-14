# /home/dfront/code/dear_future_me/tests/test_crud/test_user_profile_crud.py
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure UserTable is imported from its definitive location
from app.auth.models import UserTable
from app.crud.user_profile import (
    create_user_profile,
    get_user_profile,
    update_user_profile,
)
from app.db.models import UserProfileTable


@pytest.mark.asyncio
async def test_create_user_profile(async_session: AsyncSession):
    # Create a dummy user first with a unique email for this test run
    user_email = f"test_profile_create_{uuid.uuid4().hex[:8]}@example.com"
    dummy_user = UserTable(
        id=uuid.uuid4(),
        email=user_email,
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    async_session.add(dummy_user)
    # No need to commit here if async_session fixture handles transaction rollback per test
    # await async_session.commit()
    await async_session.flush()  # Use flush to make the user available in the session
    await async_session.refresh(dummy_user)

    profile_data = {
        "name": "Test User",
        "future_me_persona_summary": "Summary",
        "key_therapeutic_language": "Language",
        "core_values_summary": "Values",
        "safety_plan_summary": "Safety",
    }
    # create_user_profile commits internally, which is fine with the fixture's rollback
    user_profile = await create_user_profile(async_session, user_id=dummy_user.id, profile_data=profile_data)

    assert user_profile.id is not None
    assert user_profile.user_id == dummy_user.id
    assert user_profile.name == "Test User"
    assert user_profile.future_me_persona_summary == "Summary"
    assert user_profile.created_at is not None
    assert user_profile.updated_at is not None

    # Verify it exists in the DB within the same transaction
    fetched_profile = await get_user_profile(async_session, user_id=dummy_user.id)
    assert fetched_profile is not None
    assert fetched_profile.id == user_profile.id


@pytest.mark.asyncio
async def test_get_user_profile(async_session: AsyncSession):
    user_email = f"test_profile_get_{uuid.uuid4().hex[:8]}@example.com"
    dummy_user = UserTable(
        id=uuid.uuid4(),
        email=user_email,
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    async_session.add(dummy_user)
    await async_session.flush()  # Flush user
    await async_session.refresh(dummy_user)

    dummy_profile = UserProfileTable(user_id=dummy_user.id, name="Getter Test")
    async_session.add(dummy_profile)
    await async_session.flush()  # Flush profile
    await async_session.refresh(dummy_profile)

    fetched_profile = await get_user_profile(async_session, user_id=dummy_user.id)
    assert fetched_profile is not None
    assert fetched_profile.id == dummy_profile.id
    assert fetched_profile.name == "Getter Test"
    assert fetched_profile.user_id == dummy_user.id

    # Test getting a non-existent profile
    non_existent_profile = await get_user_profile(async_session, user_id=uuid.uuid4())
    assert non_existent_profile is None


@pytest.mark.asyncio
async def test_update_user_profile(async_session: AsyncSession):
    user_email = f"test_profile_update_{uuid.uuid4().hex[:8]}@example.com"
    dummy_user = UserTable(
        id=uuid.uuid4(),
        email=user_email,
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    async_session.add(dummy_user)
    await async_session.flush()  # Flush user
    await async_session.refresh(dummy_user)

    initial_profile_data = {
        "name": "Initial Name",
        "future_me_persona_summary": "Initial Summary",
    }
    # create_user_profile commits internally, which is fine with the fixture's rollback
    user_profile = await create_user_profile(async_session, user_id=dummy_user.id, profile_data=initial_profile_data)
    # Refresh to get the state after create_user_profile's commit
    await async_session.refresh(user_profile)

    update_data = {
        "name": "Updated Name",
        "key_therapeutic_language": "New Language",
    }
    # update_user_profile commits internally, which is fine with the fixture's rollback
    updated_profile = await update_user_profile(async_session, user_profile, profile_data=update_data)
    # Refresh to get the state after update_user_profile's commit
    await async_session.refresh(updated_profile)

    assert updated_profile.id == user_profile.id
    assert updated_profile.name == "Updated Name"
    assert updated_profile.key_therapeutic_language == "New Language"
    assert updated_profile.future_me_persona_summary == "Initial Summary"
    assert updated_profile.safety_plan_summary is None
    assert updated_profile.updated_at > user_profile.created_at

    fetched_profile = await get_user_profile(async_session, user_id=dummy_user.id)
    assert fetched_profile is not None
    assert fetched_profile.name == "Updated Name"
    assert fetched_profile.key_therapeutic_language == "New Language"
