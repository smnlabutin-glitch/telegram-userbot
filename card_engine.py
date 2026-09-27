import io
import os
import sys
from functools import lru_cache
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

ASSETS_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# Color palette - Minimalist Architectural Dark Theme
COLOR_BG = (10, 12, 16)           # #0A0C10 - Pure deep obsidian canvas
COLOR_SURFACE = (16, 19, 26)      # #10131A - Elevated card surface
COLOR_BOX_BG = (12, 14, 19)       # #0C0E13 - Inset metric box surface
COLOR_BORDER = (32, 38, 50)       # #202632 - Hairline border
COLOR_BORDER_LIGHT = (45, 53, 70) # #2D3546 - Accent hairline border
COLOR_TEXT_WHITE = (244, 246, 250)# #F4F6FA - High-contrast crisp white
COLOR_TEXT_MUTED = (140, 149, 168)# #8C95A8 - Muted slate for secondary labels
COLOR_TEXT_DIM = (85, 94, 112)    # #555E70 - Subtle timestamps and technical IDs

# Badge color palettes (Background with alpha, Border, Text, Dot)
BADGE_THEMES = {
    "success": {
        "bg": (16, 185, 129, 28),     # #10B981 emerald
        "border": (16, 185, 129, 100),
        "text": (52, 211, 153),
        "dot": (16, 185, 129),
    },
    "info": {
        "bg": (59, 130, 246, 28),     # #3B82F6 blue
        "border": (59, 130, 246, 100),
        "text": (96, 165, 250),
        "dot": (59, 130, 246),
    },
    "running": {
        "bg": (168, 85, 247, 28),    # #A855F7 violet
        "border": (168, 85, 247, 100),
        "text": (192, 132, 252),
        "dot": (168, 85, 247),
    },
    "warn": {
        "bg": (245, 158, 11, 28),     # #F59E0B amber
        "border": (245, 158, 11, 100),
        "text": (251, 191, 36),
        "dot": (245, 158, 11),
    },
    "error": {
        "bg": (239, 68, 68, 28),      # #EF4444 rose
        "border": (239, 68, 68, 100),
        "text": (248, 113, 113),
        "dot": (239, 68, 68),
    },
}

@lru_cache(maxsize=16)
def _find_font(bold: bool = False, mono: bool = False) -> str:
    """Finds best available font, prioritizing bundled fonts in assets/fonts/."""
    # 1. Check bundled high-quality fonts first (ensures identical rendering everywhere)
    if mono:
        bundled = os.path.join(ASSETS_FONT_DIR, "RobotoMono-Regular.ttf")
    elif bold:
        bundled = os.path.join(ASSETS_FONT_DIR, "Roboto-Bold.ttf")
    else:
        bundled = os.path.join(ASSETS_FONT_DIR, "Roboto-Regular.ttf")

    if os.path.isfile(bundled):
        return bundled

    # 2. Fallback to system fonts
    candidates = []
    if sys.platform == "win32":
        if mono:
            candidates = [
                "C:/Windows/Fonts/consola.ttf",
                "C:/Windows/Fonts/cascadiacode.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        elif bold:
            candidates = [
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/calibrib.ttf",
            ]
        else:
            candidates = [
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ]
    elif sys.platform == "darwin":
        if mono:
            candidates = ["/System/Library/Fonts/Menlo.ttc"]
        elif bold:
            candidates = ["/System/Library/Fonts/SFPro-Bold.ttf", "/System/Library/Fonts/HelveticaNeue.ttc"]
        else:
            candidates = ["/System/Library/Fonts/SFPro-Regular.ttf", "/System/Library/Fonts/HelveticaNeue.ttc"]
    else:
        # Linux / VPS / Headless server
        if mono:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/roboto/RobotoMono-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
            ]
        elif bold:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
        else:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return ""

