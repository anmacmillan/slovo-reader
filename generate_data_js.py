#!/usr/bin/env python3
import json
import os
import re

LANG_DIR = "/Users/alexandermacmillan/Google Drive/My Drive/Personal/Languages"
OUT_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"

def parse_russian(text):
    chapters = {}
    current, buf = 1, []
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r'\d', s):
            chapters[current] = buf
            current = int(s)
            buf = []
        elif s and s not in ('КАВКАЗСКИЙ ПЛЕННИК', 'Л. Н. Толстой (1872)'):
            buf.append(s)
    chapters[current] = buf
    return chapters

def parse_english(text):
    roman = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6}
    chapters = {}
    current, buf = None, []
    raw_paras = re.split(r'\n\s*\n', text.strip())
    for block in raw_paras:
        s = ' '.join(block.split()).strip()
        if not s:
            continue
        m = re.fullmatch(r'(VI?|I{1,3}V?)\.', s)
        if m:
            if current is not None:
                chapters[current] = buf
            current = roman[m.group(1)]
            buf = []
        elif current is not None:
            buf.append(s)
    if current is not None:
        chapters[current] = buf
    return chapters

def split_equal_chunks(paras, n):
    text = ' '.join(paras)
    sents = re.split(r'(?<=[.!?»])\s+', text.strip())
    sents = [s.strip() for s in sents if s.strip()]
    if not sents:
        return [''] * n

    total = sum(len(s.split()) for s in sents)
    target = total / n

    chunks, cur, cur_w = [], [], 0
    for sent in sents:
        w = len(sent.split())
        cur.append(sent)
        cur_w += w
        if cur_w >= target and len(chunks) < n - 1:
            chunks.append(' '.join(cur))
            cur, cur_w = [], 0
    if cur:
        chunks.append(' '.join(cur))

    while len(chunks) > n:
        chunks[-2] += ' ' + chunks[-1]
        chunks.pop()
    while len(chunks) < n:
        chunks.append('')
    return chunks

def main():
    rus_path = os.path.join(LANG_DIR, "kavkazsky_plennik_russian.txt")
    eng_path = os.path.join(LANG_DIR, "prisoner_of_the_caucasus_english.txt")
    
    if not os.path.exists(rus_path) or not os.path.exists(eng_path):
        print(f"Error: Required files not found in {LANG_DIR}")
        return

    with open(rus_path, "r", encoding="utf-8") as f:
        rus_raw = f.read()
    with open(eng_path, "r", encoding="utf-8") as f:
        eng_raw = f.read()

    # Strip Gutenberg headers
    eng_raw = re.sub(r'\*\*\* START.*?\*\*\*', '', eng_raw, flags=re.DOTALL)
    eng_raw = re.sub(r'\*\*\* END.*',          '', eng_raw, flags=re.DOTALL)

    rus_chapters = parse_russian(rus_raw)
    eng_chapters = parse_english(eng_raw)

    TARGET_WORDS = 85
    chapters_data = []

    ROMAN = {1:'I', 2:'II', 3:'III', 4:'IV', 5:'V', 6:'VI'}

    for ch in range(1, 7):
        rp = rus_chapters.get(ch, [])
        ep = eng_chapters.get(ch, [])
        rus_w = sum(len(p.split()) for p in rp)
        eng_w = sum(len(p.split()) for p in ep)
        
        # Calculate optimal number of aligned chunks
        n = max(1, round((rus_w + eng_w) / 2 / TARGET_WORDS))
        rus_chunks = split_equal_chunks(rp, n)
        eng_chunks = split_equal_chunks(ep, n)
        
        chapters_data.append({
            "chapterNum": ch,
            "titleRus": f"Глава {ch}",
            "titleEng": f"Chapter {ROMAN[ch]}",
            "russian": rus_chunks,
            "english": eng_chunks
        })
        print(f"Chapter {ch} aligned into {n} chunks.")

    book = {
        "title": "Кавказский пленник",
        "titleEng": "A Prisoner of the Caucasus",
        "author": "Л. Н. Толстой",
        "authorEng": "Leo Tolstoy",
        "year": "1872",
        "chapters": chapters_data
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "data.js")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const PRELOADED_BOOKS = ")
        json.dump([book], f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Successfully wrote data.js to {out_path}")

if __name__ == "__main__":
    main()
