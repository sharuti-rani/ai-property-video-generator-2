"""Fast MP4 video renderer using Pillow and the FFmpeg binary bundled by imageio-ffmpeg.

Rendering pre-composes still slides and lets FFmpeg encode them, avoiding the
large per-frame Python overhead that can make small web instances time out.
"""
import logging
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio_ffmpeg

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, SCENE_DURATION,
    TITLE_DURATION, CTA_DURATION, FONTS_DIR, TTS_LANG, TTS_SLOW,
)

logger = logging.getLogger(__name__)


def _font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend([
            os.path.join(FONTS_DIR, "Montserrat-Bold.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ])
    else:
        candidates.extend([
            os.path.join(FONTS_DIR, "Montserrat-Regular.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ])
    for path in candidates:
        try:
            if os.path.isfile(path):
                return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = str(text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _draw_centered_text(draw, text, y, font, fill, max_width, line_gap=10):
    lines = _wrap_text(draw, text, font, max_width)
    heights = [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines]
    total_h = sum(heights) + line_gap * (len(lines) - 1)
    cursor_y = int(y - total_h / 2)
    for line, height in zip(lines, heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        x = max(20, (VIDEO_WIDTH - width) // 2)
        draw.text((x + 2, cursor_y + 3), line, font=font, fill=(0, 0, 0, 170), stroke_width=0)
        draw.text((x, cursor_y), line, font=font, fill=fill)
        cursor_y += height + line_gap


def _gradient(top=(14, 19, 31), bottom=(35, 53, 77)):
    image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(VIDEO_HEIGHT):
        t = y / max(VIDEO_HEIGHT - 1, 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, VIDEO_WIDTH, y), fill=color)
    return image


def _title_slide(script):
    image = _gradient()
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((60, 55, VIDEO_WIDTH - 60, VIDEO_HEIGHT - 55), outline=(201, 169, 110, 190), width=2)
    _draw_centered_text(draw, script.get("title_text", "Beautiful Property"), VIDEO_HEIGHT // 2 - 55, _font(48, True), (244, 239, 230, 255), VIDEO_WIDTH - 150)
    _draw_centered_text(draw, script.get("title_subtitle", "Discover your next home"), VIDEO_HEIGHT // 2 + 45, _font(25), (227, 207, 163, 255), VIDEO_WIDTH - 150)
    return image


def _image_slide(path, caption):
    with Image.open(path) as source:
        image = ImageOps.fit(source.convert("RGB"), (VIDEO_WIDTH, VIDEO_HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    # Darken the bottom band so the caption stays readable.
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle((0, VIDEO_HEIGHT - 150, VIDEO_WIDTH, VIDEO_HEIGHT), fill=(0, 0, 0, 155))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_centered_text(draw, caption or "A place to call home", VIDEO_HEIGHT - 78, _font(29, True), (255, 255, 255, 255), VIDEO_WIDTH - 100, 6)
    return image.convert("RGB")


def _cta_slide(script):
    image = _gradient((24, 13, 35), (58, 29, 66))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((60, 55, VIDEO_WIDTH - 60, VIDEO_HEIGHT - 55), outline=(201, 169, 110, 190), width=2)
    _draw_centered_text(draw, script.get("cta_headline", "Your Dream Home Awaits"), VIDEO_HEIGHT // 2 - 60, _font(43, True), (227, 207, 163, 255), VIDEO_WIDTH - 150)
    _draw_centered_text(draw, script.get("cta_body", "Get in touch today"), VIDEO_HEIGHT // 2 + 45, _font(24), (244, 239, 230, 255), VIDEO_WIDTH - 150)
    return image


def _generate_tts_audio(text: str, output_path: str) -> str:
    from gtts import gTTS
    gTTS(text=text, lang=TTS_LANG, slow=TTS_SLOW).save(output_path)
    return output_path


def generate_video(
    image_paths: list[str],
    script: dict,
    output_path: str,
    include_narration: bool = True,
    progress_callback=None,
) -> str:
    if not image_paths:
        raise ValueError("At least one image is required to generate a video.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    total_steps = 4

    def progress(step, message):
        logger.info("[%s/%s] %s", step, total_steps, message)
        if progress_callback:
            progress_callback(step, total_steps, message)

    temp_dir = tempfile.TemporaryDirectory(prefix="property_video_")
    try:
        slide_dir = Path(temp_dir.name)
        slide_specs = []
        progress(1, "Creating title card...")
        title_path = slide_dir / "slide_000.jpg"
        _title_slide(script).save(title_path, "JPEG", quality=88, optimize=True)
        slide_specs.append((title_path, TITLE_DURATION))

        progress(2, "Preparing property photo scenes...")
        scenes = script.get("scenes", [])
        for index, image_path in enumerate(image_paths):
            caption = scenes[index].get("caption", "") if index < len(scenes) else ""
            slide_path = slide_dir / f"slide_{index + 1:03d}.jpg"
            _image_slide(image_path, caption).save(slide_path, "JPEG", quality=88, optimize=True)
            slide_specs.append((slide_path, SCENE_DURATION))

        progress(3, "Creating closing card...")
        cta_path = slide_dir / "slide_end.jpg"
        _cta_slide(script).save(cta_path, "JPEG", quality=88, optimize=True)
        slide_specs.append((cta_path, CTA_DURATION))

        # Use FFmpeg's image demuxer + concat filter: far less CPU-intensive than
        # compositing every frame in Python, especially on hosted free instances.
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        filter_parts = []
        for i, (slide_path, duration) in enumerate(slide_specs):
            command.extend(["-loop", "1", "-framerate", str(VIDEO_FPS), "-t", str(duration), "-i", str(slide_path)])
            filter_parts.append(f"[{i}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={VIDEO_FPS},format=yuv420p[v{i}]")
        concat_inputs = "".join(f"[v{i}]" for i in range(len(slide_specs)))
        filter_parts.append(f"{concat_inputs}concat=n={len(slide_specs)}:v=1:a=0[outv]")
        command.extend([
            "-filter_complex", ";".join(filter_parts), "-map", "[outv]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
        ])
        progress(4, "Encoding MP4 video...")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)
        if result.returncode != 0:
            logger.error("FFmpeg failed: %s", result.stderr[-4000:])
            raise RuntimeError("FFmpeg could not encode the MP4. Please try fewer or smaller photos.")

        if include_narration and script.get("full_voiceover", "").strip():
            try:
                audio_path = slide_dir / "narration.mp3"
                narrated_path = slide_dir / "narrated.mp4"
                _generate_tts_audio(script["full_voiceover"], str(audio_path))
                mux_command = [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(output), "-i", str(audio_path),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-af", "apad", "-t", str(TITLE_DURATION + len(image_paths) * SCENE_DURATION + CTA_DURATION),
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(narrated_path),
                ]
                mux_result = subprocess.run(mux_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
                if mux_result.returncode == 0 and narrated_path.exists() and narrated_path.stat().st_size > 0:
                    os.replace(narrated_path, output)
                else:
                    logger.warning("Could not mux narration; keeping video without narration: %s", mux_result.stderr[-1000:])
            except Exception as exc:
                # Voiceover is optional; a TTS/network issue should not destroy the MP4.
                logger.warning("Narration failed; keeping video without narration: %s", exc)

        if not output.exists() or output.stat().st_size < 1000:
            raise RuntimeError("The MP4 file was not created successfully.")
        logger.info("Video saved to %s (%s bytes)", output, output.stat().st_size)
        return str(output)
    finally:
        temp_dir.cleanup()
