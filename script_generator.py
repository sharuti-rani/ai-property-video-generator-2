"""
Script Generator — Uses Gemini API to create voiceover scripts and captions.
Falls back to a smart template engine if the API key is unavailable.
"""
import json
import logging

logger = logging.getLogger(__name__)


def _build_prompt(property_data: dict, num_images: int) -> str:
    """Build a structured prompt for the Gemini model."""
    features_text = ""
    if property_data.get("key_features"):
        features_text = "\n".join(
            f"  - {f}" for f in property_data["key_features"]
        )

    return f"""You are a professional real estate copywriter creating a voiceover script
for a short property video (20-40 seconds). The video has {num_images} image scenes plus
a title card and a closing CTA card.

PROPERTY DETAILS:
- Name: {property_data.get('property_name', 'Beautiful Property')}
- Location: {property_data.get('location', '')}
- Price: {property_data.get('price', '')}
- Type: {property_data.get('property_type', '')}
- Bedrooms: {property_data.get('bedrooms', '')}
- Bathrooms: {property_data.get('bathrooms', '')}
- Area: {property_data.get('area', '')}
- Key Features:
{features_text}
- Contact: {property_data.get('contact_name', '')} | {property_data.get('contact_phone', '')}
- CTA: {property_data.get('cta_text', 'Contact us today!')}

IMPORTANT RULES:
1. Only use facts provided above. Do NOT invent any details.
2. Keep the total script under 100 words.
3. The tone should be warm, professional, and inviting.
4. If a detail is missing/empty, skip it — do not mention it.

Return a JSON object with this exact structure:
{{
  "title_text": "Short punchy title for the opening card (max 8 words)",
  "title_subtitle": "One-line subtitle with location/price",
  "scenes": [
    {{
      "caption": "Short overlay text for this scene (max 12 words)",
      "voiceover": "One sentence voiceover narration for this scene"
    }}
  ],
  "cta_headline": "Closing headline (max 6 words)",
  "cta_body": "Brief closing with contact info",
  "full_voiceover": "Complete voiceover script combining all scenes into a flowing narrative"
}}

Generate exactly {num_images} scene entries. Return ONLY the JSON, no markdown fences.
"""


def generate_script_with_gemini(property_data: dict, num_images: int) -> dict:
    """Generate script using Google Gemini API."""
    import google.generativeai as genai
    from config import GEMINI_API_KEY, GEMINI_MODEL

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = _build_prompt(property_data, num_images)

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
        ),
    )

    text = response.text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        script = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini returned invalid JSON, falling back to template")
        script = generate_script_with_template(property_data, num_images)

    return _validate_script(script, property_data, num_images)


def generate_script_with_template(property_data: dict, num_images: int) -> dict:
    """Template-based fallback — creates a professional script without any API."""
    name = property_data.get("property_name", "Beautiful Property")
    location = property_data.get("location", "")
    price = property_data.get("price", "")
    prop_type = property_data.get("property_type", "Property")
    bedrooms = property_data.get("bedrooms", "")
    bathrooms = property_data.get("bathrooms", "")
    area = property_data.get("area", "")
    features = property_data.get("key_features", [])
    contact_name = property_data.get("contact_name", "")
    contact_phone = property_data.get("contact_phone", "")
    contact_email = property_data.get("contact_email", "")
    cta_text = property_data.get("cta_text", "Contact us today!")

    # Build title
    title_text = f"Welcome to {name}"
    subtitle_parts = [p for p in [prop_type, location] if p]
    title_subtitle = " | ".join(subtitle_parts) if subtitle_parts else name

    # Build scenes
    scene_templates = []

    # Scene pool — we'll pick based on available data and num_images
    if prop_type or bedrooms or area:
        parts = []
        if prop_type:
            parts.append(prop_type)
        if bedrooms and bathrooms:
            parts.append(f"{bedrooms} Bed, {bathrooms} Bath")
        elif bedrooms:
            parts.append(f"{bedrooms} Bedrooms")
        if area:
            parts.append(area)
        caption = " · ".join(parts)
        vo = f"This stunning {prop_type or 'property'}"
        if area:
            vo += f" spans {area}"
        if bedrooms:
            vo += f" with {bedrooms} spacious bedrooms"
        vo += "."
        scene_templates.append({"caption": caption, "voiceover": vo})

    if price:
        scene_templates.append({
            "caption": f"Priced at {price}",
            "voiceover": f"Available at an attractive price of {price}, offering exceptional value.",
        })

    for feat in features:
        scene_templates.append({
            "caption": feat,
            "voiceover": f"Enjoy {feat.lower()}.",
        })

    if location:
        scene_templates.append({
            "caption": f"Located in {location}",
            "voiceover": f"Perfectly situated in {location}, with excellent connectivity.",
        })

    # Ensure we have enough scenes
    while len(scene_templates) < num_images:
        scene_templates.append({
            "caption": f"{name} — Your Dream Home",
            "voiceover": f"{name} offers a lifestyle of comfort and elegance.",
        })

    scenes = scene_templates[:num_images]

    # Build CTA
    cta_headline = cta_text or "Your Dream Home Awaits"
    cta_parts = []
    if contact_name:
        cta_parts.append(f"Contact {contact_name}")
    if contact_phone:
        cta_parts.append(contact_phone)
    if contact_email:
        cta_parts.append(contact_email)
    cta_body = " | ".join(cta_parts) if cta_parts else "Get in touch today!"

    # Build full voiceover
    full_vo = " ".join(s["voiceover"] for s in scenes)
    full_vo += f" {cta_headline}. {cta_body}."

    return {
        "title_text": title_text,
        "title_subtitle": title_subtitle,
        "scenes": scenes,
        "cta_headline": cta_headline,
        "cta_body": cta_body,
        "full_voiceover": full_vo,
    }


def _validate_script(script: dict, property_data: dict, num_images: int) -> dict:
    """Ensure script has all required fields and correct number of scenes."""
    defaults = generate_script_with_template(property_data, num_images)

    for key in ["title_text", "title_subtitle", "cta_headline", "cta_body", "full_voiceover"]:
        if not script.get(key):
            script[key] = defaults[key]

    if not script.get("scenes") or len(script["scenes"]) != num_images:
        script["scenes"] = defaults["scenes"]

    for i, scene in enumerate(script["scenes"]):
        if not scene.get("caption"):
            scene["caption"] = defaults["scenes"][i]["caption"]
        if not scene.get("voiceover"):
            scene["voiceover"] = defaults["scenes"][i]["voiceover"]

    return script


def generate_script(property_data: dict, num_images: int) -> dict:
    """
    Main entry point — tries Gemini first, falls back to template.
    Returns a script dict with title, scenes, CTA, and full voiceover.
    """
    from config import GEMINI_API_KEY

    if GEMINI_API_KEY:
        try:
            logger.info("Generating script with Gemini API...")
            return generate_script_with_gemini(property_data, num_images)
        except Exception as e:
            logger.warning(f"Gemini API failed: {e}. Falling back to template.")

    logger.info("Generating script with template engine...")
    return generate_script_with_template(property_data, num_images)
