import inspect
import fastapi_users
import fastapi_users.schemas
import fastapi_users.models

print("fastapi_users version:", fastapi_users.__version__)
print("\nfastapi_users.schemas dir:", dir(fastapi_users.schemas))
print("\nfastapi_users.models dir:", dir(fastapi_users.models))

if hasattr(fastapi_users.schemas, 'models'):
    print("\nfastapi_users.schemas.models dir:", dir(fastapi_users.schemas.models))

# Check if there's a UserDB class in any module
for module_name in dir(fastapi_users):
    module = getattr(fastapi_users, module_name)
    if hasattr(module, "UserDB"):
        print(f"\nFound UserDB in {module_name}")
        print(inspect.getmro(module.UserDB))