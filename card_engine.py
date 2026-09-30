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


def render_mlbb_card(
    player_data: dict,
    avatar_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    """
    Renders an ultra-premium Mobile Legends: Bang Bang player dossier card.
    Uses Frosted Glassmorphism, 2x supersampling and Lanczos downsampling.
    Matches the exact architectural dark theme of the Telegram userbot.
    """
    scale = 2
    target_width = 1040
    target_height = 680
    w = target_width * scale
    h = target_height * scale

    # Load typography
    font_bold_path = _find_font(bold=True)
    font_reg_path = _find_font(bold=False)
    font_mono_path = _find_font(mono=True)

    f_category = _load_font(font_bold_path, 12 * scale)
    f_badge = _load_font(font_bold_path, 12 * scale)
    f_name = _load_font(font_bold_path, 30 * scale)
    f_meta = _load_font(font_reg_path, 14 * scale)
    f_meta_mono = _load_font(font_mono_path or font_bold_path, 14 * scale)
    f_stat_label = _load_font(font_bold_path, 11 * scale)
    f_stat_val = _load_font(font_bold_path, 21 * scale)
    f_stat_val_mono = _load_font(font_mono_path or font_bold_path, 20 * scale)
    f_row_label = _load_font(font_bold_path, 13 * scale)
    f_row_val = _load_font(font_mono_path or font_bold_path, 13 * scale)
    f_footer = _load_font(font_reg_path, 12 * scale)

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
        badge_type = "warn"  # Gold / Amber for top Mythic
    elif "mythic" in rank_name.lower() or "myth" in tier:
        badge_type = "running"  # Violet for Mythic
    elif "legend" in rank_name.lower():
        badge_type = "info"  # Blue for Legend
    else:
        badge_type = "success"  # Emerald

    # Peak / Highest Rank
    hist_rank = player_data.get("historyRank")
    if isinstance(hist_rank, dict):
        peak_rank_name = hist_rank.get("name") or rank_name
    elif isinstance(hist_rank, str) and hist_rank:
        peak_rank_name = hist_rank
    else:
        peak_rank_name = rank_name

    # Compute overall statistics from all seasons
    raw_stats = player_data.get("stats")
    total_games = 0
    total_wins = 0
    total_mvps = 0
    ranked_seasons = []

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

    # Sort ranked seasons descending by season number
    ranked_seasons.sort(key=lambda x: x.get("season", 0), reverse=True)

    # Current / latest season info
    if ranked_seasons:
        latest = ranked_seasons[0]
        cur_season_num = latest.get("season", "")
        cur_season_games = latest.get("games", 0)
        cur_season_wr = latest.get("winRate", 0.0)
        cur_season_kda = latest.get("kda", 0.0)
        cur_season_mvp = latest.get("mvp", 0)
        cur_season_text = f"{cur_season_games} игр ({cur_season_wr:.1f}%)"
        cur_kda_text = f"{cur_season_kda:.2f} KDA • {cur_season_mvp} MVP"
    else:
        cur_season_num = ""
        cur_season_text = "Нет матчей"
        cur_kda_text = "—"


    # 0. Base wallpaper / dark obsidian background
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
    content_y = card_inset + (30 * scale)
    content_right = w - card_inset - (34 * scale)

    # 1. Top row: Category tag + Status Pill
    draw.text((content_x, content_y + 4 * scale), "MOBILE LEGENDS // PLAYER DOSSIER", font=f_category, fill=COLOR_TEXT_DIM)

    # Badge pill on right
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
    header_y = content_y + (38 * scale)
    avatar_size = 88 * scale
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
        # Fallback stylized avatar box with ML icon initial
        draw.rounded_rectangle(avatar_rect, radius=avatar_radius, fill=COLOR_BOX_BG)
        initial = (name[0] if name else "M").upper()
        f_init = _load_font(font_bold_path, 36 * scale)
        ibox = f_init.getbbox(initial)
        iw = ibox[2] - ibox[0]
        ih = ibox[3] - ibox[1]
        draw.text(
            (content_x + (avatar_size - iw) // 2 - ibox[0], header_y + (avatar_size - ih) // 2 - ibox[1]),
            initial,
            font=f_init,
            fill=accent_theme["dot"],
        )

    # Avatar glowing hairline border
    draw.rounded_rectangle(avatar_rect, radius=avatar_radius, outline=COLOR_BORDER_LIGHT, width=2 * scale)

    # Name and Meta next to avatar
    text_info_x = content_x + avatar_size + (22 * scale)
    name_y = header_y + (4 * scale)
    draw.text((text_info_x, name_y), name, font=f_name, fill=COLOR_TEXT_WHITE)

    meta_y1 = name_y + (38 * scale)
    id_str = f"ID: {role_id} ({zone_id})" if role_id and zone_id else f"ID: {role_id}"
    meta_line1 = f"{id_str}   •   LEVEL {level}   •   SERVER CIS / GLOBAL"
    draw.text((text_info_x, meta_y1), meta_line1, font=f_meta_mono, fill=COLOR_TEXT_MUTED)

    meta_y2 = meta_y1 + (22 * scale)
    meta_line2 = f"ПИКОВЫЙ РАНГ: {peak_rank_name.upper()}   •   НАГРАДЫ MVP: {total_mvps:,}"
    draw.text((text_info_x, meta_y2), meta_line2, font=f_meta, fill=COLOR_TEXT_DIM)

    # Hairline divider
    divider_y = header_y + avatar_size + (24 * scale)
    draw.line([(content_x, divider_y), (content_right, divider_y)], fill=COLOR_BORDER, width=1 * scale)

    # 3. Main Stats Grid (4 Metric Boxes)
    curr_y = divider_y + (20 * scale)
    stat_cards_h = 92 * scale
    col_gap = 14 * scale

    grid_stats = [
        ("ОБЩИЙ ВИНРЕЙТ", overall_wr_str, BADGE_THEMES["success"]["text"] if overall_wr_str != "—" and float(overall_wr_str.rstrip("%")) >= 55 else COLOR_TEXT_WHITE),
        ("ВСЕГО МАТЧЕЙ", f"{total_games:,}" if total_games else "—", COLOR_TEXT_WHITE),
        (f"СЕЗОН {cur_season_num} (RANKED)", cur_season_text, COLOR_TEXT_WHITE),
        ("KDA СЕЗОНА & MVP", cur_kda_text, accent_theme["text"]),
    ]

    total_gaps = col_gap * (len(grid_stats) - 1)
    card_width = (content_right - content_x - total_gaps) // len(grid_stats)

    for i, (label, val, val_color) in enumerate(grid_stats):
        cx1 = content_x + i * (card_width + col_gap)
        cx2 = cx1 + card_width
        cy1 = curr_y
        cy2 = cy1 + stat_cards_h

        draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=10 * scale, fill=COLOR_BOX_BG, outline=COLOR_BORDER, width=1 * scale)
        draw.text((cx1 + 16 * scale, cy1 + 14 * scale), label, font=f_stat_label, fill=COLOR_TEXT_DIM)
        draw.text((cx1 + 16 * scale, cy1 + 38 * scale), str(val), font=f_stat_val_mono, fill=val_color)

    curr_y += stat_cards_h + (18 * scale)

    # 4. Ranked Seasons History Strip (Last 3 ranked seasons)
    hist_box_h = 138 * scale
    draw.rounded_rectangle(
        [content_x, curr_y, content_right, curr_y + hist_box_h],
        radius=10 * scale,
        fill=COLOR_BOX_BG,
        outline=COLOR_BORDER,
        width=1 * scale,
    )

    # Title of history strip
    draw.text((content_x + 18 * scale, curr_y + 14 * scale), "ИСТОРИЯ ПОСЛЕДНИХ СЕЗОНОВ // RANKED MATCHES", font=f_stat_label, fill=COLOR_TEXT_DIM)

    # Show up to 3 seasons rows
    sample_seasons = ranked_seasons[:3]
    if sample_seasons:
        row_y = curr_y + (38 * scale)
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
            (content_x + 18 * scale, curr_y + 60 * scale),
            "Подробная история матчей отсутствует или скрыта в настройках приватности",
            font=f_meta,
            fill=COLOR_TEXT_MUTED,
        )

    # 5. Footer Bar
    footer_y = h - card_inset - (38 * scale)
    draw.line([(content_x, footer_y - (14 * scale)), (content_right, footer_y - (14 * scale))], fill=COLOR_BORDER, width=1 * scale)
    draw.text((content_x, footer_y), "MLBB TELEMETRY ENGINE // USERBOT v1.0", font=f_footer, fill=COLOR_TEXT_DIM)

    meta_r = "REAL-TIME SYNCED • DATA VERIFIED"
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
    output.name = "mlbb_card.png"
    return output


