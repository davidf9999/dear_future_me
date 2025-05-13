# Makefile for the Dear Future Me project

# Default shell for make to use
SHELL := /bin/bash

# Variables
COMPOSE_SCRIPT := ./compose.sh # Assuming compose.sh is in the project root

.PHONY: help build build-no-cache dev prod dev-up prod-up dev-down prod-down dev-build prod-build up down logs ps

help:
	@echo "Dear Future Me Project Makefile"
	@echo "---------------------------------"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help                 Show this help message."
	@echo "  build                Build Docker images for both dev and prod profiles (uses cache)."
	@echo "  build-no-cache       Build Docker images for both dev and prod profiles (no cache)."
	@echo ""
	@echo "  dev                  Start the development environment (backend & frontend)."
	@echo "  prod                 Start the production environment (backend & frontend)."
	@echo ""
	@echo "  dev-up               Alias for 'dev'."
	@echo "  prod-up              Alias for 'prod'."
	@echo ""
	@echo "  dev-down             Stop and remove development environment containers."
	@echo "  prod-down            Stop and remove production environment containers."
	@echo ""
	@echo "  dev-build            Build images for the development profile (uses cache)."
	@echo "  prod-build           Build images for the production profile (uses cache)."
	@echo "  dev-build-no-cache   Build images for the development profile (no cache)."
	@echo "  prod-build-no-cache  Build images for the production profile (no cache)."
	@echo ""
	@echo "  up                   Start both dev and prod environments simultaneously."
	@echo "  down                 Stop and remove all (dev & prod) environment containers."
	@echo ""
	@echo "  logs                 Follow logs for all active services (dev & prod)."
	@echo "  logs-dev             Follow logs for development services."
	@echo "  logs-prod            Follow logs for production services."
	@echo ""
	@echo "  ps                   List running containers for this project (dev & prod)."
	@echo "  ps-dev               List running containers for dev profile."
	@echo "  ps-prod              List running containers for prod profile."

# Build targets
build: dev-build prod-build

build-no-cache: dev-build-no-cache prod-build-no-cache

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

dev-down:
	$(COMPOSE_SCRIPT) --profile dev down
prod-down:
	$(COMPOSE_SCRIPT) --profile prod down

up:
	$(COMPOSE_SCRIPT) --profile dev --profile prod up -d

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