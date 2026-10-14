# AttendAI: open the app without keeping your laptop running

GitHub stores the source code. Railway runs the application and MySQL online.
Visitors use the HTTPS address Railway generates. Add that address to your
GitHub repository's About -> Website field and README as the Live Demo link.

These additional files were prepared against your saved AttendAI project ZIP.
They do not include or replace your updated CSS, templates, or existing app code.
Use them with the Flask version that contains app/, config.py, and run.py.

## 1. Add these files to the existing repository

Copy the contents of this ZIP directly into P:\AttendAI-GitHub, alongside run.py.
The Dockerfile must be at the repository root, not inside another folder.

In the VS Code PowerShell terminal run these commands one at a time:

```powershell
cd P:\AttendAI-GitHub
git add Dockerfile .dockerignore cloud_app.py requirements-cloud.txt DEPLOY_RAILWAY.md
git commit -m "Add AttendAI cloud deployment setup"
git push origin main
```

## 2. Create the Railway project and MySQL service

1. Open https://railway.com and sign in with GitHub.
2. Review the plan and usage limits in your dashboard before starting services.
   Railway offers limited trial credits; continuous Flask + MySQL hosting is
   not guaranteed to fit the Free plan. Hobby starts at USD 5/month and usage
   above the included amount costs extra. Do not select a paid upgrade unless
   you want those charges.
3. Create an Empty Project and give it a name such as AttendAI.
4. Add a Database service -> MySQL. Leave its name as MySQL for the variable
   reference below. Wait for it to become ready.
5. Add a GitHub Repository service -> prajit242006/AttendAI, branch main.
   Grant Railway access to this repository if asked.
6. Railway detects the Dockerfile. The initial app deployment may fail until
   the following variables and volume are configured. Complete the setup and
   redeploy. Leave the Build Command and Start Command overrides empty so the
   Dockerfile controls both.

## 3. Configure the AttendAI APP service

Open the AttendAI app service's Variables tab (not the MySQL service).

| Variable | Value |
| --- | --- |
| MYSQL_URL | ${{MySQL.MYSQL_URL}} |
| SECRET_KEY | A random secret generated below |
| DEFAULT_TEACHER_USERNAME | admin |
| DEFAULT_TEACHER_PASSWORD | A new private password, at least 12 characters |

Use Railway's Add Reference option for MYSQL_URL if available; select the
MySQL service's MYSQL_URL. If you renamed that service, use its actual name.
The app automatically selects PyMySQL. Do not point the cloud app at localhost.

Generate a secret locally with your existing Python installation:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy that result into Railway's SECRET_KEY field. Do not commit secrets to GitHub.
The default teacher password is used only when creating a new account. Changing
the variable later does not change the password of an existing teacher account.

## 4. Attach persistent storage and deploy

1. Attach a Railway Volume to the AttendAI app service at mount path /data.
   This is separate from the MySQL service's own database volume.
2. Keep the app at one replica. The Dockerfile also uses one Gunicorn worker,
   because AttendAI keeps liveness challenge state in process memory.
3. Deploy the pending changes or redeploy the app service.
4. The application creates empty database tables and the configured teacher
   account when it starts. Local student data and trained faces are not imported.
5. After the service becomes healthy, open Settings -> Networking -> Public
   Networking -> Generate Domain. Use the port Railway detects from PORT.
6. Open the generated HTTPS link and log in using the username/password you
   configured. If a healthcheck is required, use /healthz.

The /data volume keeps face samples and the trained model across deployments.
The MySQL service stores users, students, subjects, and attendance records.
Create demo students and register their faces again on the hosted app.

## 5. Verify the public website

1. Open the HTTPS domain on your phone using mobile data, or on a friend's device.
2. Confirm that the login page loads and teacher login works.
3. Create a demo subject/student and test camera registration. Allow browser
   camera permission. The camera used is on the visitor's device.
4. Confirm that saved records remain after an app restart.
5. Close your local Flask terminal and open the hosted HTTPS link again.
6. Share the HTTPS link, and put it in GitHub's About -> Website and README.
   Keep localhost listed only as a local-development address.

Do not publish the admin password. Friends who only need to view their own
attendance should receive their own student accounts.

## If something fails

- Build fails: open Build Logs and copy the final error lines.
- Missing SECRET_KEY or DEFAULT_TEACHER_PASSWORD: add the variables to the app.
- MySQL connection error: check the reference and that the MySQL service is up.
- Camera unavailable: use HTTPS and grant camera access in the browser.
- Face data disappears after redeploy: check the app volume mount is /data.
- Website stops after trial: check billing/usage in the Railway dashboard.

This kit does not create or pay for a Railway account, import your local MySQL
records, or deploy the website by itself. A real public URL exists only after
you finish the Railway setup.

## Validation performed

- Installed all cloud requirements successfully in an isolated Linux environment.
- Passed all 14 tests bundled with your saved project (helpers, detector,
  liveness, model training, and recognition).
- Checked cloud startup, teacher creation, secure cookies, the health route,
  HTTPS login with CSRF, and teacher dashboard rendering. This smoke test used
  a temporary SQLite database in place of a hosted MySQL instance.
- Checked that restarting does not duplicate the teacher account, and that
  headless OpenCV includes the LBPH face-recognition module.
- Validation used Python 3.12. The Dockerfile selects Python 3.11, as used by
  your original project. A Docker image build, real MySQL connection, browser
  webcam session, and live Railway deployment have not been tested here.

Official references, checked 14 October 2026:
- https://docs.railway.com/guides/flask
- https://docs.railway.com/databases/mysql
- https://docs.railway.com/volumes
- https://docs.railway.com/networking/public-networking
- https://docs.railway.com/pricing/plans
