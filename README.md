# ShelfWise Library Management System

A simple library-management website built with FastAPI, Jinja2, SQLAlchemy, and PostgreSQL/SQLite. It is deployed on Render.

**Live site:** https://shelfwise-library-2e6m.onrender.com

## Features
- Admin login
- Dashboard with book, member, active-loan, and overdue counts
- Add/search/delete books
- Add/search/delete members
- Issue books with a due date
- Return books and update available-copy counts
- PostgreSQL on Render; SQLite fallback for local development
- Health endpoint at `/health`

## Live deployment
The app is running at **https://shelfwise-library-2e6m.onrender.com**.

- **Login:** use the `ADMIN_USERNAME` and `ADMIN_PASSWORD` values you set in Render during deployment.
- **Health check:** https://shelfwise-library-2e6m.onrender.com/health
- **Cold starts:** on Render's free tier, the service may spin down after a period of inactivity. The first request after that can take up to a minute to respond.
- **Database:** data is stored in the Render-managed PostgreSQL database provisioned by `render.yaml`.

## Run locally
Requires Python 3.10+.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD='Choose-A-Strong-Password'
export SESSION_SECRET='use-a-long-random-secret'
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. On Windows Command Prompt, use `set ADMIN_USERNAME=admin` etc. instead of `export`.

Default local login if environment variables are not set:
- Username: `admin`
- Password: `ChangeMe123!`

Change these defaults before exposing the app to the internet. These defaults apply to local development only; the deployed site uses the credentials you set in Render.

## Deploy to Render
1. Create a GitHub repository and upload all files/folders from this project to its root.
2. In Render, choose **New + → Blueprint** and connect that repository.
3. Render reads `render.yaml` and provisions the web service and PostgreSQL database.
4. When asked for `ADMIN_USERNAME` and `ADMIN_PASSWORD`, set your own values. Use a strong password.
5. Deploy, wait for the build to finish, then open the generated `onrender.com` URL and log in.

If you prefer creating a Web Service manually, use:
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add a PostgreSQL database and set the web service's `DATABASE_URL` to its internal connection string.
- Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and a long random `SESSION_SECRET`.

## Updating the deployed site
Render redeploys automatically when you push to the connected branch (if auto-deploy is enabled):

```bash
git add .
git commit -m "Describe your change"
git push
```

You can also trigger a manual deploy from the Render dashboard.

## Important notes
- Render's local filesystem is ephemeral for many service configurations. This project uses PostgreSQL when deployed via the included Blueprint so data is stored in the database, not in a local SQLite file.
- The starter project has one admin login configured through environment variables. It does not include self-registration, password reset, multiple staff accounts, fine-grained roles, or CSRF protection. Add those before using it for sensitive or production workloads.
- This is an educational starter, not a fully audited production system.

<div align="center">

Developed by Lakshya Kansal

</div>
