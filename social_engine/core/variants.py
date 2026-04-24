"""Social post skin variants — randomly selected per post.

Usage in jobs / renderer:
    from core.variants import pick_random_skin
    skin = pick_random_skin()
    html = template.render(**ctx, base_css=base_css, skin_class=skin["class"])
"""
import random

SKINS: list[dict] = [
    {
        "id":    "neural",
        "class": "skin-neural",
        "label": "Neural Cyan",
        "desc":  "Default AI-green + cyan glow, dot-grid bg",
    },
    {
        "id":    "plasma",
        "class": "skin-plasma",
        "label": "Plasma Gold",
        "desc":  "Championship gold + amber, diagonal-line bg, top-glow card border",
    },
    {
        "id":    "ice",
        "class": "skin-ice",
        "label": "Ice Command",
        "desc":  "Institutional blue + light-blue, dense dot-grid, minimal card borders",
    },
    {
        "id":    "crimson",
        "class": "skin-crimson",
        "label": "Crimson Protocol",
        "desc":  "High-conviction red + coral, horizontal-line bg, thick left stripe",
    },
    {
        "id":    "volt",
        "class": "skin-volt",
        "label": "Volt Purple",
        "desc":  "Luxury violet + hot-pink, checkerboard dot-grid, glow border",
    },
]


def pick_random_skin() -> dict:
    """Return a random skin. Use skin['class'] in template context."""
    return random.choice(SKINS)


def get_skin(skin_id: str) -> dict:
    """Fetch skin by id; falls back to neural if not found."""
    return next((s for s in SKINS if s["id"] == skin_id), SKINS[0])
