.SHELLFLAGS := -ec

CSS_INPUT = ./app/core/static/css/styles.css
CSS_OUTPUT = ./app/core/static/css/output.css

MAGENTA = \033[0;35m
YELLOW = \033[0;33m
NC = \033[0m

.PHONY: tailwind db requirements build setup_project

setup_project:
	@echo "$(YELLOW)> Setting Up Project$(NC)"
	@echo "$(YELLOW)> Installing Python Dependencies$(NC)"
	pip install -r requirements.txt
	@echo "$(YELLOW)> Installing NPM Dependencies$(NC)"
	npm install
	@echo "$(YELLOW)> Creating .env File$(NC)"
	cp .env.example .env
	@echo "$(YELLOW)> Project Setup Complete - Modify .env file before continuing$(NC)"

tailwind:
	npx @tailwindcss/cli -i $(CSS_INPUT) -o $(CSS_OUTPUT) --minify

db:
	flask db check

requirements:
	pip freeze > requirements.txt

build:
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
