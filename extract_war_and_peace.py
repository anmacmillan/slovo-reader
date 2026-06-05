#!/usr/bin/env python3
"""
Extract Vol 1, Chapters 1-3 from the parallel War and Peace text
and generate data.js for slovo-reader.
"""

import os
import re
import json
import sys

LANG_DIR = "/Users/alexandermacmillan/Downloads"
OUT_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"
BIG_FILE = os.path.join(LANG_DIR, "Война и мир.txt")

# ── Parse the parallel text ──────────────────────────────────────────────────
# The format is:
# BOOK ONE: 1805
# 
# ЧАСТЬ ПЕРВАЯ
# CHAPTER I
# 
# > Russian text...
# " English translation...

def parse_book(text):
    """Split into Book > Part > Chapter structure."""
    lines = text.strip().splitlines()
    chapters = []
    current_chapter = []
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Detect chapter markers: "CHAPTER I", "CHAPTER II", etc.
        if re.match(r'^CHAPTER\s+[IVXLCDM]+', s):
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = []
        else:
            current_chapter.append(s)
    
    if current_chapter:
        chapters.append(current_chapter)
    
    return chapters

def split_chapters(chapter_texts):
    """Split each chapter into Russian (lines starting with >) and English (lines starting with ")."""
    rus_paras = []
    eng_paras = []
    
    for lines in chapter_texts[:3]:  # Only first 3 chapters
        for line in lines:
            line = line.strip()
            if line.startswith('>') and re.match(r'[а-яёА-ЯЁ]', line):
                # Russian line
                rus_paras.append(line[1:].strip())
            elif line.startswith('"') and not line.startswith('">'):
                # English line
                eng_paras.append(line[1:].strip())
            elif not line.startswith('>') and not line.startswith('"'):
                # Could be either - check if it has Cyrillic
                if re.search(r'[а-яёА-ЯЁ]', line):
                    rus_paras.append(line)
                else:
                    eng_paras.append(line)
    
    return rus_paras, eng_paras

def main():
    with open(BIG_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Find Book One
    book1_start = text.find("BOOK ONE")
    if book1_start < 0:
        print("Book One not found")
        sys.exit(1)
    
    book1 = text[book1_start:]
    
    # Split into chapters
    chapters = parse_book(book1)
    print(f"Found {len(chapters)} chapters")
    
    rus_paras, eng_paras = split_chapters(chapters)
    
    print(f"Russian paragraphs: {len(rus_paras)}")
    print(f"English paragraphs: {len(eng_paras)}")
    
    for i, (r, e) in enumerate(zip(rus_paras[:5], eng_paras[:5])):
        print(f"  [{i}] R: {r[:60]}...")
        print(f"      E: {e[:60]}...")

if __name__ == "__main__":
    main()