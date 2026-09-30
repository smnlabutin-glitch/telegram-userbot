import io
import os
import sys
import math
from functools import lru_cache
from typing import List, Tuple, Optional, Dict
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

def render_quiz_card(
    frame_bytes: Optional[bytes],
    masked_hint: str,
    genres: str,
    year_season: str,
    title: str = "Угадай аниме по кадру",
    subtitle: str = "Внимательно изучите кадр и отправьте название тайтла в чат",
    badge_text: str = "45 СЕКУНД",
    badge_type: str = "running",
) -> io.BytesIO:
    """
    Renders an anime quiz question card with the anime screenshot frame embedded
    inside the dark frosted glass container, matching the userbot design aesthetic.
    Uses 2x supersampling for ultra-crisp output.
    """
    scale = 2
    target_width = 1040
    target_height = 800
    w = target_width * scale
    h = target_height * scale

    # Load system fonts
    font_bold_path = _find_font(bold=True)
    font_reg_path = _find_font(bold=False)
    font_mono_path = _find_font(mono=True)

    f_category = _load_font(font_bold_path, 12 * scale)
    f_badge = _load_font(font_bold_path, 12 * scale)
    f_title = _load_font(font_bold_path, 28 * scale)
    f_subtitle = _load_font(font_reg_path, 15 * scale)
    f_stat_label = _load_font(font_bold_path, 11 * scale)
    f_stat_val = _load_font(font_mono_path or font_bold_path, 17 * scale)
    f_stat_val_mono = _load_font(font_mono_path or font_bold_path, 20 * scale)
    f_footer = _load_font(font_reg_path, 12 * scale)

    # 0. Base wallpaper / dark background
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

    # Dark Frosted Glassmorphism card surface
    glass_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass_overlay)
    GLASS_SURFACE = (11, 14, 21, 230)
    GLASS_BORDER = (75, 92, 125, 185)
    glass_draw.rounded_rectangle(card_rect, radius=card_radius, fill=GLASS_SURFACE, outline=GLASS_BORDER, width=2 * scale)

    # Decorative top accent hairline
    accent_theme = BADGE_THEMES.get(badge_type.lower(), BADGE_THEMES["running"])
    accent_bar_len = 150 * scale
    glass_draw.line(
        [(card_inset + card_radius, card_inset), (card_inset + card_radius + accent_bar_len, card_inset)],
        fill=accent_theme["dot"],
        width=3 * scale,
    )
    img = Image.alpha_composite(img, glass_overlay)
    glass_overlay.close()
    draw = ImageDraw.Draw(img)

    content_x = card_inset + (34 * scale)
    content_y = card_inset + (30 * scale)
    content_right = w - card_inset - (34 * scale)

    # 1. Top row: Category tag + Status Pill
    draw.text((content_x, content_y + 4 * scale), "ANIME QUIZ // MINI-GAME", font=f_category, fill=COLOR_TEXT_DIM)

    # Badge pill on right
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

    pill_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_overlay)
    pill_draw.rounded_rectangle(
        [pill_x1, pill_y1, pill_x2, pill_y2],
        radius=pill_h // 2,
        fill=accent_theme["bg"],
        outline=accent_theme["border"],
        width=1 * scale,
    )
    dot_center_x = pill_x1 + pill_padding_x + dot_radius
    dot_center_y = pill_y1 + (pill_h // 2)
    pill_draw.ellipse(
        [dot_center_x - dot_radius, dot_center_y - dot_radius, dot_center_x + dot_radius, dot_center_y + dot_radius],
        fill=accent_theme["dot"],
    )
    img = Image.alpha_composite(img, pill_overlay)
    draw = ImageDraw.Draw(img)

    text_pos_x = dot_center_x + dot_radius + dot_gap
    text_pos_y = pill_y1 + pill_padding_y - bbox[1]
    draw.text((text_pos_x, text_pos_y), badge_label, font=f_badge, fill=accent_theme["text"])

    # 2. Main Title & Subtitle
    title_y = content_y + (36 * scale)
    draw.text((content_x, title_y), title, font=f_title, fill=COLOR_TEXT_WHITE)
    sub_y = title_y + (40 * scale)
    draw.text((content_x, sub_y), subtitle, font=f_subtitle, fill=COLOR_TEXT_MUTED)

    divider_y = sub_y + (30 * scale)
    draw.line([(content_x, divider_y), (content_right, divider_y)], fill=COLOR_BORDER, width=1 * scale)

    # 3. Center: Anime Frame Container with rounded corners & clean crop
    frame_x1 = content_x
    frame_x2 = content_right
    frame_y1 = divider_y + (16 * scale)
    frame_width = frame_x2 - frame_x1
    frame_height = 420 * scale  # 420px at 1x = 840px at 2x (classic 16:9 ratio)
    frame_y2 = frame_y1 + frame_height
    frame_radius = 12 * scale

    if frame_bytes:
        try:
            with Image.open(io.BytesIO(frame_bytes)) as raw_frame:
                rf = raw_frame.convert("RGBA")
                fw, fh = rf.size
                ratio = max(frame_width / fw, frame_height / fh)
                scaled_w = int(fw * ratio)
                scaled_h = int(fh * ratio)
                resized_frame = rf.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                rf.close()

                crop_x = (scaled_w - frame_width) // 2
                crop_y = (scaled_h - frame_height) // 2
                cropped_frame = resized_frame.crop((crop_x, crop_y, crop_x + frame_width, crop_y + frame_height))
                resized_frame.close()

                # Mask with rounded corners
                mask = Image.new("L", (frame_width, frame_height), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, frame_width, frame_height], radius=frame_radius, fill=255)

                img.paste(cropped_frame, (frame_x1, frame_y1), mask)
                cropped_frame.close()
                mask.close()
        except Exception as e:
            draw.rounded_rectangle([frame_x1, frame_y1, frame_x2, frame_y2], radius=frame_radius, fill=COLOR_BOX_BG)
            draw.text((frame_x1 + 30 * scale, frame_y1 + (frame_height // 2) - 10 * scale), "Ошибка отображения кадра", font=f_subtitle, fill=COLOR_TEXT_MUTED)
    else:
        draw.rounded_rectangle([frame_x1, frame_y1, frame_x2, frame_y2], radius=frame_radius, fill=COLOR_BOX_BG)

    # Hairline glowing border around the frame
    draw.rounded_rectangle(
        [frame_x1, frame_y1, frame_x2, frame_y2],
        radius=frame_radius,
        outline=COLOR_BORDER_LIGHT,
        width=2 * scale,
    )

    # 4. Stat Grid below frame (Hint, Genres, Release)
    curr_y = frame_y2 + (16 * scale)
    stat_cards_h = 76 * scale
    col_gap = 14 * scale

    stats_data = [
        ("ПОДСКАЗКА", masked_hint, True),
        ("ЖАНРЫ", genres, False),
        ("ГОД И СЕЗОН", year_season, False),
    ]

    total_w = content_right - content_x - (col_gap * 2)
    w_hint = int(total_w * 0.44)
    w_genre = int(total_w * 0.36)
    w_rel = total_w - w_hint - w_genre

    col_widths = [w_hint, w_genre, w_rel]
    cx = content_x
    for i, (label, val, is_mono) in enumerate(stats_data):
        cw = col_widths[i]
        cx1 = cx
        cx2 = cx1 + cw
        cy1 = curr_y
        cy2 = cy1 + stat_cards_h
        cx += cw + col_gap

        draw.rounded_rectangle(
            [cx1, cy1, cx2, cy2],
            radius=10 * scale,
            fill=COLOR_BOX_BG,
            outline=COLOR_BORDER,
            width=1 * scale,
        )

        draw.text((cx1 + 16 * scale, cy1 + 12 * scale), label, font=f_stat_label, fill=COLOR_TEXT_DIM)
        val_str = str(val)[:28]
        draw.text(
            (cx1 + 16 * scale, cy1 + 36 * scale),
            val_str,
            font=f_stat_val_mono if is_mono else f_stat_val,
            fill=COLOR_TEXT_WHITE,
        )

    # 5. Footer Bar
    footer_y = h - card_inset - (38 * scale)
    draw.line([(content_x, footer_y - (14 * scale)), (content_right, footer_y - (14 * scale))], fill=COLOR_BORDER, width=1 * scale)
    draw.text((content_x, footer_y), "ANIME TRIVIA ENGINE // REAL-TIME LISTENER", font=f_footer, fill=COLOR_TEXT_DIM)

    meta_r = "TIME LIMIT: 45s • TYPE IN CHAT"
    bbox_r = f_footer.getbbox(meta_r)
    w_r = bbox_r[2] - bbox_r[0]
    draw.text((content_right - w_r, footer_y), meta_r, font=f_footer, fill=COLOR_TEXT_DIM)

    # 6. Downsample 2x Lanczos -> 1x
    final_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    img.close()

    output = io.BytesIO()
    rgb_img = final_img.convert("RGB")
    final_img.close()
    rgb_img.save(output, format="PNG", optimize=True)
    rgb_img.close()

    output.seek(0)
    output.name = "anime_quiz_card.png"
    return output


ROLE_RU = {
    "mage": "МАГ",
    "assassin": "УБИЙЦА",
    "fighter": "БОЕЦ",
    "marksman": "СТРЕЛОК",
    "tank": "ТАНК",
    "support": "ПОДДЕРЖКА",
}

PLAYSTYLE_INFO = {
    "balanced": ("Balanced", "Универсальный стиль"),
    "support": ("Support", "Командная поддержка"),
    "assassin": ("Assassin", "Охотник за головами"),
    "marksman": ("Marksman", "Стрелок дальнего боя"),
    "mage": ("Mage", "Магический контроль"),
    "fighter": ("Fighter", "Контактный боец"),
    "tank": ("Tank", "Надёжный защитник"),
    "roamer": ("Roamer", "Активная ротация"),
    "jungler": ("Jungler", "Контроль объектов и леса"),
}

RANK_BADGE_THEMES = {
    1: {"bg": (245, 158, 11, 45), "border": (245, 158, 11, 160), "text": (251, 191, 36)},
    2: {"bg": (148, 163, 184, 45), "border": (148, 163, 184, 160), "text": (226, 232, 240)},
    3: {"bg": (217, 119, 6, 45), "border": (217, 119, 6, 160), "text": (245, 158, 11)},
}


RANK_ICONS_CONFIG = [
    {"key": "immortal", "file": "mythicalimmortal.png"},
    {"key": "glory", "file": "mythicalglory.png"},
    {"key": "honor", "file": "mythical_honor.png"},
    {"key": "mythic", "file": "mythic.png"},
    {"key": "legend", "file": "legend.png"},
    {"key": "epic", "file": "epic.png"},
    {"key": "grandmaster", "file": "grandmaster.png"},
    {"key": "master", "file": "master.png"},
    {"key": "elite", "file": "elite.png"},
    {"key": "warrior", "file": "warrior.png"},
]

def _get_rank_icon_path(rank_name: str, tier: str = "") -> Optional[str]:
    combined = f"{rank_name} {tier}".lower()
    for item in RANK_ICONS_CONFIG:
        if item["key"] in combined:
            p = os.path.join(ASSETS_FONT_DIR, "..", "ranks", item["file"])
            p = os.path.normpath(p)
            if os.path.isfile(p):
                return p
    return None

def _draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_out: float, fill: tuple, outline: tuple = None) -> None:
    points = []
    r_in = r_out * 0.42
    for i in range(10):
        angle = i * (math.pi / 5.0) - (math.pi / 2.0)
        r = r_out if i % 2 == 0 else r_in
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=outline)

def _plural_ru(n: int, one: str, two: str, five: str) -> str:
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        return five
    rem = n_abs % 10
    if rem == 1:
        return one
    if 2 <= rem <= 4:
        return two
    return five


def render_mlbb_card(
    player_data: dict,
    avatar_bytes: Optional[bytes] = None,
    hero_icons: Optional[Dict[str, bytes]] = None,
) -> io.BytesIO:
    """
    Renders an ultra-premium Mobile Legends: Bang Bang player dossier card.
    Includes:
    - Player header with current rank, peak rank, level, server, MVP
    - Key metrics: Winrate, Playstyle (Стиль игры), Current Season, Activity (Активность)
    - Top Heroes (Топ герои) podium with circular icons, roles, KDA, matches, winrate
    - Season history strip
    """
    scale = 2
    target_width = 1040
    target_height = 650
    w = target_width * scale
    h = target_height * scale

    if hero_icons is None:
        hero_icons = {}

    # Load typography
    font_bold_path = _find_font(bold=True)
    font_reg_path = _find_font(bold=False)
    font_mono_path = _find_font(mono=True)

    f_category = _load_font(font_bold_path, 12 * scale)
    f_badge = _load_font(font_bold_path, 12 * scale)
    f_badge_sm = _load_font(font_bold_path, 11 * scale)
    f_name = _load_font(font_bold_path, 28 * scale)
    f_meta = _load_font(font_reg_path, 13 * scale)
    f_meta_mono = _load_font(font_mono_path or font_bold_path, 13 * scale)
    f_stat_label = _load_font(font_bold_path, 11 * scale)
    f_stat_val = _load_font(font_bold_path, 20 * scale)
    f_stat_val_mono = _load_font(font_mono_path or font_bold_path, 20 * scale)
    f_stat_sub = _load_font(font_reg_path, 11 * scale)
    f_row_label = _load_font(font_bold_path, 13 * scale)
    f_row_val = _load_font(font_mono_path or font_bold_path, 13 * scale)
    f_footer = _load_font(font_reg_path, 12 * scale)

    f_hero_name = _load_font(font_bold_path, 15 * scale)
    f_hero_role = _load_font(font_bold_path, 10 * scale)
    f_hero_stat = _load_font(font_bold_path, 11 * scale)
    f_hero_wr = _load_font(font_bold_path, 20 * scale)
    f_hero_rank = _load_font(font_bold_path, 11 * scale)

    # Extract player properties
    name = str(player_data.get("name") or "Player").strip()
    role_id = str(player_data.get("roleId") or "")
    zone_id = str(player_data.get("zoneId") or "")
    level = str(player_data.get("level") or "—")

    # Current Rank
    rank_info = player_data.get("currentRank") or {}
    rank_name = rank_info.get("name") or "Unranked"
    rank_stars = rank_info.get("stars")
    tier = str(rank_info.get("tier") or "").lower()

    if rank_stars is not None and rank_stars > 0:
        rank_badge_text = f"{rank_name.upper()} • {rank_stars} STARS"
    else:
        rank_badge_text = rank_name.upper()

    # Determine badge theme based on rank tier
    if "immortal" in rank_name.lower() or "glory" in rank_name.lower():
        badge_type = "warn"
    elif "mythic" in rank_name.lower() or "myth" in tier:
        badge_type = "running"
    elif "legend" in rank_name.lower():
        badge_type = "info"
    else:
        badge_type = "success"

    # Peak Rank
    hist_rank = player_data.get("historyRank")
    if isinstance(hist_rank, dict):
        peak_rank_name = hist_rank.get("name") or rank_name
    elif isinstance(hist_rank, str) and hist_rank:
        peak_rank_name = hist_rank
    else:
        peak_rank_name = rank_name

    # Raw stats extraction
    raw_stats = player_data.get("stats")
    total_games = 0
    total_wins = 0
    total_mvps = 0
    ranked_seasons = []
    playstyle_raw = ""
    heroes_pool = []
    active_seasons_cnt = 0
    total_heroes_cnt = 0

    if isinstance(raw_stats, dict):
        total_games = raw_stats.get("totalGames") or 0
        total_wins = raw_stats.get("totalWins") or 0
        total_mvps = raw_stats.get("mvpCount") or 0
        direct_wr = raw_stats.get("winRate")
        if direct_wr is not None:
            overall_wr_str = f"{float(direct_wr):.1f}%"
        elif total_games > 0:
            overall_wr_str = f"{(total_wins / total_games) * 100:.1f}%"
        else:
            overall_wr_str = "—"

        playstyle_raw = raw_stats.get("playstyle") or ""
        heroes_pool = raw_stats.get("heroes") or []
        active_seasons_cnt = raw_stats.get("activeSeasons") or 0
        total_heroes_cnt = raw_stats.get("totalHeroesPlayed") or len(heroes_pool)

        seasons_pool = raw_stats.get("seasonSummaries") or []
        for entry in seasons_pool:
            if isinstance(entry, dict) and entry.get("mode") == 2 and entry.get("games", 0) > 0:
                ranked_seasons.append(entry)
    elif isinstance(raw_stats, list):
        for entry in raw_stats:
            if isinstance(entry, dict):
                games = entry.get("games", 0)
                wr = entry.get("winRate", 0.0)
                mvp = entry.get("mvp", 0)
                mode = entry.get("mode")

                total_games += games
                total_wins += round(games * (wr / 100.0))
                total_mvps += mvp

                if mode == 2 and games > 0:
                    ranked_seasons.append(entry)

        if total_games > 0:
            overall_wr = (total_wins / total_games) * 100.0
            overall_wr_str = f"{overall_wr:.1f}%"
        else:
            overall_wr_str = "—"
    else:
        overall_wr_str = "—"

    if not playstyle_raw:
        playstyle_raw = player_data.get("playstyle") or ""

    if not heroes_pool and isinstance(player_data.get("heroes"), list):
        heroes_pool = player_data.get("heroes")

    # If playstyle is empty, deduce from most played hero role
    if not playstyle_raw and heroes_pool:
        role_counts = {}
        for h_item in heroes_pool:
            r = (h_item.get("heroRole") or "").strip().lower()
            if r:
                role_counts[r] = role_counts.get(r, 0) + h_item.get("games", 0)
        if role_counts:
            playstyle_raw = max(role_counts.items(), key=lambda x: x[1])[0]

    # Resolve playstyle title and description
    p_info = PLAYSTYLE_INFO.get(playstyle_raw.lower())
    if p_info:
        style_title, style_desc = p_info
    elif playstyle_raw:
        style_title = playstyle_raw.capitalize()
        style_desc = "Индивидуальный стиль"
    else:
        style_title = "Balanced"
        style_desc = "Универсальный стиль"

    # Sort ranked seasons descending
    ranked_seasons.sort(key=lambda x: x.get("season", 0), reverse=True)

    if not active_seasons_cnt:
        active_seasons_cnt = len(ranked_seasons) if ranked_seasons else 1
    if not total_heroes_cnt:
        total_heroes_cnt = len(heroes_pool)

    # Current season info
    if ranked_seasons:
        latest = ranked_seasons[0]
        cur_season_num = latest.get("season", "")
        cur_season_games = latest.get("games", 0)
        cur_season_wr = latest.get("winRate", 0.0)
        cur_season_kda = latest.get("kda", 0.0)
        cur_season_mvp = latest.get("mvp", 0)
        cur_season_val = f"{cur_season_wr:.1f}% WR"
        cur_season_sub = f"{cur_season_games} игр · {cur_season_kda:.2f} KDA"
    else:
        cur_season_num = ""
        cur_season_val = "—"
        cur_season_sub = "Нет матчей"

    # Base background
    anime_bg_path = os.path.normpath(os.path.join(ASSETS_FONT_DIR, "..", "anime_bg.jpg"))
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

    # Outer container
    card_inset = 20 * scale
    card_rect = [card_inset, card_inset, w - card_inset, h - card_inset]
    card_radius = 18 * scale

    glass_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass_overlay)
    GLASS_SURFACE = (11, 14, 21, 235)
    GLASS_BORDER = (75, 92, 125, 185)
    glass_draw.rounded_rectangle(card_rect, radius=card_radius, fill=GLASS_SURFACE, outline=GLASS_BORDER, width=2 * scale)

    accent_theme = BADGE_THEMES.get(badge_type, BADGE_THEMES["warn"])
    accent_bar_len = 160 * scale
    glass_draw.line(
        [(card_inset + card_radius, card_inset), (card_inset + card_radius + accent_bar_len, card_inset)],
        fill=accent_theme["dot"],
        width=3 * scale,
    )
    img = Image.alpha_composite(img, glass_overlay)
    glass_overlay.close()
    draw = ImageDraw.Draw(img)

    content_x = card_inset + (34 * scale)
    content_y = card_inset + (26 * scale)
    content_right = w - card_inset - (34 * scale)

    # 1. Top row: Category tag + Status Pill
    draw.text((content_x, content_y + 4 * scale), "MOBILE LEGENDS // PLAYER DOSSIER", font=f_category, fill=COLOR_TEXT_DIM)

    # 1. Top Right: Rank Crest Icon + Stars Pill Below Icon
    rank_icon_path = _get_rank_icon_path(rank_name, tier)
    drawn_rank_icon = False

    if rank_icon_path and os.path.isfile(rank_icon_path):
        try:
            with Image.open(rank_icon_path) as raw_rank_icon:
                orig_w, orig_h = raw_rank_icon.size
                aspect = orig_w / orig_h
                icon_h = int(68 * scale)
                icon_w = int(icon_h * aspect)
                badge_center_x = content_right - (56 * scale)
                icon_x = badge_center_x - (icon_w // 2)
                icon_y = content_y + (2 * scale)

                resized_rank = raw_rank_icon.convert("RGBA").resize((icon_w, icon_h), Image.Resampling.LANCZOS)
                img.paste(resized_rank, (icon_x, icon_y), resized_rank)
                resized_rank.close()
                drawn_rank_icon = True

                # Stars or rank pill below the rank icon
                below_y = icon_y + icon_h + (3 * scale)
                p_pad_x = 9 * scale
                p_pad_y = 3 * scale

                if rank_stars is not None and rank_stars > 0:
                    num_str = str(rank_stars)
                    s_box = f_badge_sm.getbbox(num_str)
                    s_w = s_box[2] - s_box[0]
                    s_h = s_box[3] - s_box[1]
                    star_r = 5 * scale
                    star_gap = 5 * scale
                    inner_w = (star_r * 2) + star_gap + s_w
                    p_w = inner_w + (p_pad_x * 2)
                    p_h = max(s_h, int(star_r * 2)) + (p_pad_y * 2)
                    p_x1 = badge_center_x - (p_w // 2)
                    p_x2 = p_x1 + p_w
                    p_y1 = below_y
                    p_y2 = p_y1 + p_h

                    p_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    p_draw = ImageDraw.Draw(p_overlay)
                    p_draw.rounded_rectangle(
                        [p_x1, p_y1, p_x2, p_y2],
                        radius=p_h // 2,
                        fill=accent_theme["bg"],
                        outline=accent_theme["border"],
                        width=1 * scale,
                    )
                    # Vector crisp 5-pointed star
                    star_cx = p_x1 + p_pad_x + star_r
                    star_cy = p_y1 + (p_h // 2)
                    _draw_star(p_draw, star_cx, star_cy, star_r, fill=accent_theme["text"])
                    img = Image.alpha_composite(img, p_overlay)
                    p_overlay.close()
                    draw = ImageDraw.Draw(img)

                    # Star number
                    text_x = star_cx + star_r + star_gap - s_box[0]
                    text_y = p_y1 + p_pad_y - s_box[1]
                    draw.text((text_x, text_y), num_str, font=f_badge_sm, fill=accent_theme["text"])
                else:
                    star_label = rank_name.upper()
                    s_box = f_badge_sm.getbbox(star_label)
                    s_w = s_box[2] - s_box[0]
                    s_h = s_box[3] - s_box[1]
                    p_w = s_w + (p_pad_x * 2)
                    p_h = s_h + (p_pad_y * 2)
                    p_x1 = badge_center_x - (p_w // 2)
                    p_x2 = p_x1 + p_w
                    p_y1 = below_y
                    p_y2 = p_y1 + p_h

                    p_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    p_draw = ImageDraw.Draw(p_overlay)
                    p_draw.rounded_rectangle(
                        [p_x1, p_y1, p_x2, p_y2],
                        radius=p_h // 2,
                        fill=accent_theme["bg"],
                        outline=accent_theme["border"],
                        width=1 * scale,
                    )
                    img = Image.alpha_composite(img, p_overlay)
                    p_overlay.close()
                    draw = ImageDraw.Draw(img)

                    draw.text(
                        (p_x1 + p_pad_x - s_box[0], p_y1 + p_pad_y - s_box[1]),
                        star_label,
                        font=f_badge_sm,
                        fill=accent_theme["text"],
                    )
        except Exception:
            drawn_rank_icon = False

    if not drawn_rank_icon:
        bbox = f_badge.getbbox(rank_badge_text)
        text_w = bbox[2] - bbox[0]
        pill_padding_x = 16 * scale
        pill_padding_y = 6 * scale
        dot_radius = 4 * scale
        dot_gap = 8 * scale
        pill_w = text_w + (dot_radius * 2) + dot_gap + (pill_padding_x * 2)
        pill_h = (bbox[3] - bbox[1]) + (pill_padding_y * 2)

        pill_x2 = content_right
        pill_x1 = pill_x2 - pill_w
        pill_y1 = content_y
        pill_y2 = pill_y1 + pill_h

        pill_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pill_draw = ImageDraw.Draw(pill_overlay)
        pill_draw.rounded_rectangle(
            [pill_x1, pill_y1, pill_x2, pill_y2],
            radius=pill_h // 2,
            fill=accent_theme["bg"],
            outline=accent_theme["border"],
            width=1 * scale,
        )
        dot_center_x = pill_x1 + pill_padding_x + dot_radius
        dot_center_y = pill_y1 + (pill_h // 2)
        pill_draw.ellipse(
            [dot_center_x - dot_radius, dot_center_y - dot_radius, dot_center_x + dot_radius, dot_center_y + dot_radius],
            fill=accent_theme["dot"],
        )
        img = Image.alpha_composite(img, pill_overlay)
        draw = ImageDraw.Draw(img)

        text_pos_x = dot_center_x + dot_radius + dot_gap
        text_pos_y = pill_y1 + pill_padding_y - bbox[1]
        draw.text((text_pos_x, text_pos_y), rank_badge_text, font=f_badge, fill=accent_theme["text"])

    # 2. Header Area: Avatar + Name + Meta
    header_y = content_y + (36 * scale)
    avatar_size = 80 * scale
    avatar_rect = [content_x, header_y, content_x + avatar_size, header_y + avatar_size]
    avatar_radius = 16 * scale

    if avatar_bytes:
        try:
            with Image.open(io.BytesIO(avatar_bytes)) as raw_av:
                av_rgba = raw_av.convert("RGBA")
                av_resized = av_rgba.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                av_rgba.close()

                mask = Image.new("L", (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, avatar_size, avatar_size], radius=avatar_radius, fill=255)

                img.paste(av_resized, (content_x, header_y), mask)
                av_resized.close()
                mask.close()
        except Exception:
            draw.rounded_rectangle(avatar_rect, radius=avatar_radius, fill=COLOR_BOX_BG)
    else:
        draw.rounded_rectangle(avatar_rect, radius=avatar_radius, fill=COLOR_BOX_BG)
        initial = (name[0] if name else "M").upper()
        f_init = _load_font(font_bold_path, 34 * scale)
        ibox = f_init.getbbox(initial)
        iw = ibox[2] - ibox[0]
        ih = ibox[3] - ibox[1]
        draw.text(
            (content_x + (avatar_size - iw) // 2 - ibox[0], header_y + (avatar_size - ih) // 2 - ibox[1]),
            initial,
            font=f_init,
            fill=accent_theme["dot"],
        )

    draw.rounded_rectangle(avatar_rect, radius=avatar_radius, outline=COLOR_BORDER_LIGHT, width=2 * scale)

    # Name and Meta next to avatar
    text_info_x = content_x + avatar_size + (20 * scale)
    name_y = header_y + (2 * scale)
    draw.text((text_info_x, name_y), name, font=f_name, fill=COLOR_TEXT_WHITE)

    # Playstyle pill tag next to player name
    tag_str = style_title.upper()
    name_bbox = f_name.getbbox(name)
    nw = name_bbox[2] - name_bbox[0]
    tag_x = text_info_x + nw + (14 * scale)
    t_box = f_badge_sm.getbbox(tag_str)
    t_w = t_box[2] - t_box[0]
    t_h = t_box[3] - t_box[1]
    t_pad_x = 10 * scale
    t_pad_y = 4 * scale
    t_pw = t_w + (t_pad_x * 2)
    t_ph = t_h + (t_pad_y * 2)
    t_py = name_y + (28 * scale - t_ph) // 2

    tag_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tag_draw = ImageDraw.Draw(tag_overlay)
    tag_draw.rounded_rectangle(
        [tag_x, t_py, tag_x + t_pw, t_py + t_ph],
        radius=t_ph // 2,
        fill=BADGE_THEMES["info"]["bg"],
        outline=BADGE_THEMES["info"]["border"],
        width=1 * scale,
    )
    img = Image.alpha_composite(img, tag_overlay)
    tag_overlay.close()
    draw = ImageDraw.Draw(img)
    draw.text((tag_x + t_pad_x - t_box[0], t_py + t_pad_y - t_box[1]), tag_str, font=f_badge_sm, fill=BADGE_THEMES["info"]["text"])

    meta_y1 = name_y + (34 * scale)
    id_str = f"ID: {role_id} ({zone_id})" if role_id and zone_id else f"ID: {role_id}"
    meta_line1 = f"{id_str}   •   LEVEL {level}   •   SERVER CIS / GLOBAL"
    draw.text((text_info_x, meta_y1), meta_line1, font=f_meta_mono, fill=COLOR_TEXT_MUTED)

    meta_y2 = meta_y1 + (20 * scale)
    meta_line2 = f"ПИКОВЫЙ РАНГ: {peak_rank_name.upper()}   •   НАГРАДЫ MVP: {total_mvps:,}"
    draw.text((text_info_x, meta_y2), meta_line2, font=f_meta, fill=COLOR_TEXT_DIM)

    # Hairline divider
    divider_y = header_y + avatar_size + (18 * scale)
    draw.line([(content_x, divider_y), (content_right, divider_y)], fill=COLOR_BORDER, width=1 * scale)

    # 3. Main Stats Grid (4 Metric Boxes):
    # Box 1: ОБЩИЙ ВИНРЕЙТ
    # Box 2: СТИЛЬ ИГРЫ (with subtitle description)
    # Box 3: СЕЗОН (RANKED)
    # Box 4: АКТИВНОСТЬ (with played heroes count)
    curr_y = divider_y + (16 * scale)
    stat_cards_h = 78 * scale
    col_gap = 14 * scale

    seasons_plural = _plural_ru(active_seasons_cnt, "сезон", "сезона", "сезонов")
    heroes_plural = _plural_ru(total_heroes_cnt, "герой сыгран", "героя сыграно", "героев сыграно")

    grid_stats = [
        (
            "ОБЩИЙ ВИНРЕЙТ",
            overall_wr_str,
            f"{total_games:,} игр всего" if total_games else "—",
            BADGE_THEMES["success"]["text"] if overall_wr_str != "—" and float(overall_wr_str.rstrip("%")) >= 55 else COLOR_TEXT_WHITE,
        ),
        (
            "СТИЛЬ ИГРЫ",
            style_title,
            style_desc,
            BADGE_THEMES["warn"]["text"],
        ),
        (
            f"СЕЗОН {cur_season_num} (RANKED)",
            cur_season_val,
            cur_season_sub,
            accent_theme["text"],
        ),
        (
            "АКТИВНОСТЬ",
            f"{active_seasons_cnt} {seasons_plural}",
            f"{total_heroes_cnt} {heroes_plural}",
            COLOR_TEXT_WHITE,
        ),
    ]

    total_gaps = col_gap * (len(grid_stats) - 1)
    card_width = (content_right - content_x - total_gaps) // len(grid_stats)

    for i, (label, val, sub_val, val_color) in enumerate(grid_stats):
        cx1 = content_x + i * (card_width + col_gap)
        cx2 = cx1 + card_width
        cy1 = curr_y
        cy2 = cy1 + stat_cards_h

        draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=10 * scale, fill=COLOR_BOX_BG, outline=COLOR_BORDER, width=1 * scale)
        draw.text((cx1 + 16 * scale, cy1 + 10 * scale), label, font=f_stat_label, fill=COLOR_TEXT_DIM)
        draw.text((cx1 + 16 * scale, cy1 + 28 * scale), str(val), font=f_stat_val if label in ('СТИЛЬ ИГРЫ', 'АКТИВНОСТЬ') else f_stat_val_mono, fill=val_color)
        draw.text((cx1 + 16 * scale, cy1 + 54 * scale), str(sub_val), font=f_stat_sub, fill=COLOR_TEXT_MUTED)

    curr_y += stat_cards_h + (18 * scale)

    # 4. Top Heroes Section (Podium layout like the website)
    valid_heroes = [h_entry for h_entry in heroes_pool if isinstance(h_entry, dict) and h_entry.get("games", 0) > 0]
    valid_heroes.sort(key=lambda x: x.get("games", 0), reverse=True)
    top_3 = valid_heroes[:3]

    if len(top_3) == 3:
        podium_heroes = [(top_3[1], 2), (top_3[0], 1), (top_3[2], 3)]
    elif len(top_3) == 2:
        podium_heroes = [(top_3[0], 1), (top_3[1], 2)]
    elif len(top_3) == 1:
        podium_heroes = [(top_3[0], 1)]
    else:
        podium_heroes = []

    if podium_heroes:
        draw.text((content_x + 2 * scale, curr_y), "ТОП ГЕРОИ", font=f_stat_label, fill=COLOR_TEXT_WHITE)
        heroes_total_label = f"ВСЕ ГЕРОИ ({len(heroes_pool)}) >" if heroes_pool else "ВСЕ ГЕРОИ >"
        h_bbox = f_stat_label.getbbox(heroes_total_label)
        draw.text((content_right - (h_bbox[2] - h_bbox[0]), curr_y), heroes_total_label, font=f_stat_label, fill=BADGE_THEMES["info"]["text"])

        curr_y += 18 * scale

        hero_card_h = 76 * scale
        h_gaps = col_gap * (len(podium_heroes) - 1)
        h_card_w = (content_right - content_x - h_gaps) // len(podium_heroes)

        for idx, (h_data, rank_num) in enumerate(podium_heroes):
            hx1 = content_x + idx * (h_card_w + col_gap)
            hx2 = hx1 + h_card_w
            hy1 = curr_y
            hy2 = hy1 + hero_card_h

            badge_style = RANK_BADGE_THEMES.get(rank_num, RANK_BADGE_THEMES[2])

            # Hero card container
            draw.rounded_rectangle([hx1, hy1, hx2, hy2], radius=10 * scale, fill=COLOR_BOX_BG, outline=COLOR_BORDER, width=1 * scale)

            # Rank number pill (top right)
            rw = 18 * scale
            rh = 18 * scale
            rx2 = hx2 - 12 * scale
            ry1 = hy1 + 10 * scale
            rx1 = rx2 - rw
            ry2 = ry1 + rh

            r_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            r_draw = ImageDraw.Draw(r_overlay)
            r_draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=4 * scale, fill=badge_style["bg"], outline=badge_style["border"], width=1 * scale)
            img = Image.alpha_composite(img, r_overlay)
            r_overlay.close()
            draw = ImageDraw.Draw(img)

            r_text = str(rank_num)
            rbox = f_hero_rank.getbbox(r_text)
            draw.text((rx1 + (rw - (rbox[2] - rbox[0])) // 2 - rbox[0], ry1 + (rh - (rbox[3] - rbox[1])) // 2 - rbox[1]), r_text, font=f_hero_rank, fill=badge_style["text"])

            # Circular hero avatar
            av_dia = 50 * scale
            av_x = hx1 + 12 * scale
            av_y = hy1 + (hero_card_h - av_dia) // 2
            av_rect = [av_x, av_y, av_x + av_dia, av_y + av_dia]

            hero_icon_path = h_data.get("heroIcon") or ""
            icon_bytes = hero_icons.get(hero_icon_path) or hero_icons.get(str(h_data.get("heroId")))

            if icon_bytes:
                try:
                    with Image.open(io.BytesIO(icon_bytes)) as raw_icon:
                        icon_rgba = raw_icon.convert("RGBA")
                        icon_resized = icon_rgba.resize((av_dia, av_dia), Image.Resampling.LANCZOS)
                        icon_rgba.close()

                        c_mask = Image.new("L", (av_dia, av_dia), 0)
                        c_draw = ImageDraw.Draw(c_mask)
                        c_draw.ellipse([0, 0, av_dia, av_dia], fill=255)

                        img.paste(icon_resized, (av_x, av_y), c_mask)
                        icon_resized.close()
                        c_mask.close()
                except Exception:
                    draw.ellipse(av_rect, fill=(22, 27, 36))
            else:
                draw.ellipse(av_rect, fill=(22, 27, 36))
                h_name_initial = (h_data.get("heroNameRu") or h_data.get("heroName") or "H")[0].upper()
                f_hi = _load_font(font_bold_path, 20 * scale)
                hib = f_hi.getbbox(h_name_initial)
                draw.text(
                    (av_x + (av_dia - (hib[2] - hib[0])) // 2 - hib[0], av_y + (av_dia - (hib[3] - hib[1])) // 2 - hib[1]),
                    h_name_initial,
                    font=f_hi,
                    fill=badge_style["text"],
                )

            # Circular hairline border
            draw.ellipse(av_rect, outline=badge_style["border"], width=1 * scale)

            # Hero info
            info_x = av_x + av_dia + 12 * scale
            ru_name = h_data.get("heroNameRu")
            if ru_name and "\ufffd" not in ru_name and len(ru_name.strip()) > 1:
                hero_name = ru_name.strip()
            else:
                hero_name = str(h_data.get("heroName") or "Hero").strip()

            hero_role_raw = str(h_data.get("heroRole") or "").lower()
            hero_role = ROLE_RU.get(hero_role_raw, hero_role_raw.upper()) if hero_role_raw else "ГЕРОЙ"
            hero_games = h_data.get("games", 0)
            hero_kda = h_data.get("kda", 0.0)
            hero_wr = h_data.get("winRate", 0.0)

            # Hero Name
            draw.text((info_x, hy1 + 10 * scale), hero_name, font=f_hero_name, fill=COLOR_TEXT_WHITE)

            # Role
            draw.text((info_x, hy1 + 30 * scale), hero_role, font=f_hero_role, fill=COLOR_TEXT_DIM)

            # Stat line: "{kda:.2f} KDA · {games} игр"
            kda_color = BADGE_THEMES["success"]["text"] if hero_kda >= 4.0 else (BADGE_THEMES["warn"]["text"] if hero_kda >= 3.0 else COLOR_TEXT_WHITE)
            kda_str = f"{hero_kda:.2f}"
            draw.text((info_x, hy1 + 47 * scale), kda_str, font=f_hero_stat, fill=kda_color)
            kbox = f_hero_stat.getbbox(kda_str)
            kda_w = kbox[2] - kbox[0]
            draw.text((info_x + kda_w + 4 * scale, hy1 + 47 * scale), f"KDA · {hero_games} игр", font=f_hero_stat, fill=COLOR_TEXT_MUTED)

            # Win Rate on right side
            wr_str = f"{hero_wr:.1f}%" if not float(hero_wr).is_integer() else f"{int(hero_wr)}%"
            wbox = f_hero_wr.getbbox(wr_str)
            ww = wbox[2] - wbox[0]
            wh = wbox[3] - wbox[1]
            wr_x = hx2 - 16 * scale - ww
            wr_y = hy1 + (hero_card_h - wh) // 2 + 3 * scale
            draw.text((wr_x, wr_y), wr_str, font=f_hero_wr, fill=COLOR_TEXT_WHITE)

        curr_y += hero_card_h + (18 * scale)

    # 5. Ranked Seasons History Strip (Last 3 ranked seasons)
    hist_box_h = 136 * scale
    draw.rounded_rectangle(
        [content_x, curr_y, content_right, curr_y + hist_box_h],
        radius=10 * scale,
        fill=COLOR_BOX_BG,
        outline=COLOR_BORDER,
        width=1 * scale,
    )

    draw.text((content_x + 18 * scale, curr_y + 12 * scale), "ИСТОРИЯ ПОСЛЕДНИХ СЕЗОНОВ // RANKED MATCHES", font=f_stat_label, fill=COLOR_TEXT_DIM)

    sample_seasons = ranked_seasons[:3]
    if sample_seasons:
        row_y = curr_y + (34 * scale)
        for s_idx, s_data in enumerate(sample_seasons):
            s_num = s_data.get("season", "")
            s_games = s_data.get("games", 0)
            s_wr = s_data.get("winRate", 0.0)
            s_kda = s_data.get("kda", 0.0)
            s_mvp = s_data.get("mvp", 0)

            col1 = f"СЕЗОН {s_num}"
            col2 = f"{s_games} МАТЧЕЙ"
            col3 = f"WIN RATE: {s_wr:.1f}%"
            col4 = f"KDA: {s_kda:.2f}"
            col5 = f"MVP: {s_mvp}"

            draw.text((content_x + 18 * scale, row_y), col1, font=f_row_label, fill=COLOR_TEXT_WHITE)
            draw.text((content_x + 180 * scale, row_y), col2, font=f_row_val, fill=COLOR_TEXT_MUTED)
            draw.text((content_x + 380 * scale, row_y), col3, font=f_row_val, fill=BADGE_THEMES["success"]["text"] if s_wr >= 55 else COLOR_TEXT_WHITE)
            draw.text((content_x + 590 * scale, row_y), col4, font=f_row_val, fill=COLOR_TEXT_MUTED)
            draw.text((content_x + 780 * scale, row_y), col5, font=f_row_val, fill=accent_theme["text"])

            row_y += 30 * scale
    else:
        draw.text(
            (content_x + 18 * scale, curr_y + 50 * scale),
            "Подробная история матчей отсутствует или скрыта в настройках приватности",
            font=f_meta,
            fill=COLOR_TEXT_MUTED,
        )

    # 6. Footer Bar
    footer_y = h - card_inset - (34 * scale)
    draw.line([(content_x, footer_y - (12 * scale)), (content_right, footer_y - (12 * scale))], fill=COLOR_BORDER, width=1 * scale)
    draw.text((content_x, footer_y), "MLBB TELEMETRY ENGINE // USERBOT v1.0", font=f_footer, fill=COLOR_TEXT_DIM)

    meta_r = "REAL-TIME SYNCED • DATA VERIFIED"
    bbox_r = f_footer.getbbox(meta_r)
    w_r = bbox_r[2] - bbox_r[0]
    draw.text((content_right - w_r, footer_y), meta_r, font=f_footer, fill=COLOR_TEXT_DIM)

    # Downsample 2x Lanczos -> 1x
    final_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    img.close()

    output = io.BytesIO()
    rgb_img = final_img.convert("RGB")
    final_img.close()
    rgb_img.save(output, format="PNG", optimize=True)
    rgb_img.close()

    output.seek(0)
    output.name = "mlbb_card.png"
    return output


def render_profile_card(
    user_id: int,
    name: str,
    username: str,
    user_type: str,
    reg_date: str,
    country_region: str,
    dc_str: str,
    chat_id: str,
    avatar_bytes: io.BytesIO = None,
    items: list = None,
    badge_type: str = "info",
    category: str = "TELEGRAM // USER DOSSIER",
) -> io.BytesIO:
    scale = 2
    target_width = 1040
    target_height = 620
    w = target_width * scale
    h = target_height * scale

    # Load fonts
    font_bold_path = _find_font(bold=True)
    font_reg_path = _find_font(bold=False)
    font_mono_path = _find_font(mono=True)

    f_category = _load_font(font_bold_path, 12 * scale)
    f_badge = _load_font(font_bold_path, 12 * scale)
    f_badge_sm = _load_font(font_bold_path, 11 * scale)
    f_name = _load_font(font_bold_path, 30 * scale)
    f_meta = _load_font(font_reg_path, 13 * scale)
    f_meta_mono = _load_font(font_mono_path or font_bold_path, 13 * scale)
    f_stat_label = _load_font(font_bold_path, 11 * scale)
    f_stat_val = _load_font(font_bold_path, 20 * scale)
    f_stat_val_mono = _load_font(font_mono_path or font_bold_path, 20 * scale)
    f_stat_sub = _load_font(font_reg_path, 11 * scale)
    f_row_label = _load_font(font_bold_path, 13 * scale)
    f_row_val = _load_font(font_mono_path or font_bold_path, 13 * scale)
    f_footer = _load_font(font_reg_path, 12 * scale)

    # Base background
    anime_bg_path = os.path.normpath(os.path.join(ASSETS_FONT_DIR, "..", "anime_bg.jpg"))
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

    card_inset = 20 * scale
    card_rect = [card_inset, card_inset, w - card_inset, h - card_inset]
    card_radius = 18 * scale

    glass_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass_overlay)
    GLASS_SURFACE = (11, 14, 21, 235)
    GLASS_BORDER = (75, 92, 125, 185)
    glass_draw.rounded_rectangle(card_rect, radius=card_radius, fill=GLASS_SURFACE, outline=GLASS_BORDER, width=2 * scale)

    accent_theme = BADGE_THEMES.get(badge_type, BADGE_THEMES["info"])
    accent_bar_len = 160 * scale
    glass_draw.line(
        [(card_inset + card_radius, card_inset), (card_inset + card_radius + accent_bar_len, card_inset)],
        fill=accent_theme["dot"],
        width=3 * scale,
    )
    img = Image.alpha_composite(img, glass_overlay)
    glass_overlay.close()
    draw = ImageDraw.Draw(img)

    content_x = card_inset + (34 * scale)
    content_y = card_inset + (26 * scale)
    content_right = w - card_inset - (34 * scale)

    # 1. Top row: Category tag + Status Pill
    draw.text((content_x, content_y + 4 * scale), category, font=f_category, fill=COLOR_TEXT_DIM)

    # Status Pill on right
    badge_label = user_type.upper()
    bbox = f_badge.getbbox(badge_label)
    text_w = bbox[2] - bbox[0]
    pill_padding_x = 16 * scale
    pill_padding_y = 6 * scale
    dot_radius = 4 * scale
    dot_gap = 8 * scale
    pill_w = text_w + (dot_radius * 2) + dot_gap + (pill_padding_x * 2)
    pill_h = (bbox[3] - bbox[1]) + (pill_padding_y * 2)

    pill_x2 = content_right
    pill_x1 = pill_x2 - pill_w
    pill_y1 = content_y
    pill_y2 = pill_y1 + pill_h

    pill_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_overlay)
    pill_draw.rounded_rectangle(
        [pill_x1, pill_y1, pill_x2, pill_y2],
        radius=pill_h // 2,
        fill=accent_theme["bg"],
        outline=accent_theme["border"],
        width=1 * scale,
    )
    dot_center_x = pill_x1 + pill_padding_x + dot_radius
    dot_center_y = pill_y1 + (pill_h // 2)
    pill_draw.ellipse(
        [dot_center_x - dot_radius, dot_center_y - dot_radius, dot_center_x + dot_radius, dot_center_y + dot_radius],
        fill=accent_theme["dot"],
    )
    img = Image.alpha_composite(img, pill_overlay)
    draw = ImageDraw.Draw(img)

    text_pos_x = dot_center_x + dot_radius + dot_gap
    text_pos_y = pill_y1 + pill_padding_y - bbox[1]
    draw.text((text_pos_x, text_pos_y), badge_label, font=f_badge, fill=accent_theme["text"])

    # 2. Header Area: Avatar + Name + Meta
    header_y = content_y + (36 * scale)
    avatar_size = 80 * scale
    avatar_rect = [content_x, header_y, content_x + avatar_size, header_y + avatar_size]
    avatar_radius = 16 * scale

    if avatar_bytes:
        try:
            with Image.open(io.BytesIO(avatar_bytes) if isinstance(avatar_bytes, bytes) else avatar_bytes) as raw_av:
                av_rgba = raw_av.convert("RGBA")
                av_resized = av_rgba.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                av_rgba.close()

                mask = Image.new("L", (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, avatar_size, avatar_size], radius=avatar_radius, fill=255)

                img.paste(av_resized, (content_x, header_y), mask)
                av_resized.close()
                mask.close()
        except Exception:
            draw.rounded_rectangle(avatar_rect, radius=avatar_radius, fill=COLOR_BOX_BG)
    else:
        draw.rounded_rectangle(avatar_rect, radius=avatar_radius, fill=COLOR_BOX_BG)
        initial = (name[0] if name else "U").upper()
        f_init = _load_font(font_bold_path, 34 * scale)
        ibox = f_init.getbbox(initial)
        iw = ibox[2] - ibox[0]
        ih = ibox[3] - ibox[1]
        draw.text(
            (content_x + (avatar_size - iw) // 2 - ibox[0], header_y + (avatar_size - ih) // 2 - ibox[1]),
            initial,
            font=f_init,
            fill=accent_theme["dot"],
        )

    draw.rounded_rectangle(avatar_rect, radius=avatar_radius, outline=COLOR_BORDER_LIGHT, width=2 * scale)

    # Name and Meta next to avatar
    text_info_x = content_x + avatar_size + (20 * scale)
    name_y = header_y + (2 * scale)
    draw.text((text_info_x, name_y), name, font=f_name, fill=COLOR_TEXT_WHITE)

    # Username tag next to name if present
    if username and username != "—":
        name_bbox = f_name.getbbox(name)
        nw = name_bbox[2] - name_bbox[0]
        tag_x = text_info_x + nw + (14 * scale)
        tag_str = username.upper()
        t_box = f_badge_sm.getbbox(tag_str)
        t_w = t_box[2] - t_box[0]
        t_h = t_box[3] - t_box[1]
        t_pad_x = 10 * scale
        t_pad_y = 4 * scale
        t_pw = t_w + (t_pad_x * 2)
        t_ph = t_h + (t_pad_y * 2)
        t_py = name_y + (28 * scale - t_ph) // 2

        tag_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        tag_draw = ImageDraw.Draw(tag_overlay)
        tag_draw.rounded_rectangle(
            [tag_x, t_py, tag_x + t_pw, t_py + t_ph],
            radius=t_ph // 2,
            fill=BADGE_THEMES["info"]["bg"],
            outline=BADGE_THEMES["info"]["border"],
            width=1 * scale,
        )
        img = Image.alpha_composite(img, tag_overlay)
        tag_overlay.close()
        draw = ImageDraw.Draw(img)
        draw.text((tag_x + t_pad_x - t_box[0], t_py + t_pad_y - t_box[1]), tag_str, font=f_badge_sm, fill=BADGE_THEMES["info"]["text"])

    meta_y1 = name_y + (34 * scale)
    meta_line1 = f"ID: {user_id}   •   {dc_str}   •   STATUS: {user_type.upper()}"
    draw.text((text_info_x, meta_y1), meta_line1, font=f_meta_mono, fill=COLOR_TEXT_MUTED)

    meta_y2 = meta_y1 + (20 * scale)
    meta_line2 = f"РЕГИСТРАЦИЯ: {reg_date.upper()}   •   РЕГИОН: {country_region.upper()}"
    draw.text((text_info_x, meta_y2), meta_line2, font=f_meta, fill=COLOR_TEXT_DIM)

    # Hairline divider
    divider_y = header_y + avatar_size + (18 * scale)
    draw.line([(content_x, divider_y), (content_right, divider_y)], fill=COLOR_BORDER, width=1 * scale)

    # 3. Main Stats Grid (4 Metric Boxes)
    curr_y = divider_y + (16 * scale)
    stat_cards_h = 78 * scale
    col_gap = 14 * scale

    grid_stats = [
        ("TELEGRAM ID", str(user_id), "Уникальный номер", COLOR_TEXT_WHITE),
        ("РЕГИСТРАЦИЯ", reg_date, "Примерная дата", BADGE_THEMES["warn"]["text"]),
        ("РЕГИОН АККАУНТА", country_region, dc_str, COLOR_TEXT_WHITE),
        ("ТЕКУЩИЙ ЧАТ", str(chat_id), "Идентификатор чата", COLOR_TEXT_MUTED),
    ]

    total_gaps = col_gap * (len(grid_stats) - 1)
    card_width = (content_right - content_x - total_gaps) // len(grid_stats)

    for i, (label, val, sub_val, val_color) in enumerate(grid_stats):
        cx1 = content_x + i * (card_width + col_gap)
        cx2 = cx1 + card_width
        cy1 = curr_y
        cy2 = cy1 + stat_cards_h

        draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=10 * scale, fill=COLOR_BOX_BG, outline=COLOR_BORDER, width=1 * scale)
        draw.text((cx1 + 16 * scale, cy1 + 10 * scale), label, font=f_stat_label, fill=COLOR_TEXT_DIM)
        draw.text((cx1 + 16 * scale, cy1 + 28 * scale), str(val), font=f_stat_val if label in ("РЕГИСТРАЦИЯ", "РЕГИОН АККАУНТА") else f_stat_val_mono, fill=val_color)
        draw.text((cx1 + 16 * scale, cy1 + 54 * scale), str(sub_val), font=f_stat_sub, fill=COLOR_TEXT_MUTED)

    curr_y += stat_cards_h + (18 * scale)

    # 4. Detailed Info Strip (Items)
    if items:
        info_box_h = 138 * scale
        draw.rounded_rectangle(
            [content_x, curr_y, content_right, curr_y + info_box_h],
            radius=10 * scale,
            fill=COLOR_BOX_BG,
            outline=COLOR_BORDER,
            width=1 * scale,
        )

        draw.text((content_x + 18 * scale, curr_y + 14 * scale), "ДЕТАЛЬНАЯ ИНФОРМАЦИЯ // PROFILE ATTRIBUTES", font=f_stat_label, fill=COLOR_TEXT_DIM)

        row_y = curr_y + (38 * scale)
        for key, value in items[:3]:
            draw.text((content_x + 18 * scale, row_y), key, font=f_row_label, fill=COLOR_TEXT_WHITE)
            draw.text((content_x + 280 * scale, row_y), value, font=f_row_val, fill=COLOR_TEXT_MUTED)
            row_y += 30 * scale

    # 5. Footer Bar
    footer_y = h - card_inset - (26 * scale)
    draw.line([(content_x, footer_y - (12 * scale)), (content_right, footer_y - (12 * scale))], fill=COLOR_BORDER, width=1 * scale)
    draw.text((content_x, footer_y), "TELEGRAM IDENTITY ENGINE // USERBOT v1.0", font=f_footer, fill=COLOR_TEXT_DIM)

    meta_r = "PEER RESOLVED • REAL-TIME MTPROTO"
    bbox_r = f_footer.getbbox(meta_r)
    w_r = bbox_r[2] - bbox_r[0]
    draw.text((content_right - w_r, footer_y), meta_r, font=f_footer, fill=COLOR_TEXT_DIM)

    final_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    img.close()

    output = io.BytesIO()
    rgb_img = final_img.convert("RGB")
    final_img.close()
    rgb_img.save(output, format="PNG", optimize=True)
    rgb_img.close()

    output.seek(0)
    output.name = "telegram_profile_card.png"
    return output
