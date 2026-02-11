# 🚀 How to Deploy Your AI Backend to Hugging Face (From Scratch)

This guide assumes you are starting with **nothing** on Hugging Face and want to deploy your `Live-Measurements-Api` (Python/Flask) backend live during the hackathon.

---

## 🏗️ Step 1: Create the Space
1.  Go to [huggingface.co/spaces](https://huggingface.co/spaces).
2.  Click **"Create new Space"**.
3.  **Name:** `youngin-backend-v2` (or something unique).
4.  **License:** `MIT`.
5.  **SDK:** Select **Docker** (Crucial! Do not select Streamlit/Gradio).
6.  **Template:** Select **Blank**.
7.  **Visibility:** **Public** (Easiest for hackathon) or Private (Requires Token).
8.  Click **"Create Space"**.

---

## 📂 Step 2: Prepare Your Files
Since we deleted the backend from your project folder, you need to get it from the **Backup Zip**.

1.  Open `c:\Users\zeedan\OneDrive\Desktop\Youngin_AI_Backup.zip`.
2.  Extract the **`Live-Measurements-Api`** folder to your Desktop.
3.  Open that folder. It should contain:
    *   `app.py` or `index.py` (Main server file)
    *   `Dockerfile`
    *   `requirements.txt`
    *   `.env` (Optional, we'll set these in settings)
    *   `cv_utils.py` / `measurement_utils.py` (Helper files)

---

## 📤 Step 3: Upload Files to Hugging Face
1.  In your new Hugging Face Space, scroll down to **"Files"** tab (or click "Files and versions").
2.  Click **"Add file"** -> **"Upload files"**.
3.  **Drag and Drop** ALL the files from your extracted `Live-Measurements-Api` folder into the upload box.
    *   *Make sure `Dockerfile` is at the root level.*
4.  **Commit Message:** "Initial backend deployment".
5.  Click **"Commit changes to main"**.

---

## ⚙️ Step 4: Configure Environment Variables (Secrets)
Does your backend use a Gemini API Key? If yes:

1.  Go to **"Settings"** tab in your Space.
2.  Scroll to **"Variables and secrets"**.
3.  Click **"New secret"**.
    *   **Name:** `GOOGLE_API_KEY` (or whatever your `.env` uses).
    *   **Value:** Paste your actual API Key.
4.  Click **Save**.
    *   *The Space will automatically restart and rebuild.*

---

## ⏳ Step 5: Wait for Build
1.  Click the **"App"** tab.
2.  You will see **"Building..."** with a blue log.
    *   *This takes 3-5 minutes because it installs OpenCV and MediaPipe.*
3.  **Success:** When it says **"Running"** and shows a green badge.

---

## 🔗 Step 6: Connect Frontend (Vercel)
Your frontend (on Vercel) needs to know where this new backend is.

1.  Copy your Space URL (e.g., `https://zeedan991-youngin-backend-v2.hf.space`).
2.  Go to your **Local Project** -> `vercel.json`.
3.  Update the `destination` URL:
    ```json
    {
        "rewrites": [
            {
                "source": "/api/:path*",
                "destination": "https://zeedan991-youngin-backend-v2.hf.space/:path*"
            }
        ]
    }
    ```
4.  **Redeploy Frontend:**
    *   `git add vercel.json`
    *   `git commit -m "fix: Connected to new production backend"`
    *   `git push`

---

## 🆘 Troubleshooting (Emergency Dockerfile)
If your upload fails or the `Dockerfile` is missing/broken, create a new file named `Dockerfile` on Hugging Face and paste this **Standard Robust Config**:

```dockerfile
FROM python:3.9-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create a non-root user (Hugging Face requirement)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Command to run Flask (Adjust 'index:app' to your filename)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "index:app"]
```
*(Make sure `requirements.txt` includes `gunicorn`, `flask`, `opencv-python-headless`, `mediapipe`)*.
