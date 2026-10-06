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

1. Clone the repository and create a Python virtual environment:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   make setup_project
   ```

   Python, Node.js/npm, Git, and a running PostgreSQL server are needed. The setup command installs the locked dependencies and creates `.env` from `.env.example` if it does not already exist. On Windows, activate the environment with `.venv\Scripts\Activate.ps1` and use a shell with `make`, or run the installation commands from the Makefile individually.

2. Complete the [environment and service setup](#setting-up-your-environment) below. Configure SendGrid and Twilio Verify email before creating the administrator: `create_admin` enables 2FA for that account by default.
3. When ready, apply the database migrations and initialize the application:

   ```sh
   flask --app app db upgrade
   flask --app app update_app
   flask --app app create_admin
   ```

   The application loads `.env` automatically. `update_app` initializes system settings, including self-service registration. `create_admin` creates the initial account from the `ADMIN_*` values and grants user-management permissions; it does not update an account that already exists. To synchronize defaults on existing users after adding registered settings or permissions, run `flask --app app update_users`.

4. Build the frontend assets:

   ```sh
   make tailwind
   make vite
   ```

5. Check configured services, then start the development server:

   ```sh
   flask --app app doctor
   flask --app app run --port 8080 --debug
   ```

   Open [http://localhost:8080](http://localhost:8080). Keep the chosen hostname consistent with your Google OAuth callback and storage CORS settings.

Run `make help` to see the available commands. `make update` also merges template changes and applies database migrations; review the Makefile before using it on an existing application.

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

Use `.env.example` for local development. For a new production installation, copy `.env.production.example` to `.env` and replace its placeholders. Keep `.env` out of source control; it is already ignored. The example files contain placeholder credentials and do not create any provider accounts or resources.

The database and secret key are the foundation. SendGrid provides account emails and email notifications; Twilio Verify provides 2FA codes, including email codes. Twilio Messaging provides ordinary text messages, and S3-compatible storage provides file uploads. Google login and Sentry are optional integrations, although the login page displays the Google button even when its credentials are empty. Leaving a service blank does not automatically hide or disable its related UI.

#### Application identity, administrator, and secret key

| Variable | What to enter |
|----------|---------------|
| `APP_NAME` | The display name used in the UI and messages. |
| `APP_ABBR` | A short application abbreviation, such as `FT`. It also determines the development database fallback name. |
| `SITE_THEME` | A configured DaisyUI theme, such as `light` or `dark`. |
| `ADMIN_NAME` | The initial administrator's name. |
| `ADMIN_EMAIL` | A real email address that can receive verification codes. |
| `ADMIN_PASSWORD` | A unique password for the initial administrator; replace `replace_me`. |
| `SECRET_KEY` | A random, persistent secret used to sign sessions and protect forms. |

Generate a secret locally and paste the result into `SECRET_KEY`:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Keep the same key across application workers and restarts. Production configuration refuses to start with an empty `SECRET_KEY`; development otherwise falls back to `dev_secret`.

#### PostgreSQL database

Create a PostgreSQL login role and a database owned by that role. With a local server running, execute these commands as a database administrator (add `-U postgres` if that is your administrator login):

```sh
createuser --pwprompt flask_template
createdb --owner=flask_template ft_dev
```

Set the connection URL using the password supplied to `createuser`:

```dotenv
DATABASE_URL="postgresql://flask_template:YOUR_URL_ENCODED_PASSWORD@localhost:5432/ft_dev"
```

URL-encode special characters in the username or password. For a hosted database, use its connection details and required TLS options, such as `?sslmode=require`. The database must exist before you apply migrations; migrations create the application's tables.

An empty `DATABASE_URL` in development uses `postgresql://localhost/<lowercase APP_ABBR>_dev` (`ft_dev` for `FT`). That fallback assumes your local PostgreSQL authentication and operating-system user are already configured. Production requires an explicit URL.

See PostgreSQL's [createuser](https://www.postgresql.org/docs/current/app-createuser.html) and [createdb](https://www.postgresql.org/docs/current/app-createdb.html) documentation for administrator connection options.

#### SendGrid: account emails and notifications

