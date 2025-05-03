import inspect
import fastapi

# Print the fastapi module contents
print("fastapi module contents:", dir(fastapi))

# Check if there's a TestClient
try:
    from fastapi.testclient import TestClient
    print("\nTestClient class:")
    print(inspect.signature(TestClient.__init__))
    print("\nTestClient docstring:")
    print(TestClient.__doc__)
except ImportError:
    print("\nTestClient class does not exist")