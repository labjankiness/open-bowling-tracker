# Live Bowling Tracker — Web & Cloud Dashboard

A private, modern web dashboard for tracking bowler biomechanics and pin-deck scoring with automated Google Drive export.

## Features

- 🔒 **Private & Secure**: Protected by an access passcode (`BOWLING_SECRET_KEY`).
- 📹 **Drag & Drop Video Upload**: Supports MP4 and MOV (up to 4K 60fps).
- 📊 **Biomechanics Analytics**: Real-time pose skeleton tracking, peak release velocity, spine tilt, and knee angle curves.
- 🎳 **Pin Deck Scoring**: Classical computer vision frame-by-frame roll detection and scorecard generation.
- ☁️ **Google Drive Auto-Sync**: Automatically saves annotated MP4 video output and CSV metrics back to your Google Drive folder.
- 📱 **Mobile & Desktop Optimized**: Responsive dark UI ready to use on phones at the bowling alley or desktop in Chrome.

---

## Local Development & Chrome Testing

1. Activate virtual environment:
   ```bash
   source venv/bin/activate
   ```
2. Start the web server:
   ```bash
   uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Open in Google Chrome:
   ```
   http://localhost:8000
   ```
   * Default Passcode: `bowling2026` (or set `export BOWLING_SECRET_KEY="your_custom_passcode"`).

---

## 24/7 Cloud Hosting (Private to You)

### Option A: Hugging Face Spaces (Free, 24/7, 16GB RAM / 2 vCPUs)
1. Create a new Space on [huggingface.co/new-space](https://huggingface.co/new-space).
2. Select **Docker** SDK and set visibility to **Private** (or Public with password protection).
3. Connect your GitHub repository `labjankiness/live-bowling-tracker`.
4. Add the secret environment variable:
   - `BOWLING_SECRET_KEY`: `your_custom_passcode`
5. The space builds automatically using `Dockerfile` and gives you a 24/7 URL!

### Option B: Render.com / Railway.app
1. Create a new Web Service pointing to `labjankiness/live-bowling-tracker`.
2. Choose Docker environment.
3. Add Environment Variable:
   - `BOWLING_SECRET_KEY`: `your_secret_passcode`
4. Deploy — live 24/7!

---

## Google Drive Setup

1. In the top-right corner of the dashboard, click **Google Drive Sync**.
2. Paste your target **Google Drive Folder ID** (from your browser URL `drive.google.com/drive/folders/<FOLDER_ID>`).
3. Upload your Google Cloud Service Account JSON key (or set `GOOGLE_APPLICATION_CREDENTIALS`).
4. Ensure the Service Account email has **Editor** access to your Google Drive folder.
5. All future processed videos and CSVs will automatically sync to your Drive.
