"""
Generate sample property images using Pillow for testing.
Creates realistic-looking placeholder images with gradients and labels.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_data", "images")

SCENES = [
    ("exterior", "Apartment Exterior", [(30, 60, 120), (60, 130, 200)]),
    ("living_room", "Living Room", [(120, 90, 60), (200, 170, 130)]),
    ("kitchen", "Modern Kitchen", [(80, 100, 80), (160, 190, 150)]),
    ("bedroom", "Master Bedroom", [(90, 70, 100), (170, 140, 190)]),
    ("bathroom", "Bathroom", [(60, 100, 110), (130, 190, 200)]),
    ("balcony", "Balcony View", [(40, 100, 150), (100, 180, 220)]),
    ("swimming_pool", "Swimming Pool", [(30, 80, 130), (80, 180, 230)]),
    ("gym", "Gymnasium", [(80, 80, 80), (160, 160, 160)]),
]

WIDTH, HEIGHT = 1920, 1080


def create_gradient(width, height, color1, color2):
    """Create a smooth gradient image."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def add_decorative_elements(img, draw, scene_type):
    """Add geometric shapes to make images look more realistic."""
    w, h = img.size
    random.seed(hash(scene_type))

    # Add some rectangular shapes to simulate room elements
    for _ in range(random.randint(3, 8)):
        x1 = random.randint(0, w - 200)
        y1 = random.randint(0, h - 200)
        x2 = x1 + random.randint(100, 400)
        y2 = y1 + random.randint(80, 300)
        opacity = random.randint(20, 60)
        color = (255, 255, 255, opacity)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [(x1, y1), (x2, y2)],
            radius=random.randint(5, 20),
            fill=color,
        )
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
        draw = ImageDraw.Draw(img)

    # Add a soft vignette effect
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vignette_draw = ImageDraw.Draw(vignette)
    for i in range(30):
        alpha = int((i / 30) * 40)
        vignette_draw.rectangle(
            [(i * 5, i * 3), (w - i * 5, h - i * 3)],
            outline=(0, 0, 0, alpha),
        )
    img_rgba = img.convert("RGBA")
    img = Image.alpha_composite(img_rgba, vignette).convert("RGB")
    return img


def generate_image(filename, label, color1, color2):
    """Generate a single sample image."""
    img = create_gradient(WIDTH, HEIGHT, color1, color2)
    draw = ImageDraw.Draw(img)

    # Add decorative elements
    img = add_decorative_elements(img, draw, filename)
    draw = ImageDraw.Draw(img)

    # Add a subtle camera icon / watermark area
    # Draw a centered label with a nice background box
    try:
        font_large = ImageFont.truetype("arial.ttf", 64)
        font_small = ImageFont.truetype("arial.ttf", 32)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Semi-transparent label box
    label_text = f"📸  {label}"
    bbox = draw.textbbox((0, 0), label_text, font=font_large)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    box_x1 = (WIDTH - text_w) // 2 - 40
    box_y1 = (HEIGHT - text_h) // 2 - 30
    box_x2 = (WIDTH + text_w) // 2 + 40
    box_y2 = (HEIGHT + text_h) // 2 + 30

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [(box_x1, box_y1), (box_x2, box_y2)],
        radius=15,
        fill=(0, 0, 0, 120),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Draw main label
    draw.text(
        ((WIDTH - text_w) // 2, (HEIGHT - text_h) // 2),
        label_text,
        fill=(255, 255, 255),
        font=font_large,
    )

    # Draw "SAMPLE IMAGE" subtitle
    subtitle = "SAMPLE IMAGE — FOR DEMONSTRATION"
    sbbox = draw.textbbox((0, 0), subtitle, font=font_small)
    sw = sbbox[2] - sbbox[0]
    draw.text(
        ((WIDTH - sw) // 2, box_y2 + 20),
        subtitle,
        fill=(200, 200, 200),
        font=font_small,
    )

    # Apply a slight blur to soften
    img = img.filter(ImageFilter.GaussianBlur(radius=1))

    return img


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating {len(SCENES)} sample images in: {OUTPUT_DIR}")

    for filename, label, (c1, c2) in SCENES:
        filepath = os.path.join(OUTPUT_DIR, f"{filename}.jpg")
        img = generate_image(filename, label, c1, c2)
        img.save(filepath, "JPEG", quality=92)
        print(f"  [OK] {filepath}")

    print("\nDone! Sample images are ready.")


if __name__ == "__main__":
    main()
