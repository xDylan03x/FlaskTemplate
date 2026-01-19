# Flask Template

This is an opinionated template for a Flask web application.
It includes the necessary structure and functionality to get started with a Flask project.

## Features

- Authentication handled with Flask-Login and extras (2FA and password-less login) with email/text (with Twilio)
- User management with roles and email-based accounts
- Email and text notifications with Twilio
- Database integration using SQLAlchemy (PostgreSQL by default)
- Frontend styled with TailwindCSS 4 and DaisyUI (default themes included)

## Structure

The application in structured into 'modules' (flask blueprints) for better organization.
Each module contains files for its own routes, forms, helper functions, decorators, asynchronous jobs (to be used with
something like Celery), and templates (except for the API module).

- The core module contains the applications base template (including assets like CSS JS, and images) and account/system management functionality.
- The auth module handles user authentication and management.
- The api module provides API endpoints.
- Other modules can be built out as needed.

## Getting Started
Once you clone the directory (and set up your venv), follow these steps to get started:
1. Run `make setup_project` to install Python and NPM dependencies.
2. Edit the newly created `.env` file to set your environment variables.
3. Once your local PostgreSQL database is set up and running, run `flask db init` to set up the migration folder. Then run `flask db migrate -m "Initial setup"` and `flask db upgrade`.
4. Run `flask create_admin` to set up the admin user.
5. Use `flask run --port 8080 --debug` to start the development server.