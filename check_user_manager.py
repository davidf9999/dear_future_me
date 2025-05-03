import inspect
from fastapi_users.manager import BaseUserManager
from fastapi_users.authentication import JWTStrategy

# Print the BaseUserManager class
print("BaseUserManager class:")
print(inspect.signature(BaseUserManager.__init__))
print("\nBaseUserManager docstring:")
print(BaseUserManager.__doc__)

# Print the JWTStrategy class
print("\nJWTStrategy class:")
print(inspect.signature(JWTStrategy.__init__))
print("\nJWTStrategy docstring:")
print(JWTStrategy.__doc__)