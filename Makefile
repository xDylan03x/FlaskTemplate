.SHELLFLAGS := -ec

CSS_INPUT = ./app/core/static/css/styles.css
CSS_OUTPUT = ./app/core/static/css/output.css

MAGENTA = \033[0;35m
YELLOW = \033[0;33m
NC = \033[0m

default: help
.PHONY: help tailwind vite db requirements git setup_project update build

help: # Show this help message
	@grep -E '^[a-zA-Z0-9 -]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done

tailwind: # Compile Tailwind CSS for production
	npx @tailwindcss/cli -i $(CSS_INPUT) -o $(CSS_OUTPUT) --minify

vite: # Build the Vite project
	npm run build

db: # Create the database status
	flask db check

requirements: # Update the requirements.txt file with the current environment's dependencies
	pip freeze > requirements.txt

git: # Update the project with the current template files from the Git repository
	git fetch template
	git merge template/master

setup_project: # Set up the project by installing dependencies and configuring environment variables
	@echo "$(YELLOW)> Setting Up Project$(NC)"
	@echo "$(YELLOW)> Installing Python Dependencies$(NC)"
	pip install -r requirements.txt
	@echo "$(YELLOW)> Installing NPM Dependencies$(NC)"
	npm install
	@echo "$(YELLOW)> Creating .env File$(NC)"
	cp .env.example .env
	@echo "$(YELLOW)> Project Setup Complete - Modify .env file before continuing$(NC)"

update: # Update the project with the current template files
	@echo "$(MAGENTA)> Updating from Project Template$(NC)"
	@echo "$(MAGENTA)> [1/7] Updating from GIT repository$(NC)"
	@echo ""
	$(MAKE) git
	@echo ""
	@echo "$(MAGENTA)> [2/7] Running Tailwind CSS Build$(NC)"
	@echo ""
	$(MAKE) tailwind
	@echo ""
	@echo "$(MAGENTA)> [3/7] Running Vite Build$(NC)"
	@echo ""
	$(MAKE) vite
	@echo ""
	@echo "$(MAGENTA)> [4/7] Updating Python Dependencies$(NC)"
	@echo ""
	pip install -r requirements.txt
	@echo ""
	@echo "$(MAGENTA)> [5/7] Upgrading Database$(NC)"
	@echo ""
	flask db migrate -m "Upgrade from template"
	flask db upgrade
	@echo ""
	@echo "$(MAGENTA)> [6/7] Updating Users$(NC)"
	@echo ""
	flask update_users
	@echo ""
	@echo "$(MAGENTA)> [7/7] Updating App$(NC)"
	@echo ""
	flask update_app
	@echo ""
	@echo "$(MAGENTA)> Project Template Update Complete$(NC)"
	@echo "$(YELLOW)> Note: You may need to run 'git push'$(NC)"

build: # Build the project for production - combines other individual steps
	@echo "$(MAGENTA)> Building Project$(NC)"
	@echo "$(MAGENTA)> [1/4] Running Tailwind CSS Build$(NC)"
	@echo ""
	$(MAKE) tailwind
	@echo ""
	@echo "$(MAGENTA)> [2/4] Running Vite Build$(NC)"
	@echo ""
	$(MAKE) vite
	@echo ""
	@echo "$(MAGENTA)> [3/4] Checking Database Migrations$(NC)"
	@echo ""
	$(MAKE) db
	@echo ""
	@echo "$(MAGENTA)> [4/4] Freezing Python Dependencies$(NC)"
	@echo ""
	$(MAKE) requirements
	@echo ""
	@echo "$(MAGENTA)> Build Complete$(NC)"
