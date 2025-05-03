from app.auth.router import auth_backend, fastapi_users

# Print the auth_backend name
print("Auth backend name:", auth_backend.name)

# Print the auth_router routes
auth_router = fastapi_users.get_auth_router(auth_backend)
print("\nAuth router routes:")
for route in auth_router.routes:
    print(f"  {route.methods} {route.path}")

# Print the register_router routes
register_router = fastapi_users.get_register_router()
print("\nRegister router routes:")
for route in register_router.routes:
    print(f"  {route.methods} {route.path}")