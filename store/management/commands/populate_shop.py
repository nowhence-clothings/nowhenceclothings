"""
Populate the shop with dummy products and generate placeholder images via Pillow.
Usage: python manage.py populate_shop
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.core.management.base import BaseCommand
from store.models import ShowcaseProduct

# Colour palettes per category (bg, accent)
PALETTES = {
    'bridal':   [('#3d1f1f', '#c4a57b'), ('#2e1515', '#d4b48a'), ('#4a2525', '#e0c9a0')],
    'designer': [('#1f2a3d', '#c4a57b'), ('#15202e', '#b8a070'), ('#253545', '#d0b888')],
    'festival': [('#3d2e1f', '#c4a57b'), ('#2e2515', '#d0b070'), ('#453520', '#c8a868')],
    'party':    [('#2d1f3d', '#c4a57b'), ('#201530', '#b890c0'), ('#352545', '#d0a8e0')],
    'casual':   [('#1f3d2a', '#c4a57b'), ('#153020', '#90c0a0'), ('#254535', '#a8d0b8')],
}

PRODUCTS = [
    {'name': 'Royal Crimson Bridal Lehenga',      'category': 'bridal',   'price': 89999, 'discount': 15},
    {'name': 'Golden Embroidered Bridal Set',      'category': 'bridal',   'price': 125000, 'discount': 10},
    {'name': 'Ivory Pearl Bridal Ensemble',        'category': 'bridal',   'price': 78500,  'discount': 0},
    {'name': 'Midnight Velvet Designer Lehenga',   'category': 'designer', 'price': 64990, 'discount': 20},
    {'name': 'Rose Gold Sequin Designer Set',      'category': 'designer', 'price': 55000, 'discount': 12},
    {'name': 'Sapphire Blue Couture Lehenga',      'category': 'designer', 'price': 72000, 'discount': 0},
    {'name': 'Diwali Collection Floral Lehenga',   'category': 'festival', 'price': 35990, 'discount': 25},
    {'name': 'Navratri Special Chaniya Choli',     'category': 'festival', 'price': 28500, 'discount': 18},
    {'name': 'Festive Magenta Mirror Work',        'category': 'festival', 'price': 42000, 'discount': 0},
    {'name': 'Champagne Cocktail Lehenga',         'category': 'party',    'price': 45990, 'discount': 15},
    {'name': 'Starlight Black Shimmer Set',        'category': 'party',    'price': 38000, 'discount': 22},
    {'name': 'Blush Pink Party Lehenga',           'category': 'party',    'price': 32500, 'discount': 0},
    {'name': 'Cotton Pastel Summer Lehenga',       'category': 'casual',   'price': 15990, 'discount': 10},
    {'name': 'Linen Everyday Comfort Set',         'category': 'casual',   'price': 12500, 'discount': 0},
    {'name': 'Indigo Block Print Lehenga',         'category': 'casual',   'price': 18990, 'discount': 30},
]


def make_placeholder(media_dir, filename, label, category, w=600, h=800):
    """Generate an elegant placeholder image."""
    idx = hash(filename) % len(PALETTES.get(category, PALETTES['bridal']))
    bg, accent = PALETTES[category][idx]
    img = Image.new('RGB', (w, h), bg)
    draw = ImageDraw.Draw(img)

    accent_rgb = tuple(int(accent.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    light = tuple(min(c + 40, 255) for c in accent_rgb)

    for i in range(3):
        offset = 20 + i * 8
        draw.rectangle([offset, offset, w - offset, h - offset],
                       outline=(*accent_rgb, 60), width=1)

    cx, cy = w // 2, h // 2 - 30
    size = 80
    diamond = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
    draw.polygon(diamond, outline=light, fill=None)
    inner = 50
    diamond2 = [(cx, cy - inner), (cx + inner, cy), (cx, cy + inner), (cx - inner, cy)]
    draw.polygon(diamond2, outline=accent_rgb, fill=None)

    draw.line([(cx - 120, cy), (cx - size - 10, cy)], fill=accent_rgb, width=1)
    draw.line([(cx + size + 10, cy), (cx + 120, cy)], fill=accent_rgb, width=1)

    try:
        font_sm = ImageFont.truetype("arial.ttf", 14)
        font_lg = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font_sm = ImageFont.load_default()
        font_lg = font_sm

    cat_text = category.upper()
    cat_bbox = draw.textbbox((0, 0), cat_text, font=font_sm)
    cat_w = cat_bbox[2] - cat_bbox[0]
    draw.text(((w - cat_w) // 2, cy + size + 30), cat_text, fill=accent_rgb, font=font_sm)

    words = label.split()
    line1 = ' '.join(words[:3])
    line2 = ' '.join(words[3:]) if len(words) > 3 else ''
    bbox1 = draw.textbbox((0, 0), line1, font=font_lg)
    draw.text(((w - (bbox1[2] - bbox1[0])) // 2, cy + size + 60), line1, fill=light, font=font_lg)
    if line2:
        bbox2 = draw.textbbox((0, 0), line2, font=font_lg)
        draw.text(((w - (bbox2[2] - bbox2[0])) // 2, cy + size + 88), line2, fill=light, font=font_lg)

    wm = 'Nowhence Clothings'
    wm_bbox = draw.textbbox((0, 0), wm, font=font_sm)
    draw.text(((w - (wm_bbox[2] - wm_bbox[0])) // 2, h - 50), wm, fill=(*accent_rgb, 80), font=font_sm)

    path = media_dir / filename
    img.save(path, 'JPEG', quality=90)
    return f'showcase/{filename}'


class Command(BaseCommand):
    help = 'Populate the shop with dummy products and placeholder images.'

    def handle(self, *args, **options):
        media_dir = Path(settings.MEDIA_ROOT) / 'showcase'
        media_dir.mkdir(parents=True, exist_ok=True)

        ShowcaseProduct.objects.all().delete()
        self.stdout.write('Cleared existing showcase products.')

        for i, p in enumerate(PRODUCTS):
            filename = f"product_{i + 1}.jpg"
            rel_path = make_placeholder(media_dir, filename, p['name'], p['category'])
            disc_price = round(p['price'] * (1 - p['discount'] / 100), 2) if p['discount'] > 0 else None
            ShowcaseProduct.objects.create(
                name=p['name'],
                category=p['category'],
                price=p['price'],
                discount_percent=p['discount'],
                discounted_price=disc_price,
                image=rel_path,
                display_order=i,
                is_active=True,
            )
            self.stdout.write(f"  ✓ {p['name']} ({p['category']})")

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {ShowcaseProduct.objects.count()} products created.'
        ))
