#!/usr/bin/env python3
"""
UGC Video Generator Pipeline
Analyzes a product URL, writes a 30-second ad script,
generates TTS audio, and assembles an animated slideshow via FFmpeg.
"""

import argparse
import os
import re
import sys
import textwrap
import time
from pathlib import Path

import subprocess as _sp

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont


# ── Config ────────────────────────────────────────────────────────────────────

SLIDE_W, SLIDE_H = 1080, 1920          # vertical 9:16 (TikTok / Reels)
BG_COLOR = (15, 15, 20)               # near-black background
ACCENT_COLOR = (255, 90, 50)          # warm orange accent
TEXT_COLOR = (245, 245, 245)
FONT_SIZE_TITLE = 72
FONT_SIZE_BODY = 52
FONT_SIZE_CTA = 64
SLIDE_DURATION = 5                     # seconds per slide
TRANSITION_FRAMES = 15                 # fade frames between slides
FPS = 30


# ── Step 1: Scrape product page ───────────────────────────────────────────────

def scrape_product(url: str) -> dict:
    """Return {title, description, price, features} from a product page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[warn] Could not fetch URL ({exc}). Using demo product data.")
        return _demo_product()

    soup = BeautifulSoup(resp.text, "html.parser")

    title = (
        soup.find("h1") or
        soup.find(attrs={"id": re.compile(r"product.?title", re.I)}) or
        soup.find(attrs={"class": re.compile(r"product.?title", re.I)})
    )
    title = title.get_text(strip=True) if title else "Amazing Product"

    # Grab meta description as fallback body copy
    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc = meta_desc["content"] if meta_desc and meta_desc.get("content") else ""

    # Pull bullet features if present
    feature_tags = soup.select("li")[:8]
    features = [li.get_text(strip=True) for li in feature_tags if li.get_text(strip=True)][:5]

    price_tag = soup.find(string=re.compile(r"\$[\d,]+\.?\d*"))
    price = price_tag.strip() if price_tag else ""

    return {
        "title": title[:80],
        "description": desc[:300] or "A product you will love.",
        "price": price,
        "features": features or ["High quality", "Easy to use", "Great value"],
        "url": url,
    }


def _demo_product() -> dict:
    return {
        "title": "ProGlow LED Face Mask",
        "description": "Clinically proven red & blue light therapy at home. Reduce acne, boost collagen, and reveal glowing skin in just 10 minutes a day.",
        "price": "$89",
        "features": [
            "7 light wavelengths",
            "FDA-cleared technology",
            "Hands-free design",
            "Rechargeable battery",
            "30-day money-back guarantee",
        ],
        "url": "https://example.com/proglow",
    }


# ── Step 2: Generate UGC ad script ───────────────────────────────────────────

def generate_script(product: dict) -> list[dict]:
    """
    Return a list of slide dicts: {headline, body, visual_note}
    Targeting ~30 seconds total @ SLIDE_DURATION sec/slide.
    """
    title = product["title"]
    desc = product["description"]
    feats = product["features"]
    price = product["price"]
    price_str = f"for only {price}" if price else ""

    slides = [
        {
            "headline": "Wait — have you seen this? 👀",
            "body": f"I finally tried {title} and I can't stop talking about it.",
            "visual_note": "Creator pointing at product, candid selfie angle",
        },
        {
            "headline": "Here's the deal:",
            "body": textwrap.shorten(desc, width=120, placeholder="..."),
            "visual_note": "Close-up of product",
        },
        {
            "headline": "What makes it special?",
            "body": "\n".join(f"✓ {f}" for f in feats[:3]),
            "visual_note": "Feature demo / unboxing shots",
        },
        {
            "headline": "The results speak for themselves",
            "body": f"After just one week I noticed a huge difference. Totally worth it {price_str}.",
            "visual_note": "Before/after or testimonial overlay",
        },
        {
            "headline": "Don't sleep on this 🔥",
            "body": "Link in bio → grab yours before they sell out!",
            "visual_note": "Creator thumbs up, CTA text animation",
        },
    ]
    return slides


def script_to_voiceover(slides: list[dict]) -> str:
    """Flatten slides into a single narration string."""
    lines = []
    for s in slides:
        lines.append(s["headline"].replace("👀", "").replace("🔥", "").strip())
        lines.append(s["body"].replace("✓ ", "").replace("\n", ". "))
    return "  ".join(lines)


# ── Step 3: TTS voiceover ─────────────────────────────────────────────────────

def generate_tts(text: str, output_path: str):
    """Offline TTS via espeak-ng → WAV, then convert to MP3 with ffmpeg."""
    print(f"[tts] Generating voiceover (espeak-ng) → {output_path}")
    wav_path = output_path.replace(".mp3", ".wav")
    # espeak-ng: -s speed (words/min), -a amplitude, -v voice
    result = _sp.run(
        ["espeak-ng", "-v", "en-us", "-s", "145", "-a", "180",
         "-w", wav_path, text],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("[espeak error]", result.stderr)
        sys.exit(1)
    # Convert WAV → MP3
    _sp.run(
        ["ffmpeg", "-loglevel", "warning", "-y", "-i", wav_path,
         "-b:a", "128k", output_path],
        check=True,
    )
    os.remove(wav_path)
    print(f"[tts] Saved {output_path}")


# ── Step 4: Render slide images ───────────────────────────────────────────────

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_slide(slide: dict, index: int, total: int, out_path: str):
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_SIZE_TITLE)
    font_body = _load_font(FONT_SIZE_BODY)
    font_cta = _load_font(FONT_SIZE_CTA)

    # Accent bar at top
    draw.rectangle([(0, 0), (SLIDE_W, 12)], fill=ACCENT_COLOR)

    # Slide counter dots
    dot_r = 10
    dot_spacing = 30
    total_dots_w = total * dot_spacing
    dot_x0 = (SLIDE_W - total_dots_w) // 2
    for i in range(total):
        cx = dot_x0 + i * dot_spacing + dot_r
        cy = 50
        color = ACCENT_COLOR if i == index else (80, 80, 90)
        draw.ellipse([(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)], fill=color)

    margin = 80
    max_text_w = SLIDE_W - 2 * margin
    y = 130

    # Headline
    headline_lines = _wrap_text(slide["headline"], font_title, max_text_w)
    for line in headline_lines:
        bbox = font_title.getbbox(line)
        x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font_title, fill=ACCENT_COLOR)
        y += bbox[3] - bbox[1] + 16

    y += 40

    # Body
    body_font = font_cta if index == len_slides - 1 else font_body  # noqa — patched below
    body_lines_raw = slide["body"].split("\n")
    for raw_line in body_lines_raw:
        for line in _wrap_text(raw_line, font_body, max_text_w):
            bbox = font_body.getbbox(line)
            x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, font=font_body, fill=TEXT_COLOR)
            y += bbox[3] - bbox[1] + 12

    # Visual note (small, bottom area)
    note = f"🎬 {slide['visual_note']}"
    note_font = _load_font(36)
    note_lines = _wrap_text(note, note_font, max_text_w)
    note_y = SLIDE_H - 160 - len(note_lines) * 46
    for line in note_lines:
        bbox = note_font.getbbox(line)
        x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, note_y), line, font=note_font, fill=(120, 120, 135))
        note_y += bbox[3] - bbox[1] + 8

    # Accent bar at bottom
    draw.rectangle([(0, SLIDE_H - 12), (SLIDE_W, SLIDE_H)], fill=ACCENT_COLOR)

    img.save(out_path, "PNG")


# Patch the forward-reference in render_slide
len_slides = 5


# ── Step 5: Assemble video with FFmpeg ────────────────────────────────────────

def build_video(slide_dir: str, audio_path: str, output_path: str, n_slides: int):
    """
    Build a slideshow video:
    - Each slide held for SLIDE_DURATION seconds
    - Cross-fade transition of TRANSITION_FRAMES frames
    - Mixed with TTS audio
    """
    import subprocess

    slide_duration = SLIDE_DURATION
    fade_dur = TRANSITION_FRAMES / FPS  # seconds

    # Build filter_complex for cross-fade between slides
    inputs = []
    for i in range(n_slides):
        inputs += ["-loop", "1", "-t", str(slide_duration + fade_dur),
                   "-i", str(Path(slide_dir) / f"slide_{i:02d}.png")]

    # xfade chain
    filter_parts = []
    prev = "0:v"
    for i in range(1, n_slides):
        offset = i * slide_duration - (i - 1) * fade_dur
        out_label = f"v{i}"
        filter_parts.append(
            f"[{prev}][{i}:v]xfade=transition=fade:duration={fade_dur:.3f}:offset={offset:.3f}[{out_label}]"
        )
        prev = out_label

    filter_complex = ";".join(filter_parts)
    total_video_dur = n_slides * slide_duration

    cmd = (
        inputs +
        ["-i", audio_path,
         "-filter_complex", filter_complex,
         "-map", f"[{prev}]",
         "-map", f"{n_slides}:a",
         "-c:v", "libx264",
         "-preset", "fast",
         "-crf", "22",
         "-c:a", "aac",
         "-b:a", "128k",
         "-t", str(total_video_dur),
         "-pix_fmt", "yuv420p",
         "-y", output_path]
    )

    full_cmd = ["ffmpeg", "-loglevel", "warning"] + cmd
    print(f"[ffmpeg] Assembling video → {output_path}")
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ffmpeg error]", result.stderr[-2000:])
        sys.exit(1)
    print(f"[ffmpeg] Done. File: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UGC Video Generator")
    parser.add_argument("url", nargs="?", default="demo",
                        help="Product page URL (or 'demo' to use sample data)")
    parser.add_argument("--out", default="ugc_output/ad_video.mp4",
                        help="Output video path")
    parser.add_argument("--slides-only", action="store_true",
                        help="Render slide PNGs without building video")
    args = parser.parse_args()

    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    slide_dir = out_dir / "slides"
    slide_dir.mkdir(exist_ok=True)

    # ── 1. Scrape ──
    url = args.url if args.url != "demo" else None
    if url:
        print(f"[scrape] Fetching {url}")
        product = scrape_product(url)
    else:
        print("[scrape] Using demo product data")
        product = _demo_product()

    print(f"[product] {product['title']}")

    # ── 2. Script ──
    slides = generate_script(product)
    global len_slides
    len_slides = len(slides)
    print(f"[script] Generated {len(slides)} slides")
    for i, s in enumerate(slides):
        print(f"  Slide {i+1}: {s['headline']}")

    # ── 3. TTS ──
    voiceover_text = script_to_voiceover(slides)
    audio_path = str(out_dir / "voiceover.mp3")
    generate_tts(voiceover_text, audio_path)

    # ── 4. Render slides ──
    print("[render] Drawing slide images…")
    for i, slide in enumerate(slides):
        out_png = str(slide_dir / f"slide_{i:02d}.png")
        render_slide(slide, i, len(slides), out_png)
        print(f"  → {out_png}")

    if args.slides_only:
        print("[done] Slides rendered. Skipping video assembly.")
        return

    # ── 5. Build video ──
    build_video(str(slide_dir), audio_path, args.out, len(slides))

    size_mb = Path(args.out).stat().st_size / 1_048_576
    print(f"\n✅ UGC ad video ready: {args.out}  ({size_mb:.1f} MB)")
    print(f"   Duration: ~{len(slides) * SLIDE_DURATION}s  |  Resolution: {SLIDE_W}x{SLIDE_H}")


if __name__ == "__main__":
    main()
