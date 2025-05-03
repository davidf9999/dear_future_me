from app.auth.router import auth_backend, fastapi_users, auth_router, register_router

# Print the auth_backend name
print("Auth backend name:", auth_backend.name)

# Print the auth_router routes
print("\nAuth router routes:")
for route in auth_router.routes:
    print(f"  {route.methods} {route.path}")

# Print the register_router routes
print("\nRegister router routes:")
for route in register_router.routes:
    print(f"  {route.methods} {route.path}")