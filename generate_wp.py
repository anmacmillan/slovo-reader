#!/usr/bin/env python3
"""
Generate data.js for War and Peace — Vol 1, Chapters 1-3
as a second book in slovo-reader.
"""

import os
import re
import json
import sys

LANG_DIR = "/Users/alexandermacmillan/Downloads"
SLOVO_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"
BIG_FILE = os.path.join(LANG_DIR, "Война и мир.txt")

def parse_rus_chapters(text):
    """Find ЧАСТЬ/CHAPTER markers in the text and extract paragraphs."""
    # The text uses > for Russian original and " for English translation
    # We need to extract just the Russian paragraphs from Book 1
    
    # Find the start of Book One
    book_start = text.find("BOOK ONE") if "BOOK ONE" in text else 0
    text = text[book_start:]
    
    lines = text.splitlines()
    
    # Split by chapter markers (CHAPTER I, II etc.)
    rus_chapters = {}
    current_ch = 1
    buf = []
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        
        # Detect chapter headers
        m = re.match(r'^CHAPTER\s+(I{1,3}V?|VI{0,3}|X{0,3})', s)
        if m:
            if buf:
                rus_chapters[current_ch] = buf
            current_ch = int(1)  # Just count sequentially
            buf = []
        elif s.startswith('>') or s.startswith('–') or s.startswith('«'):
            # Russian text
            buf.append(s)
        elif s.startswith('"') or s.startswith('"'):
            # English text - skip for now
            pass
    
    if buf:
        rus_chapters[current_ch] = buf
    
    return rus_chapters

def parse_eng_chapters(text):
    """Find CHAPTER markers and extract English paragraphs."""
    lines = text.splitlines()
    eng_chapters = {}
    current_ch = 1
    buf = []
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        
        m = re.match(r'^CHAPTER\s+(I{1,3}V?|VI{0,3}|X{0,3})', s)
        if m:
            if buf:
                eng_chapters[current_ch] = buf
            current_ch += 1
            buf = []
        elif s.startswith('"') and not s.startswith('" '):
            # English text (lines starting with double quote)
            buf.append(s)
    
    if buf:
        eng_chapters[current_ch] = buf
    
    return eng_chapters

def main():
    with open(BIG_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Find Book One (after Gutenberg headers)
    book1_start = text.find("BOOK ONE")
    if book1_start < 0:
        print("No 'BOOK ONE' marker found")
        sys.exit(1)
    
    book1 = text[book1_start:]
    
    # Find first 3 chapters
    # The text has: BOOK ONE > BOOK ONE: 1805
    # Then chapters are marked as: CHAPTER I, CHAPTER II etc.
    
    # Parse both languages
    all_lines = book1.split("\n")
    
    # Extract Russian and English paragraphs
    rus_lines, eng_lines = [], []
    current_chapter = 0
    in_chapter = False
    
    for line in all_lines:
        s = line.strip()
        
        if re.match(r'^CHAPTER\s+[IVXLCDM]+', s):
            current_chapter += 1
            if current_chapter > 3:
                break
        
        if current_chapter <= 3 and current_chapter >= 1:
            # Check if line has Russian text (starts with > or has Cyrillic)
            if s.startswith('>') and re.search(r'[а-яёА-ЯЁ]', s):
                rus_lines.append(s[1:].strip())
            elif s.startswith('"') and not re.search(r'[а-яёА-ЯЁ]', s):
                eng_lines.append(s[1:].strip())
            elif s.startswith('—') or s.startswith('–') or s.startswith('«'):
                rus_lines.append(s)
            elif s.startswith('"') or s.startswith('"'):
                eng_lines.append(s)
    
    # Now we have Russian and English paragraphs for chapters 1-3
    # Split them into aligned chunks
    TARGET_WORDS = 85
    
    # Count words in each
    rus_w = sum(len(p.split()) for p in rus_lines)
    eng_w = sum(len(p.split()) for p in eng_lines)
    print(f"Ch 1: {rus_w} / {eng_w} words")
    
    # For now just output the first few paragraphs
    for i in range(min(10, len(rus_lines))):
        print(f"  [{i}] R: {rus_lines[i][:60]...}")
        print(f"      E: {eng_lines[i][:60]...}")

if __name__ == "__main__":
    main()