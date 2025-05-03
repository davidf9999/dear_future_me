import inspect
from fastapi_users.db import SQLAlchemyUserDatabase

# Print the SQLAlchemyUserDatabase class
print("SQLAlchemyUserDatabase class:")
print(inspect.signature(SQLAlchemyUserDatabase.__init__))
print("\nSQLAlchemyUserDatabase docstring:")
print(SQLAlchemyUserDatabase.__doc__)