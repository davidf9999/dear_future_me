import inspect
from httpx import AsyncClient

# Print the AsyncClient class
print("AsyncClient class:")
print(inspect.signature(AsyncClient.__init__))
print("\nAsyncClient docstring:")
print(AsyncClient.__doc__)