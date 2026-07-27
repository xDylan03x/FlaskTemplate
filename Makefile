SHELL := /bin/sh
.SHELLFLAGS := -ec
.DEFAULT_GOAL := help

PYTHON ?= python3
NPM ?= npm
NPX ?= npx

PIP := $(PYTHON) -m pip
FLASK := $(PYTHON) -m flask --app app

CSS_INPUT := ./app/core/static/css/styles.css
CSS_OUTPUT := ./app/core/static/css/output.css

MAGENTA := \033[0;35m
YELLOW := \033[0;33m
GREEN := \033[1;32m
NC := \033[0m

.PHONY: \
	help \
	tailwind \
	vite \
	assets \
	db \
	db_check \
	db_upgrade \
	doctor \
	requirements \
	install_python \
	install_node \
	git \
	setup_project \
	update \
	build_for_release \
	setup_for_server


help: # Show this help message
	@awk 'BEGIN {FS = ":.*# "} /^[A-Za-z0-9_.-]+:.*# / {printf "$(GREEN)%-24s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)


tailwind: # Compile Tailwind CSS for production
	$(NPX) --no-install @tailwindcss/cli \
		-i $(CSS_INPUT) \
		-o $(CSS_OUTPUT) \
		--minify


vite: # Build the Vite project
	$(NPM) run build


assets: tailwind vite # Build all production frontend assets


db: db_check # Check whether database migrations are current


db_check: # Check for uncommitted database model migrations
	$(FLASK) db check


db_upgrade: # Apply committed database migrations
	$(FLASK) db upgrade


doctor: # Check database and configured external services
	$(FLASK) doctor


requirements: # Freeze the active Python environment (developer maintenance only)
	$(PIP) freeze > requirements.txt


install_python: # Install locked Python dependencies
	$(PIP) install -r requirements.txt


install_node: # Install locked Node dependencies, including build tools
	$(NPM) ci --include=dev


git: # Merge the latest project-template changes
	git fetch template
	git merge template/master -m "Merge template/master into current branch"


setup_project: # Install dependencies and create a local environment file
	@printf "$(YELLOW)> Setting Up Project$(NC)\n"

	@printf "$(YELLOW)> [1/3] Installing Python Dependencies$(NC)\n"
	$(MAKE) install_python

	@printf "$(YELLOW)> [2/3] Installing Node Dependencies$(NC)\n"
	$(MAKE) install_node

	@printf "$(YELLOW)> [3/3] Creating Environment File$(NC)\n"
	@if [ -f .env ]; then \
		printf "$(YELLOW)> .env already exists; leaving it unchanged$(NC)\n"; \
	else \
		cp .env.example .env; \
		printf "$(YELLOW)> Created .env from .env.example$(NC)\n"; \
	fi

	@printf "$(MAGENTA)> Project Setup Complete$(NC)\n"
	@printf "$(YELLOW)> Review .env before running the application$(NC)\n"


update: # Merge template changes and update the local project
	@printf "$(MAGENTA)> Updating from Project Template$(NC)\n"

	@printf "$(MAGENTA)> [1/7] Updating Git Repository$(NC)\n"
	$(MAKE) git

	@printf "$(MAGENTA)> [2/7] Installing Node Dependencies$(NC)\n"
	$(MAKE) install_node

	@printf "$(MAGENTA)> [3/7] Installing Python Dependencies$(NC)\n"
	$(MAKE) install_python

	@printf "$(MAGENTA)> [4/7] Building Tailwind CSS$(NC)\n"
	$(MAKE) tailwind

	@printf "$(MAGENTA)> [5/7] Building Vite Assets$(NC)\n"
	$(MAKE) vite

	@printf "$(MAGENTA)> [6/7] Applying Database Migrations$(NC)\n"
	$(MAKE) db_upgrade

	@printf "$(MAGENTA)> [7/7] Updating Users and Application Settings$(NC)\n"
	$(FLASK) update_users
	$(FLASK) update_app

	@printf "$(MAGENTA)> Project Template Update Complete$(NC)\n"
	@printf "$(YELLOW)> Review the changes and push them when ready$(NC)\n"


build_for_release: # Build assets and validate migrations before release
	@printf "$(MAGENTA)> Building Project for Release$(NC)\n"

	@printf "$(MAGENTA)> [1/5] Installing Locked Node Dependencies$(NC)\n"
	$(MAKE) install_node

	@printf "$(MAGENTA)> [2/5] Building Tailwind CSS$(NC)\n"
	$(MAKE) tailwind

	@printf "$(MAGENTA)> [3/5] Building Vite Assets$(NC)\n"
	$(MAKE) vite

	@printf "$(MAGENTA)> [4/5] Checking Database Migrations$(NC)\n"
	$(MAKE) db_check

	@printf "$(MAGENTA)> [5/5] Freezing Python Requirements$(NC)\n"
	$(MAKE) requirements

	@printf "$(MAGENTA)> Release Build Complete$(NC)\n"


setup_for_server: # Setup the project for deployment on a server
	@printf "$(MAGENTA)> Building Project on Server$(NC)\n"

	@printf "$(MAGENTA)> [1/8] Installing Python Dependencies$(NC)\n"
	$(MAKE) install_python

	@printf "$(MAGENTA)> [2/8] Installing Locked Node Dependencies$(NC)\n"
	$(MAKE) install_node

	@printf "$(MAGENTA)> [3/8] Building Tailwind CSS$(NC)\n"
	$(MAKE) tailwind

	@printf "$(MAGENTA)> [4/8] Building Vite Assets$(NC)\n"
	$(MAKE) vite

	@printf "$(MAGENTA)> [5/8] Creating Environment File$(NC)\n"
	@if [ -f .env ]; then \
    		printf "$(YELLOW)> .env already exists; leaving it unchanged$(NC)\n"; \
    	else \
    		cp .env.production.example .env; \
    		printf "$(YELLOW)> Created .env from .env.production.example$(NC)\n"; \
    	fi

	@printf "$(MAGENTA)> [6/8] Applying Database Migrations$(NC)\n"
	$(MAKE) db_upgrade

	@printf "$(MAGENTA)> [7/8] Creating Initial Admin User$(NC)\n"
	$(FLASK) create_admin

	@printf "$(MAGENTA)> [8/8] Updating Users and Application Settings$(NC)\n"
	$(FLASK) update_users
	$(FLASK) update_app

	@printf "$(MAGENTA)> Server Build Complete$(NC)\n"
	@printf "$(YELLOW)> Run 'make doctor' for post-deployment health checks$(NC)\n"