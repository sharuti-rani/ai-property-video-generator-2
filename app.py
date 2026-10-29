"""Flask application for AI Property Video Generator.

Video jobs run in a background thread so a long MP4 render does not keep the
browser's initial POST request open until the hosting platform times it out.
"""
import json
import logging
import os
import threading
import traceback
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, MAX_IMAGES, OUTPUT_DIR,
    SECRET_KEY, STATIC_DIR, TEMPLATE_DIR, UPLOAD_DIR,
)
from script_generator import generate_script
from video_generator import generate_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# In-memory job registry is sufficient for a single Render web instance.
# A job is kept until the service restarts; generated files live in OUTPUT_DIR.
JOBS = {}
JOBS_LOCK = threading.Lock()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _update_job(job_id, **values):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)


def _run_generation(job_id, property_data, image_paths, include_narration, output_path, output_filename):
    try:
        _update_job(job_id, status="processing", progress=5, message="Preparing property script...")
        script = generate_script(property_data, len(image_paths))

        def progress_callback(step, total, message):
            percent = 10 + int((step / max(total, 1)) * 80)
            _update_job(job_id, status="processing", progress=min(percent, 90), message=message)

        generate_video(
            image_paths=image_paths,
            script=script,
            output_path=output_path,
            include_narration=include_narration,
            progress_callback=progress_callback,
        )
        _update_job(
            job_id,
            status="completed",
            progress=100,
            message="Video ready!",
            result={
                "success": True,
                "video_url": f"/output/{output_filename}",
                "video_filename": output_filename,
                "script": script,
                "job_id": job_id,
                "num_images": len(image_paths),
            },
        )
        logger.info("Job %s completed: %s", job_id, output_path)
    except Exception as exc:
        logger.error("Job %s failed:\n%s", job_id, traceback.format_exc())
        _update_job(job_id, status="failed", progress=100, message="Video generation failed", error=str(exc))
    finally:
        # Keep upload files only for the duration of the job; outputs are preserved.
        for path in image_paths:
            try:
                os.remove(path)
            except OSError:
                pass
        if image_paths:
            try:
                os.rmdir(os.path.dirname(image_paths[0]))
            except OSError:
                pass


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/generate")
def api_generate():
    """Validate an upload and start video rendering as a background job."""
    try:
        raw = request.form.get("property_data", "{}")
        try:
            property_data = json.loads(raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid property details. Please try again."}), 400

        if not isinstance(property_data, dict):
            return jsonify({"error": "Property details must be a JSON object."}), 400
        property_data["property_name"] = str(property_data.get("property_name", "")).strip()
        if not property_data["property_name"]:
            return jsonify({"error": "Property name is required."}), 400

        features = property_data.get("key_features", [])
        if isinstance(features, str):
            property_data["key_features"] = [item.strip() for item in features.split(",") if item.strip()]
        elif not isinstance(features, list):
            property_data["key_features"] = []

        include_narration = property_data.pop("include_narration", True)
        if isinstance(include_narration, str):
            include_narration = include_narration.lower() in ("true", "1", "yes", "on")
        else:
            include_narration = bool(include_narration)

        images = request.files.getlist("images")
        images = [item for item in images if item and item.filename]
        if not images:
            return jsonify({"error": "Please upload at least one property image."}), 400
        if len(images) > MAX_IMAGES:
            return jsonify({"error": f"Please upload no more than {MAX_IMAGES} images."}), 400

        job_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        job_upload_dir = os.path.join(UPLOAD_DIR, job_id)
        os.makedirs(job_upload_dir, exist_ok=True)
        saved_images = []
        for image in images:
            if not allowed_file(image.filename):
                continue
            safe_name = secure_filename(image.filename) or "property-image.jpg"
            save_path = os.path.join(job_upload_dir, f"{len(saved_images):02d}_{safe_name}")
            image.save(save_path)
            saved_images.append(save_path)

        if not saved_images:
            try:
                os.rmdir(job_upload_dir)
            except OSError:
                pass
            return jsonify({"error": "Use PNG, JPG, JPEG, or WEBP image files."}), 400

        output_filename = f"property_video_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with JOBS_LOCK:
            JOBS[job_id] = {
                "status": "queued", "progress": 0, "message": "Your video is queued.",
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

        thread = threading.Thread(
            target=_run_generation,
            args=(job_id, property_data, saved_images, include_narration, output_path, output_filename),
            daemon=True,
        )
        thread.start()
        return jsonify({"success": True, "job_id": job_id, "status_url": url_for("job_status", job_id=job_id)}), 202
    except Exception:
        logger.exception("Could not start video generation")
        return jsonify({"error": "The server could not start this video job. Check the Render logs."}), 500


@app.get("/api/status/<job_id>")
def job_status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Video job not found. Please submit the form again."}), 404
        result = dict(job)
    return jsonify(result)


@app.get("/api/sample-data")
def sample_data():
    sample_path = os.path.join(os.path.dirname(__file__), "sample_data", "sample_property.json")
    if os.path.isfile(sample_path):
        try:
            with open(sample_path, "r", encoding="utf-8") as handle:
                return jsonify(json.load(handle))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read sample property JSON")
    return jsonify({
        "property_name": "Sunrise Heights",
        "location": "Mohali, Punjab",
        "price": "₹85 Lakhs",
        "property_type": "Modern Apartment",
        "bedrooms": "3",
        "bathrooms": "2",
        "area": "1450 sq. ft.",
        "key_features": ["Natural light", "Modern kitchen", "Balcony"],
        "contact_name": "Property Consultant",
        "contact_phone": "",
        "contact_email": "",
        "cta_text": "Book Your Site Visit Today!",
    })


@app.get("/output/<path:filename>")
def serve_video(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=False, conditional=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