@lru_cache(maxsize=64)
def _load_font(font_path: str, size: int) -> ImageFont.ImageFont:
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    # Fallback to system fonts with Cyrillic support
    for f in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def render_card(
    title: str,
    subtitle: str,
    badge_text: str = "COMPLETED",
    badge_type: str = "success",
    stats: Optional[List[Tuple[str, str]]] = None,
    items: Optional[List[Tuple[str, str]]] = None,  # Optional list of key-value or bullet items (e.g. for help)
    meta_left: str = "TELEGRAM // ENGINE v1.0",
    meta_right: str = "SECURE SESSION",
    category: str = "USERBOT ACTION REPORT",
) -> io.BytesIO:
    """
    Renders a high-end, minimalist aesthetic status card.
    Uses 2x supersampling to ensure razor-sharp anti-aliased edges and typography.
    Returns in-memory BytesIO PNG image.
    """
    scale = 2
    target_width = 1040
    # Determine height based on whether we have items/commands list
    if items:
        target_height = 540 + min(len(items), 6) * 36
    elif stats:
        target_height = 460
    else:
        target_height = 360

    w = target_width * scale
    h = target_height * scale

    # Load system fonts
    font_bold_path = _find_font(bold=True)
    font_reg_path = _find_font(bold=False)
    font_mono_path = _find_font(mono=True)

    f_category = _load_font(font_bold_path, 12 * scale)
    f_badge = _load_font(font_bold_path, 12 * scale)
    f_title = _load_font(font_bold_path, 30 * scale)
    f_subtitle = _load_font(font_reg_path, 15 * scale)
    f_stat_label = _load_font(font_bold_path, 11 * scale)
    f_stat_val = _load_font(font_mono_path or font_bold_path, 21 * scale)
    f_item_key = _load_font(font_mono_path or font_bold_path, 14 * scale)
    f_item_val = _load_font(font_reg_path, 14 * scale)
    f_footer = _load_font(font_reg_path, 12 * scale)

    # 0. Base image: Load anime wallpaper or fallback to solid dark obsidian
    anime_bg_path = os.path.join(ASSETS_FONT_DIR, "..", "anime_bg.jpg")
    anime_bg_path = os.path.normpath(anime_bg_path)

    if os.path.isfile(anime_bg_path):
        try:
            with Image.open(anime_bg_path) as raw_bg:
                bg_w, bg_h = raw_bg.size
                ratio = max(w / bg_w, h / bg_h)
                new_w = int(bg_w * ratio)
                new_h = int(bg_h * ratio)
                resized_bg = raw_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - w) // 2
                top = (new_h - h) // 2
                img = resized_bg.crop((left, top, left + w, top + h)).convert("RGBA")
                resized_bg.close()
        except Exception:
            img = Image.new("RGBA", (w, h), COLOR_BG)
    else:
        img = Image.new("RGBA", (w, h), COLOR_BG)

    # Outer container with rounded corners and subtle border
    card_inset = 20 * scale
    card_rect = [card_inset, card_inset, w - card_inset, h - card_inset]
    card_radius = 18 * scale

    # Dark Frosted Glassmorphism card surface with alpha composite
    glass_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass_overlay)
    GLASS_SURFACE = (11, 14, 21, 222)   # Deep obsidian tinted glass (87% opacity)
    GLASS_BORDER = (75, 92, 125, 185)   # Subtle icy glowing border
    glass_draw.rounded_rectangle(card_rect, radius=card_radius, fill=GLASS_SURFACE, outline=GLASS_BORDER, width=2 * scale)

    # Decorative top accent hairline (subtle tinted segment)
    accent_theme = BADGE_THEMES.get(badge_type.lower(), BADGE_THEMES["info"])
    accent_bar_len = 150 * scale
    glass_draw.line(
        [(card_inset + card_radius, card_inset), (card_inset + card_radius + accent_bar_len, card_inset)],
        fill=accent_theme["dot"],
        width=3 * scale,
    )
    img = Image.alpha_composite(img, glass_overlay)
    glass_overlay.close()
    draw = ImageDraw.Draw(img)

    # Content margins
    content_x = card_inset + (34 * scale)
    content_y = card_inset + (30 * scale)
    content_right = w - card_inset - (34 * scale)

    # 1. Top row: Category tag + Status Pill
    draw.text((content_x, content_y + 4 * scale), category.upper(), font=f_category, fill=COLOR_TEXT_DIM)

    # Draw Status Pill on the right
    badge_label = badge_text.upper()
    bbox = f_badge.getbbox(badge_label)
    text_w = bbox[2] - bbox[0]
    pill_padding_x = 15 * scale
    pill_padding_y = 6 * scale
    dot_radius = 4 * scale
    dot_gap = 8 * scale
    pill_w = text_w + (dot_radius * 2) + dot_gap + (pill_padding_x * 2)
    pill_h = (bbox[3] - bbox[1]) + (pill_padding_y * 2)

    pill_x2 = content_right
    pill_x1 = pill_x2 - pill_w
    pill_y1 = content_y
    pill_y2 = pill_y1 + pill_h

    # Translucent pill background
    pill_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_overlay)
    pill_draw.rounded_rectangle(
        [pill_x1, pill_y1, pill_x2, pill_y2],
        radius=pill_h // 2,
        fill=accent_theme["bg"],
        outline=accent_theme["border"],
        width=1 * scale,
    )
    # Status indicator dot
    dot_center_x = pill_x1 + pill_padding_x + dot_radius
    dot_center_y = pill_y1 + (pill_h // 2)
    pill_draw.ellipse(
        [dot_center_x - dot_radius, dot_center_y - dot_radius, dot_center_x + dot_radius, dot_center_y + dot_radius],
        fill=accent_theme["dot"],
    )
    img = Image.alpha_composite(img, pill_overlay)
    draw = ImageDraw.Draw(img)

    # Draw badge text
    text_pos_x = dot_center_x + dot_radius + dot_gap
    text_pos_y = pill_y1 + pill_padding_y - bbox[1]
    draw.text((text_pos_x, text_pos_y), badge_label, font=f_badge, fill=accent_theme["text"])

    # 2. Main Title & Subtitle
    title_y = content_y + (36 * scale)
    draw.text((content_x, title_y), title, font=f_title, fill=COLOR_TEXT_WHITE)

    sub_y = title_y + (44 * scale)
    draw.text((content_x, sub_y), subtitle, font=f_subtitle, fill=COLOR_TEXT_MUTED)

    # Hairline divider
    divider_y = sub_y + (34 * scale)
    draw.line([(content_x, divider_y), (content_right, divider_y)], fill=COLOR_BORDER, width=1 * scale)

    # 3. Stats Grid
    curr_y = divider_y + (20 * scale)
    if stats:
        num_stats = len(stats)
        stat_cards_h = 92 * scale
        col_gap = 14 * scale
        total_gaps = col_gap * (num_stats - 1)
        card_width = (content_right - content_x - total_gaps) // num_stats

        for i, (label, val) in enumerate(stats):
            cx1 = content_x + i * (card_width + col_gap)
            cx2 = cx1 + card_width
            cy1 = curr_y
            cy2 = cy1 + stat_cards_h

            # Stat sub-card box
            draw.rounded_rectangle(
                [cx1, cy1, cx2, cy2],
                radius=10 * scale,
                fill=COLOR_BOX_BG,
                outline=COLOR_BORDER,
                width=1 * scale,
            )

            # Label
            draw.text(
                (cx1 + 16 * scale, cy1 + 14 * scale),
                label.upper(),
                font=f_stat_label,
                fill=COLOR_TEXT_DIM,
            )

            # Value
            val_str = str(val)
            draw.text(
                (cx1 + 16 * scale, cy1 + 38 * scale),
                val_str,
                font=f_stat_val,
                fill=COLOR_TEXT_WHITE,
            )
        curr_y += stat_cards_h + (18 * scale)

    # 4. Optional Items List (for help commands or details)
    if items:
        list_bg_y1 = curr_y
        list_bg_y2 = list_bg_y1 + (len(items) * 38 * scale) + (12 * scale)
        draw.rounded_rectangle(
            [content_x, list_bg_y1, content_right, list_bg_y2],
            radius=10 * scale,
            fill=COLOR_BOX_BG,
            outline=COLOR_BORDER,
            width=1 * scale,
        )
        for idx, (cmd_key, cmd_desc) in enumerate(items):
            iy = list_bg_y1 + (12 * scale) + (idx * 38 * scale)
            # draw command badge/key
            draw.text((content_x + 16 * scale, iy), cmd_key, font=f_item_key, fill=COLOR_TEXT_WHITE)
            # draw description
            draw.text((content_x + 220 * scale, iy), cmd_desc, font=f_item_val, fill=COLOR_TEXT_MUTED)

    # 5. Footer Bar
    footer_y = h - card_inset - (38 * scale)
    draw.line([(content_x, footer_y - (14 * scale)), (content_right, footer_y - (14 * scale))], fill=COLOR_BORDER, width=1 * scale)

    draw.text((content_x, footer_y), meta_left, font=f_footer, fill=COLOR_TEXT_DIM)

    if meta_right:
        bbox_r = f_footer.getbbox(meta_right)
        w_r = bbox_r[2] - bbox_r[0]
        draw.text((content_right - w_r, footer_y), meta_right, font=f_footer, fill=COLOR_TEXT_DIM)

    # 6. Downsample from 2x supersampled to 1x using high-quality Lanczos filter
    final_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    img.close()

    # Convert to RGB and save to in-memory BytesIO
    output = io.BytesIO()
    rgb_img = final_img.convert("RGB")
    final_img.close()
    rgb_img.save(output, format="PNG", optimize=True)
    rgb_img.close()

    output.seek(0)
    output.name = "report.png"
    return output
