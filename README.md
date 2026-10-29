# AI Property Video Generator

A Flask web app that turns property details and photos into an MP4 promotional video. It creates a script with Google Gemini when `GEMINI_API_KEY` is configured and otherwise uses a built-in template script. Voice narration is optional.

## Included fixes

- The HTML page is correctly located at `templates/index.html`, matching Flask's `render_template("index.html")` call.
- The frontend reads error responses safely instead of always trying to parse HTML as JSON.
- Video rendering runs in a background thread; the browser polls job status rather than waiting for a long render request to finish.
- - Render deployment files and a health endpoint are included.
- Slides are pre-rendered and encoded by FFmpeg to avoid slow Python frame compositing on small hosting instances.

## Deploy on Render

1. Upload the contents of this folder to your GitHub repository (the `app.py`, `config.py`, `script_generator.py`, `video_generator.py`, `requirements.txt`, `render.yaml`, `Procfile`, and `templates/index.html` must be at the repository root/paths shown).
2. On Render, create a **Web Service** from the GitHub repository.
3. Use build command `pip install -r requirements.txt` and start command `gunicorn app:app --workers 1 --threads 4 --timeout 300` (or let `render.yaml` configure it).
4. Optional: add `GEMINI_API_KEY` in Render → Environment. Without it, the app uses its template-based script generator.
5. Check `/health` for a small JSON health response and use Render Logs if a generation job fails.

## Run locally

Requires Python 3.12 and internet access if voice narration is enabled.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Upload at least one JPG, PNG, or WEBP image and enter a property name. Turn narration off for the first test if you want to avoid the external text-to-speech request.

## Important limitations

No source package can guarantee zero failures on every hosting plan. Rendering performance depends on available CPU/RAM, image sizes, and hosting limits. Render free instances may sleep when idle and their local files can be ephemeral; download generated videos promptly. Do not commit API keys to GitHub.
