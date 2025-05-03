import inspect
from fastapi_users.authentication import transport

# Print the transport module contents
print("transport module contents:", dir(transport))

# Check if there's a cookie transport
try:
    from fastapi_users.authentication.transport import CookieTransport
    print("\nCookieTransport class:")
    print(inspect.signature(CookieTransport.__init__))
except ImportError:
    print("\nCookieTransport class does not exist")

# Check if there's a bearer transport
try:
    from fastapi_users.authentication.transport import BearerTransport
    print("\nBearerTransport class:")
    print(inspect.signature(BearerTransport.__init__))
except ImportError:
    print("\nBearerTransport class does not exist")