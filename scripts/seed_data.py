# scripts/seed_data.py
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Determine the project root directory and add it to sys.path
# This allows the script to be run from any location and still find the 'app' module.
# This should be done before attempting to import from 'app'.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth.models import SafetyPlanTable, UserProfileTable, UserTable  # noqa: E402
from app.auth.security import get_password_hash  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.db.session import (  # noqa: E402
    get_async_session_context,
    get_engine,
)


async def seed_users(session: AsyncSession, users_data: list):
    """Seeds user data into the UserTable."""
    print("Seeding users...")
    for user_dict in users_data:
        # Check if user already exists
        existing_user_stmt = select(UserTable).where(UserTable.email == user_dict["email"])
        existing_user_result = await session.execute(existing_user_stmt)
        if existing_user_result.scalars().first():
            print(f"User {user_dict['email']} already exists, skipping.")
            continue

        hashed_password = get_password_hash(user_dict.pop("password"))
        user = UserTable(**user_dict, hashed_password=hashed_password)
        session.add(user)
        print(f"  Added user: {user.email}")
    await session.commit()
    print("User seeding complete.")


async def seed_user_profiles(session: AsyncSession, profiles_data: list):
    """Seeds user profile data into the UserProfileTable."""
    print("Seeding user profiles...")
    for profile_dict in profiles_data:
        user_email = profile_dict.pop("user_email") # Assuming JSONL has user_email to link

        # Find the user_id for the given email
        user_stmt = select(UserTable.id).where(UserTable.email == user_email)
        user_result = await session.execute(user_stmt)
        user_id = user_result.scalars().first()

        if not user_id:
            print(f"  Warning: User with email '{user_email}' not found for profile. Skipping profile: {profile_dict.get('name', 'N/A')}")
            continue

        # Check if profile for this user_id already exists
        existing_profile_stmt = select(UserProfileTable).where(UserProfileTable.user_id == user_id)
        existing_profile_result = await session.execute(existing_profile_stmt)
        if existing_profile_result.scalars().first():
            print(f"  Profile for user_id {user_id} (email: {user_email}) already exists. Skipping.")
            continue
        
        profile = UserProfileTable(user_id=user_id, **profile_dict)
        session.add(profile)
        print(f"  Added profile for user_id: {user_id} (email: {user_email})")
    await session.commit()
    print("User profile seeding complete.")


async def seed_safety_plans(session: AsyncSession, plans_data: list):
    """Seeds safety plan data into the SafetyPlanTable."""
    print("Seeding safety plans...")
    for plan_dict in plans_data:
        user_email = plan_dict.pop("user_email") # Assuming JSONL has user_email to link

        # Find the user_id for the given email
        user_stmt = select(UserTable.id).where(UserTable.email == user_email)
        user_result = await session.execute(user_stmt)
        user_id = user_result.scalars().first()

        if not user_id:
            print(f"  Warning: User with email '{user_email}' not found for safety plan. Skipping plan for: {user_email}")
            continue
        
        # Check if plan for this user_id already exists (simple check, might need more sophisticated logic)
        existing_plan_stmt = select(SafetyPlanTable).where(SafetyPlanTable.user_id == user_id)
        existing_plan_result = await session.execute(existing_plan_stmt)
        if existing_plan_result.scalars().first(): # This assumes one plan per user for simplicity
            print(f"  Safety plan for user_id {user_id} (email: {user_email}) already exists. Skipping.")
            continue

        plan = SafetyPlanTable(user_id=user_id, **plan_dict)
        session.add(plan)
        print(f"  Added safety plan for user_id: {user_id} (email: {user_email})")
    await session.commit()
    print("Safety plan seeding complete.")


async def main():
    """Main function to load data from JSONL files and seed the database."""
    settings = get_settings()

    # Determine which .env file to load based on an argument or default
    # For simplicity, let's assume a 'dev' or 'prod' argument.
    # If no arg, default to 'dev'.
    env_type = sys.argv[1] if len(sys.argv) > 1 else "dev"
    env_file = PROJECT_ROOT / f".env.{env_type}"

    if env_file.exists():
        print(f"Loading environment variables from: {env_file}")
        load_dotenv(dotenv_path=env_file, override=True)
    else:
        print(f"Warning: Environment file {env_file} not found. Using default/existing environment.")

    # Re-fetch settings after .env might have been loaded
    # This is important if DATABASE_URL is in the .env file
    settings = get_settings()
    print(f"Using DATABASE_URL: {settings.DATABASE_URL} for seeding.")


    # Path to the directory containing JSONL files
    # Assumes JSONL files are in PROJECT_ROOT/RDB_demo_data/jsonl/
    jsonl_dir = PROJECT_ROOT / "RDB_demo_data" / "jsonl"

    users_jsonl_path = jsonl_dir / "users.jsonl"
    profiles_jsonl_path = jsonl_dir / "user_profiles.jsonl"
    safety_plans_jsonl_path = jsonl_dir / "safety_plans.jsonl"

    # Load data from JSONL files
    users_data = []
    if users_jsonl_path.exists():
        with open(users_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                users_data.append(json.loads(line))
    else:
        print(f"Warning: Users JSONL file not found at {users_jsonl_path}")

    profiles_data = []
    if profiles_jsonl_path.exists():
        with open(profiles_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                profiles_data.append(json.loads(line))
    else:
        print(f"Warning: User profiles JSONL file not found at {profiles_jsonl_path}")

    safety_plans_data = []
    if safety_plans_jsonl_path.exists():
        with open(safety_plans_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                safety_plans_data.append(json.loads(line))
    else:
        print(f"Warning: Safety plans JSONL file not found at {safety_plans_jsonl_path}")

    # Get an async session
    # The get_async_session_context should use the engine configured by get_settings()
    engine = get_engine() # Get the engine configured by settings
    
    # Optional: Create tables if they don't exist.
    # This is useful if running seed script against a fresh DB without migrations.
    # However, it's generally better to run Alembic migrations first.
    # from app.auth.models import Base # Already imported
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    # print("Ensured all tables are created (if they didn't exist).")


    async with get_async_session_context() as session: # Use the context manager
        if users_data:
            await seed_users(session, users_data)
        if profiles_data:
            await seed_user_profiles(session, profiles_data)
        if safety_plans_data:
            await seed_safety_plans(session, safety_plans_data)
    
    await engine.dispose() # Dispose the engine when done
    print("Seeding process finished.")

if __name__ == "__main__":
    print(f"Running seed_data.py with arguments: {sys.argv}")
    if len(sys.argv) > 1 and sys.argv[1] in ["dev", "prod"]:
        asyncio.run(main())
    else:
        print("Usage: python scripts/seed_data.py <dev|prod>")
        print("Example: python scripts/seed_data.py dev")