1. Create a [Twilio SendGrid account](https://signup.sendgrid.com/).
2. Verify the sender you will use for `FROM_EMAIL`. For a domain you control, set up domain authentication and add SendGrid's DNS records; for a development sender, complete Single Sender Verification. Use the resulting verified address in `FROM_EMAIL`.
3. Create an API key with **Mail Send** access. Add **Template Engine: Read** access so `flask --app app doctor` can validate the configured template. Save the key in `SENDGRID_API_KEY`.
4. Create a Dynamic Template, add a version, and make that version active. Copy its `d-...` template ID into `SENDGRID_EMAIL_TEMPLATE_ID`.

The application sends these dynamic fields: `subject`, `preheader`, and `body`. Set the template's subject to `{{subject}}`. A minimal HTML version can use:

```html
<!doctype html>
<html>
  <body>
    <div style="display:none">{{preheader}}</div>
    <div>{{{body}}}</div>
  </body>
</html>
```

The app converts line breaks in its message body to HTML, so the triple braces preserve that formatting. This template handles welcome emails, magic links, password reset links, and notifications. The separate Twilio Verify template below handles numeric 2FA codes.

See [SendGrid sender verification](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/verifying-your-account), [API keys](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys), and [Dynamic Templates](https://www.twilio.com/docs/sendgrid/ui/sending-email/how-to-send-an-email-with-dynamic-templates).

#### Twilio: verification codes and text messages

1. Create a [Twilio account](https://www.twilio.com/try-twilio). Copy the Account SID (`AC...`) and Auth Token from the account console into `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`.
2. Create a **Verify Service**, give it your app's display name, and configure six-digit verification codes to match the code-entry forms. Put the service SID (`VA...`) in `TWILIO_SERVICE_SID`. This is a Verify Service SID, not a Messaging Service SID.
3. To support email 2FA, create a second active SendGrid Dynamic Template containing `{{twilio_code}}` in its body. Create a Verify email integration using the verified sender, a SendGrid API key, and that template ID, then associate it with your Verify Service. This template ID is configured in Twilio, not in `SENDGRID_EMAIL_TEMPLATE_ID`.
4. For ordinary text messages, obtain an SMS-capable Twilio phone number and complete any messaging setup required by Twilio for its use. Store it in `FROM_PHONE_NUMBER` in E.164 format, such as `+12025550123`. Replace the example file's placeholder number.
5. Configure the Verify channels and destination permissions needed for SMS and voice verification if you plan to offer those options.

The application uses Verify for email, SMS, voice, and authenticator-code verification. It uses Twilio Messaging separately for magic links, profile phone verification links, and text notifications. A Verify Service alone does not supply the number used by those ordinary texts.

Follow the official [Verify quickstarts](https://www.twilio.com/docs/verify/quickstarts) and [Verify email integration guide](https://www.twilio.com/docs/verify/email), including its SendGrid key permissions. The initial administrator uses email 2FA, so test that integration before relying on the administrator login.

#### File storage: Cloudflare R2 or another S3-compatible provider

The current storage client signs requests with `region_name="auto"`, matching Cloudflare R2. For R2:

1. In Cloudflare's R2 dashboard, create a bucket for this application and use its name as `S3_BUCKET_NAME`.
2. Create an R2 API token with **Object Read & Write** permissions limited to that bucket. Copy the generated S3 Access Key ID and Secret Access Key into `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. These variable names are used by Boto3 even for R2 credentials.
3. Copy the provider's S3 API endpoint into `S3_UPLOAD_ENDPOINT_URL`, typically `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. Use the account endpoint, not a bucket URL or public website URL.

See Cloudflare's [S3 setup guide](https://developers.cloudflare.com/r2/get-started/s3/) and [token documentation](https://developers.cloudflare.com/r2/api/tokens/).

Browser uploads also require a bucket CORS policy. In the bucket settings, allow your application's origins and the upload/read methods:

```json
[
  {
    "AllowedOrigins": ["http://localhost:8080", "http://127.0.0.1:8080"],
    "AllowedMethods": ["GET", "HEAD", "PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Add your production HTTPS origin when deploying. Origins include the scheme and port and have no trailing path. Keep the bucket private: this app uploads and retrieves objects through presigned URLs, including files marked public within the application's database. See [R2 CORS configuration](https://developers.cloudflare.com/r2/buckets/cors/).

For AWS S3, create a bucket and grant the application principal the required bucket and object access, including `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject`, scoped to the application bucket. Update the fixed `auto` region in both `get_s3_client()` and the S3 doctor check to the bucket's AWS region before using AWS S3. Setting an AWS endpoint alone does not change that region. Other S3-compatible providers may need the same adjustment. See [AWS presigned URL permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html) and [S3 CORS configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enabling-cors-examples.html).

#### Google login (optional)

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/), then configure Google Auth Platform's branding, audience, and requested data access. This app requests the `email` scope.
2. If the app is in testing mode with an external audience, add the accounts that will test login as test users.
3. Create an OAuth client with application type **Web application**. Register the exact callback URLs you use:

   ```text
   http://localhost:8080/auth/oauth/callback/google
   http://127.0.0.1:8080/auth/oauth/callback/google
   https://app.example.com/auth/oauth/callback/google
   ```

4. Copy the client ID and client secret into `OAUTH2_GOOGLE_CLIENT_ID` and `OAUTH2_GOOGLE_CLIENT_SECRET`. Replace the production example hostname with your real hostname.

The callback is built from the request's hostname and scheme. An existing app account with the same email is required; Google login does not create an account automatically. See [Google's OpenID Connect setup documentation](https://developers.google.com/identity/openid-connect/openid-connect).

#### Sentry error monitoring (optional)

Create a Python/Flask project in Sentry and copy its project DSN into `SENTRY_DSN`. The DSN is a project client key, not a personal API auth token. Leaving it blank skips Sentry initialization. The application already initializes the installed SDK when this value is present. See [Sentry project client keys](https://docs.sentry.io/api/projects/create-a-new-client-key/).

#### Environment, hostnames, proxy, and server settings

| Variable | Purpose and setup |
|----------|-------------------|
| `FLASK_ENV` | Use `development` locally and `production` in production. This controls application configuration; use `--debug` separately for Flask's development server. |
| `ADMIN_PANEL` | Enables the diagnostic/admin panel when `true`; the production example uses `false`. Access also requires the relevant user permission. |
| `TRUSTED_HOSTS` | Comma-separated accepted hostnames, without schemes or paths, such as `localhost:8080,127.0.0.1:8080` or `app.example.com`. Keep this aligned with the URLs people use. |
| `BEHIND_PROXY` | Set `true` only when the app is behind one trusted reverse proxy that supplies forwarding headers. The app applies ProxyFix for one proxy hop. Use `false` for direct local access. |
| `APP_PORT` | Gunicorn's local bind port. The Flask development server still needs its own `--port` argument. |
| `GUNICORN_WORKERS` | Number of worker processes; example value `2`. |
| `GUNICORN_THREADS` | Threads per worker; example value `4`. |
| `GUNICORN_TIMEOUT` | Worker timeout in seconds; example value `60`. |
| `GUNICORN_GRACEFUL_TIMEOUT` | Graceful restart/shutdown timeout in seconds; example value `30`. |
| `GUNICORN_KEEPALIVE` | Keep-alive timeout in seconds; example value `5`. |

For production, configure your domain, DNS, HTTPS, and reverse proxy before using the production callback URLs and CORS origins. Export the server settings before Gunicorn reads its configuration. For a trusted `.env` file containing the example's shell-compatible assignments, a POSIX shell can use:

```sh
set -a
. ./.env
set +a
gunicorn --config gunicorn.conf.py wsgi:app
```

Gunicorn binds to `127.0.0.1:$APP_PORT`; the reverse proxy forwards traffic to that port. Use your deployment platform's secret/environment configuration instead of sourcing a file when available.

#### Checking the completed setup

Run `flask --app app doctor` after configuring the database and providers. It checks database connectivity, Twilio account/service/number access, SendGrid key/template access, and storage bucket access. A successful check does not test browser CORS, OAuth callbacks, or actual message delivery; verify those through the application's registration, login, and upload flows.

Common setup failures:

- **Email 2FA fails:** Check the Verify Service's email integration and its separate code template, not only the app's SendGrid credentials.
- **Welcome emails are missing:** Confirm the sender is verified, the app template version is active, and the API key can send mail.
- **Google reports a redirect mismatch:** Compare the full callback URL, including scheme, host, port, and path, with the OAuth client's registered URLs.
- **Uploads fail in the browser:** Check CORS origins, bucket permissions, endpoint, and the signing region. A successful bucket check alone does not prove a browser upload can complete.
- **The app rejects the hostname:** Add the actual hostname to `TRUSTED_HOSTS` and check reverse-proxy forwarding settings.
