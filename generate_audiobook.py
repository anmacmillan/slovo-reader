#!/usr/bin/env python3
"""
Slovo Reader — Audiobook Generator

Generates one WAV per chapter using Piper TTS with the
Irina-medium Russian voice. Quick, local, and deployable.
"""

import os
import re
import subprocess
import sys
import time
import numpy as np

LANG_DIR = "/Users/alexandermacmillan/Google Drive/My Drive/Personal/Languages"
SLOVO_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"
VOICE = os.path.join(SLOVO_DIR, "piper_voices", "ru_RU-irina-medium.onnx")
OUT_DIR = os.path.join(SLOVO_DIR, "audiobook")

def parse_chapters(text):
    lines = text.strip().splitlines()
    chapters = []
    buf = []
    for line in lines:
        s = line.strip()
        if s in ("КАВКАЗСКИЙ ПЛЕННИК", "Л. Н. Толстой (1872)"):
            continue
        if re.fullmatch(r'[0-9]', s):
            if buf:
                chapters.append("\n".join(buf))
            buf = []
        elif s:
            buf.append(s)
    if buf:
        chapters.append("\n".join(buf))
    return chapters

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    rus_path = os.path.join(LANG_DIR, "kavkazsky_plennik_russian.txt")
    with open(rus_path, "r", encoding="utf-8") as f:
        rus_text = f.read()

    chapters = parse_chapters(rus_text)
    print(f"Chapters: {len(chapters)}")

    for ch_idx, chapter_text in enumerate(chapters):
        ch_num = ch_idx + 1
        wc = len(chapter_text.split())
        print(f"\n  Ch {ch_num}: {wc} words...")

        t0 = time.time()
        result = subprocess.run(
            ["piper",
             "--model", VOICE,
             "--output-raw"],
            input=chapter_text.encode("utf-8"),
            capture_output=True,
            timeout=300,
        )

        if result.returncode != 0:
            print(f"    ✗ ERROR: {result.stderr.decode()[:200]}")
            # Write silence
            import soundfile as sf
            sf.write(os.path.join(OUT_DIR, f"ch{ch_num:02d}.wav"), np.zeros(24000*5, dtype=np.float32), 24000)
            continue

        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
        elapsed = time.time() - t0
        dur = len(audio) / 24000
        print(f"    ✓ {dur:.0f}s in {elapsed:.1f}s ({dur/elapsed:.1f}x)")

        out = os.path.join(OUT_DIR, f"ch{ch_num:02d}.wav")
        import soundfile as sf
        sf.write(out, audio, 24000)
        kb = os.path.getsize(out) // 1024
        print(f"    → {out} ({kb}KB)")

    print("\nDone!")
    total_kb = sum(os.path.getsize(os.path.join(OUT_DIR, f)) // 1024 for f in os.listdir(OUT_DIR))
    print(f"Total: {total_kb}KB ({total_kb/1024:.1f}MB)")

if __name__ == "__main__":
    main()