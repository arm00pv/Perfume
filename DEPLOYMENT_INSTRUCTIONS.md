# Render Deployment Settings

Here are the recommended settings for deploying your backend service on Render. This should resolve the deployment errors you've been seeing.

### Service Type
- Make sure you are creating a **"Web Service"**.

### Build & Deploy Settings
- **Root Directory:** `backend`
  - This is important! It tells Render to look inside the `backend` folder for your code and `requirements.txt`.
- **Build Command:** `pip install -r requirements.txt`
  - This command installs all the necessary dependencies.
- **Start Command:** `gunicorn app:app`
  - This command starts your application using the Gunicorn production server.

### Environment Settings
- **Python Version:** `3.12.11`
  - As we discovered, this is crucial. Make sure this is set correctly in your service's environment settings.
- **Environment Variables:** You need to add your Roboflow API key as a secret environment variable.
  - **Key:** `ROBOFLOW_API_KEY`
  - **Value:** `w4tiynu7N3E90ZAZY8aT` (This is the key you provided)

### Summary
With these settings, Render will:
1. Look inside your `backend` directory.
2. Install the correct dependencies (including `gunicorn`).
3. Use the correct Python version (3.12.11).
4. Run your application with the correct start command.
5. Provide your application with the necessary API key.

After you apply these settings and redeploy, the backend should be fully functional. You can then deploy the `frontend` folder as a **"Static Site"** on Render, and it will work with your live backend.
