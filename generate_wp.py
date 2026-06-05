#!/usr/bin/env python3
"""
Add War and Peace (Vol 1, Ch 1-3) as second book in slovo-reader.
"""

import re
import json
import sys
import os

SLOVO_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"

# Read the large parallel text file
with open("/Users/alexandermacmillan/Downloads/Война и мир.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Find Book One
b1 = text.find("BOOK ONE")
text = text[b1:]

# Split by chapters
chapters_raw = re.split(r'\n(?=CHAPTER\s)', text)

# Take first 3 chapters (indices 1, 2, 3 after the header)
chapters_data = []
for ch_idx in [1, 2, 3]:
    ch_text = chapters_raw[ch_idx] if ch_idx < len(chapters_raw) else ""
    
    # Extract Russian (>) and English (") paragraphs
    rus = []
    eng = []
    for line in ch_text.split("\n"):
        s = line.strip()
        if not s:
            continue
        # Russian: starts with > or has Cyrillic
        if s.startswith(">") and re.search(r"[а-яё]", s):
            rus.append(s[1:].strip())
        elif re.search(r"[а-яё]", s) and not s.startswith('"'):
            # Russian text without marker
            rus.append(s.lstrip(">—«").strip())
        elif s.startswith('"') and not re.search(r"[а-яё]", s):
            eng.append(s[1:].strip())
    
    chapters_data.append({
        "chapterNum": ch_idx,
        "titleRus": f"Глава {ch_idx}",
        "titleEng": f"Chapter {['I','II','III'][ch_idx-1]}",
        "russian": rus,
        "english": eng
    })
    print(f"Ch {ch_idx}: {len(rus)} / {len(eng)} paragraphs")

book = {
    "title": "Война и мир",
    "titleEng": "War and Peace",
    "author": "Л. Н. Толстой",
    "authorEng": "Leo Tolstoy",
    "year": "1869",
    "chapters": chapters_data
}

# Append to data.js
from pathlib import Path
data_path = Path(SLOVO_DIR) / "data.js"
with open(data_path, "r") as f:
    current = f.read()

m = re.search(r"const PRELOADED_BOOKS = (\[.*\]);", current, re.DOTALL)
if m:
    books = json.loads(m.group(1))
    books.append(book)
    new_data = f"const PRELOADED_BOOKS = {json.dumps(books, ensure_ascii=False, indent=2)};\n"
    with open(data_path, "w") as f:
        f.write(new_data)
    print(f"Added 'Война и мир' to data.js ({len(books)} books)")
    sys.exit(0)
else:
    print("data.js format error")
    sys.exit(1)