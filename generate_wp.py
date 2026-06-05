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
    
    # Split by double newlines into blocks
    blocks = [b.strip() for b in ch_text.split('\n\n') if b.strip()]
    
    rus = []
    eng = []
    
    # Skip block 0 (it is the CHAPTER header, e.g. "CHAPTER I")
    for block in blocks[1:]:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) == 2:
            rus_p = lines[0].lstrip('>').strip()
            # Clean up leading dashes or quotes if appropriate, but keeping French/Russian intact
            eng_p = lines[1].lstrip('"').rstrip('"').strip()
            rus.append(rus_p)
            eng.append(eng_p)
        elif len(lines) == 1:
            # Skip chapter headers like "II", "III", "IV" at the end of chapters
            if lines[0] in ['I', 'II', 'III', 'IV', 'V', 'VI']:
                continue
            rus.append(lines[0].lstrip('>').strip())
            eng.append("")
    
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