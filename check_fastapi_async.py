import inspect
import fastapi.testclient

# Print the fastapi.testclient module contents
print("fastapi.testclient module contents:", dir(fastapi.testclient))

# Check if there's an AsyncClient
try:
    from fastapi.testclient import AsyncClient
    print("\nAsyncClient class:")
    print(inspect.signature(AsyncClient.__init__))
    print("\nAsyncClient docstring:")
    print(AsyncClient.__doc__)
except ImportError:
    print("\nAsyncClient class does not exist in fastapi.testclient")