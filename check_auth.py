import inspect
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend

# Print the JWTStrategy class
print("JWTStrategy class:")
print(inspect.signature(JWTStrategy.__init__))

# Print the AuthenticationBackend class
print("\nAuthenticationBackend class:")
print(inspect.signature(AuthenticationBackend.__init__))
print("\nAuthenticationBackend docstring:")
print(AuthenticationBackend.__doc__)

# Check if there's a jwt module
try:
    from fastapi_users.authentication import jwt
    print("\nfastapi_users.authentication.jwt module exists")
    print("jwt module contents:", dir(jwt))
except ImportError:
    print("\nfastapi_users.authentication.jwt module does not exist")