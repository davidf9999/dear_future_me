# /home/dfront/code/dear_future_me/Makefile

# Default shell for make to use
SHELL := /bin/bash

# Variables
COMPOSE_SCRIPT := ./compose.sh # Assuming compose.sh is in the project root

.PHONY: help \
		dev prod dev-up prod-up dev-down prod-down dev-stop prod-stop \
		dev-build-backend dev-build-frontend prod-build-backend prod-build-frontend \
		dev-build-backend-no-cache dev-build-frontend-no-cache prod-build-backend-no-cache prod-build-frontend-no-cache \
		dev-build prod-build dev-build-no-cache prod-build-no-cache \
		up down stop logs logs-dev logs-prod ps ps-dev ps-prod

help:
	@echo "Dear Future Me Project Makefile"
	@echo "---------------------------------"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help                          Show this help message."
	@echo ""
	@echo "  dev                           Start the development environment (backend & frontend)."
	@echo "  prod                          Start the production environment (backend & frontend)."
	@echo ""
	@echo "  dev-up                        Alias for 'dev'."
	@echo "  prod-up                       Alias for 'prod'."
	@echo ""
	@echo "  dev-stop                      Stop (but do not remove) development environment containers."
	@echo "  prod-stop                     Stop (but do not remove) production environment containers."
	@echo "  dev-down                      Stop and remove development environment containers."
	@echo "  prod-down                     Stop and remove production environment containers."
	@echo ""
	@echo "  dev-build-backend             Build backend image for the dev profile (uses cache)."
	@echo "  dev-build-frontend            Build frontend image for the dev profile (uses cache)."
	@echo "  dev-build-backend-no-cache    Build backend image for the dev profile (no cache)."
	@echo "  dev-build-frontend-no-cache   Build frontend image for the dev profile (no cache)."
	@echo ""
	@echo "  prod-build-backend            Build backend image for the prod profile (uses cache)."
	@echo "  prod-build-frontend           Build frontend image for the prod profile (uses cache)."
	@echo "  prod-build-backend-no-cache   Build backend image for the prod profile (no cache)."
	@echo "  prod-build-frontend-no-cache  Build frontend image for the prod profile (no cache)."
	@echo ""
	@echo "  dev-build                     Build all images for the development profile (uses cache)."
	@echo "  prod-build                    Build all images for the production profile (uses cache)."
	@echo "  dev-build-no-cache            Build all images for the development profile (no cache)."
	@echo "  prod-build-no-cache           Build all images for the production profile (no cache)."
	@echo ""
	@echo "  up                            Start both dev and prod environments simultaneously (branch checks in compose.sh will be bypassed for this 'up' command)."
	@echo "  stop                          Stop (but do not remove) all (dev & prod) environment containers."
	@echo "  down                          Stop and remove all (dev & prod) environment containers."
	@echo ""
	@echo "  logs                          Follow logs for all active services (dev & prod)."
	@echo "  logs-dev                      Follow logs for development services."
	@echo "  logs-prod                     Follow logs for production services."
	@echo ""
	@echo "  ps                            List running containers for this project (dev & prod)."
	@echo "  ps-dev                        List running containers for dev profile."
	@echo "  ps-prod                       List running containers for prod profile."

# Granular build targets for dev profile
dev-build-backend:
	$(COMPOSE_SCRIPT) --profile dev build backend-dev
dev-build-frontend:
	$(COMPOSE_SCRIPT) --profile dev build frontend-dev
dev-build-backend-no-cache:
	$(COMPOSE_SCRIPT) --profile dev build --no-cache backend-dev
dev-build-frontend-no-cache:
	$(COMPOSE_SCRIPT) --profile dev build --no-cache frontend-dev

# Granular build targets for prod profile
prod-build-backend:
	$(COMPOSE_SCRIPT) --profile prod build backend-prod
prod-build-frontend:
	$(COMPOSE_SCRIPT) --profile prod build frontend-prod
prod-build-backend-no-cache:
	$(COMPOSE_SCRIPT) --profile prod build --no-cache backend-prod
prod-build-frontend-no-cache:
	$(COMPOSE_SCRIPT) --profile prod build --no-cache frontend-prod

# Build all services within a specific profile
dev-build:
	$(COMPOSE_SCRIPT) --profile dev build
prod-build:
	$(COMPOSE_SCRIPT) --profile prod build

dev-build-no-cache:
	$(COMPOSE_SCRIPT) --profile dev build --no-cache
prod-build-no-cache:
	$(COMPOSE_SCRIPT) --profile prod build --no-cache

# Environment management targets
dev: dev-up
dev-up:
	$(COMPOSE_SCRIPT) --profile dev up -d # -d for detached mode, remove if you want logs in foreground

prod: prod-up
prod-up:
	$(COMPOSE_SCRIPT) --profile prod up -d # -d for detached mode

dev-stop:
	$(COMPOSE_SCRIPT) --profile dev stop
prod-stop:
	$(COMPOSE_SCRIPT) --profile prod stop

dev-down:
	$(COMPOSE_SCRIPT) --profile dev down
prod-down:
	$(COMPOSE_SCRIPT) --profile prod down

# Note: The 'up', 'stop', and 'down' targets below will invoke compose.sh with both profiles.
# As per compose.sh logic, branch checks will be skipped for these specific commands.
# This might be acceptable if these operations for both simultaneously are explicit, advanced operations.
up:
	$(COMPOSE_SCRIPT) --profile dev --profile prod up -d

stop:
	$(COMPOSE_SCRIPT) --profile dev --profile prod stop

down:
	$(COMPOSE_SCRIPT) --profile dev --profile prod down

# Utility targets
logs:
	$(COMPOSE_SCRIPT) --profile dev --profile prod logs -f
logs-dev:
	$(COMPOSE_SCRIPT) --profile dev logs -f
logs-prod:
	$(COMPOSE_SCRIPT) --profile prod logs -f

ps:
	$(COMPOSE_SCRIPT) --profile dev --profile prod ps
ps-dev:
	$(COMPOSE_SCRIPT) --profile dev ps
ps-prod:
	$(COMPOSE_SCRIPT) --profile prod ps

