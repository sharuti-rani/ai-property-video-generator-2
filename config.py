"""Configuration for AI Property Video Generator."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

for directory in (UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR, ASSETS_DIR, FONTS_DIR):
    os.makedirs(directory, exist_ok=True)

# Moderate render settings to keep video generation practical on small web instances.
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 24
SCENE_DURATION = 3.5
TRANSITION_DURATION = 0.5
TITLE_DURATION = 3.0
CTA_DURATION = 3.5
MAX_IMAGES = 8
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

TTS_LANG = "en"
TTS_SLOW = False
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024
