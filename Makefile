.SHELLFLAGS := -ec

CSS_INPUT = ./app/core/static/css/styles.css
CSS_OUTPUT = ./app/core/static/css/output.css

MAGENTA = \033[0;35m
YELLOW = \033[0;33m
NC = \033[0m

default: help
.PHONY: help tailwind db requirements build setup_project

help: # Show this help message
	@grep -E '^[a-zA-Z0-9 -]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done

setup_project: # Set up the project by installing dependencies and configuring environment variables
	@echo "$(YELLOW)> Setting Up Project$(NC)"
	@echo "$(YELLOW)> Installing Python Dependencies$(NC)"
	pip install -r requirements.txt
	@echo "$(YELLOW)> Installing NPM Dependencies$(NC)"
	npm install
	@echo "$(YELLOW)> Creating .env File$(NC)"
	cp .env.example .env
	@echo "$(YELLOW)> Project Setup Complete - Modify .env file before continuing$(NC)"

tailwind: # Compile Tailwind CSS for production
	npx @tailwindcss/cli -i $(CSS_INPUT) -o $(CSS_OUTPUT) --minify

db: # Create the database status
	flask db check

requirements: # Update the requirements.txt file with the current environment's dependencies
	pip freeze > requirements.txt

build: # Build the project for production - combines other individual steps
	@echo "$(MAGENTA)> Building Project$(NC)"
	@echo "$(MAGENTA)> [1/3] Running Tailwind CSS Build$(NC)"
	@echo ""
	$(MAKE) tailwind
	@echo ""
	@echo "$(MAGENTA)> [2/3] Checking Database Migrations$(NC)"
	@echo ""
	$(MAKE) db
	@echo ""
	@echo "$(MAGENTA)> [3/3] Freezing Python Dependencies$(NC)"
	@echo ""
	$(MAKE) requirements
	@echo ""
	@echo "$(MAGENTA)> Build Complete$(NC)"
