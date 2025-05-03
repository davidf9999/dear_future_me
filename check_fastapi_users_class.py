import inspect
from fastapi_users import FastAPIUsers

# Print the signature of the FastAPIUsers constructor
print("FastAPIUsers constructor signature:")
print(inspect.signature(FastAPIUsers.__init__))

# Print the docstring of the FastAPIUsers class
print("\nFastAPIUsers class docstring:")
print(FastAPIUsers.__doc__)