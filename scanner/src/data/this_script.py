from PIL import Image, ImageDraw, ImageFont

# Standard Code 128 symbol table (values 0-102 shared symbols, 103/104/105 = START A/B/C, 106 = STOP)
# Each entry is 6 digits of bar/space module widths (STOP has 7).
CODE128_WIDTHS = [
"212222","222122","222221","121223","121322","131222","122213","122312","132212","221213",
"221312","231212","112232","122132","122231","113222","123122","123221","223211","221132",
"221231","213212","223112","312131","311222","321122","321221","312212","322112","322211",
"212123","212321","232121","111323","131123","131321","112313","132113","132311","211313",
"231113","231311","112133","112331","132131","113123","113321","133121","313121","211331",
"231131","213113","213311","213131","311123","311321","331121","312113","312311","332111",
"314111","221411","431111","111224","111422","121124","121421","141122","141221","112214",
"112412","122114","122411","142112","142211","241211","221114","413111","241112","134111",
"111242","121142","121241","114212","124112","124211","411212","421112","421211","212141",
"214121","412121","111143","111341","131141","114113","114311","411113","411311","113141",
"114131","311141","411131","211412","211214","211232","2331112"
]

START_B = 104
STOP = 106

def encode_code128b(text):
    """Encode text (printable ASCII 32-126) as Code128 Code Set B."""
    values = [ord(c) - 32 for c in text]
    for v, c in zip(values, text):
        if v < 0 or v > 94:
            raise ValueError(f"Character not supported in Code B: {c!r}")

    checksum = START_B
    for i, v in enumerate(values, start=1):
        checksum += v * i
    checksum %= 103

    symbols = [START_B] + values + [checksum, STOP]
    return symbols

def render_barcode(text, label_lines, out_path, module_width=3, bar_height=140):
    symbols = encode_code128b(text)

    pattern = ""
    for sym in symbols:
        pattern += CODE128_WIDTHS[sym]

    total_modules = sum(int(d) for d in pattern)
    quiet_zone_modules = 10
    img_width = (total_modules + quiet_zone_modules * 2) * module_width
    text_area_height = 22 * (len(label_lines) + 1)
    img_height = bar_height + text_area_height + 20

    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)

    x = quiet_zone_modules * module_width
    is_bar = True
    for digit in pattern:
        w = int(digit) * module_width
        if is_bar:
            draw.rectangle([x, 10, x + w - 1, 10 + bar_height], fill="black")
        x += w
        is_bar = not is_bar

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    ty = bar_height + 22
    # human-readable payload text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((img_width - tw) / 2, ty), text, fill="black", font=font)
    ty += 24

    for i, line in enumerate(label_lines):
        f = font_bold if i == 0 else font
        bbox = draw.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        draw.text(((img_width - tw) / 2, ty), line, fill="black", font=f)
        ty += 20

    img.save(out_path)
    print(f"Saved {out_path} ({img_width}x{img_height})")

payload_clean = "01089020000000161727063010LOT2401"
payload_conflict = "01089020000000161728063010LOT2401"

render_barcode(
    payload_clean,
    ["Dolo 650 - Baseline Scan", "GTIN 08902000000016 | Batch LOT2401 | Exp 2027-06-30"],
    "dolo_barcode_clean.png",
)

render_barcode(
    payload_conflict,
    ["Dolo 650 - Conflict Scan", "GTIN 08902000000016 | Batch LOT2401 | Exp 2028-06-30"],
    "dolo_barcode_conflict.png",
)