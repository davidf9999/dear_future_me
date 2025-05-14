# app/db/models/__init__.py
# This ensures that all models are imported when app.db.models is imported,
# allowing SQLAlchemy's Base to discover them for table creation.

from .user_profile import (
    UserProfileTable,  # Assuming UserProfileTable is in user_profile.py
)

# Import other models here if you have more

# Add models to __all__ to explicitly re-export them
__all__ = ["UserProfileTable"]
