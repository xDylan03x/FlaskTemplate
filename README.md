# Flask Template

This is an opinionated template for a Flask web application. It includes the necessary structure and functionality to get started with a Flask project.  
The project assumes the app will be used in a single-tenant environment.

## Features

- Authentication handled with Flask-Login and extras (2FA and password-less login) with email/text (with Twilio)
- User management with email-based accounts
- Permission-based access control with easy extendability
- User groups for easy group-based features
- Support for email, text, and in-app notifications
- Database integration using SQLAlchemy (PostgreSQL by default)
- Frontend styled with TailwindCSS 4 and DaisyUI (default themes included)
- Auditing and logging of user actions

## Structure

The application is structured into 'modules' (flask blueprints) for better organization.
Each module contains files for its own routes, forms, helper functions, decorators, permissions, settings, asynchronous jobs (to be used with
something like Celery), and templates (except for the API module).  
The user permissions and settings system is built with extendability in mind. It allows developers to add new features with minimal effort.

- The core module contains the application's base template (including assets like CSS, JS, and images) and account/system management functionality.
- The auth module handles user authentication and management.
- The api module provides API endpoints (like notifications).
- Other modules can be built out as needed.

## Getting Started
Once you clone the directory and set up your environment (see below), follow these steps to get started:
1. Run `make setup_project` to install Python and NPM dependencies.
2. Edit the newly created `.env` file to set your environment variables.
3. Once your local PostgreSQL database is set up and running, run `flask db init` to set up the migration folder. Then run `flask db migrate -m "Initial setup"` and `flask db upgrade`.
4. From the project's root directory, run `export FLASK_APP=app`.
5. Run `flask create_admin` to set up the admin user.
6. Use `flask run --port 8080 --debug` to start the development server.
7. Use `make vite` and `make tailwind` to build frontend resources.
8. Run `flask doctor` to check the status of the database and external providers.

_Note: You can use `make build` when you're ready to deploy your application. Use `make help` for a further list of commands._  
_When ready to update the project from the template, run `make update`._

### Cloning The Repository
To make things easier in the future, you can set up your application repository
in a way that allows you to merge new updates from this template repository.
To do this, follow these steps:
1. Navigate to wherever you want to store this project and run `git clone git@github.com:xDylan03x/FlaskTemplate.git NEW_APP_NAME`
2. Navigate into the new directory and run `git remote rename origin template` to set the template repository as such.
3. Visit the GitHub website and make a new repository with the same name you used above. Then copy the SSH URL.
4. Run `git remote add origin SSH_URL` to set the new repository as the origin.
5. Lastly, run `git push -u origin master` to push the initial commit to your new repository.
From here, you can continue with step 1 of the "Getting Started" section above.

Whenever you want to pull in new updates from this template repository, run the following commands:
1. `git fetch template `
2. `git merge template/master`

### Setting up Your Environment
To finish setting up your environment, create and enable your virtual environment (venv, conda, etc.) of choice.  
Make sure to create a database for your application and set the environment variables accordingly.
For quicker setup, use a password-less database instance named xx_dev (where 'xx' is equal to the lowercase site abbreviation set in your environment variables).