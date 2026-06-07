#!/usr/bin/env python3
"""
Add Three Sisters (Chekhov) as third book in slovo-reader.
"""

import os, re, json, sys
SLOVO_DIR = "/Users/alexandermacmillan/Projects/slovo-reader"
LANG_DIR = "/Users/alexandermacmillan/Projects/slovo-reader/texts/russian"
RUS_PATH = os.path.join(LANG_DIR, "Три сестры.txt")
# FIXME: update to repo path once moved
EN_URL = "https://www.ibiblio.org/eldritch/ac/sisters.htm"

def fetch_eng():
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resp = urllib.request.urlopen(EN_URL, context=ctx)
    html = resp.read().decode("utf-8")
    # Find act anchors
    act_starts = []
    for m in re.finditer(r'<A NAME="act(\d+)"', html):
        act_starts.append((int(m.group(1)), m.end()))
    act_starts.sort()
    acts = {}
    for i, (act_num, start_pos) in enumerate(act_starts):
        end_pos = act_starts[i+1][1] if i+1 < len(act_starts) else len(html)
        act_html = html[start_pos:end_pos]
        text = re.sub(r'<[^>]+>', '\n', act_html)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        # Split into paragraphs
        pars = [p.strip() for p in text.split('\n\n') if p.strip()]
        acts[act_num] = pars
    return acts

def parse_rus():
    with open(RUS_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    acts = {}
    current = 1
    buf = []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue
        if re.match(r'Действие\s+\d', s):
            if buf:
                acts[current] = buf
            m = re.search(r'\d+', s)
            current = int(m.group())
            buf = []
        elif s:
            buf.append(s)
    if buf:
        acts[current] = buf
    return acts

def split_equal_chunks(paras, n):
    """Split into ~85-word chunks."""
    if not paras:
        return [''] * n
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
    rus_acts = parse_rus()
    eng_acts = fetch_eng()
    
    TARGET_WORDS = 85
    chapters = []
    
    for act_num in range(1, 5):
        rp = rus_acts.get(act_num, [])
        ep = eng_acts.get(act_num, [])
        rus_w = sum(len(p.split()) for p in rp)
        eng_w = sum(len(p.split()) for p in ep)
        n = max(1, round((rus_w + eng_w) / 2 / TARGET_WORDS))
        rus_chunks = split_equal_chunks(rp, n)
        eng_chunks = split_equal_chunks(ep, n)
        
        chapters.append({
            "chapterNum": act_num,
            "titleRus": f"Действие {act_num}",
            "titleEng": f"Act {['I','II','III','IV'][act_num-1]}",
            "russian": rus_chunks,
            "english": eng_chunks
        })
        print(f"Act {act_num}: {len(rp)}/{len(ep)} -> {n} chunks")
    
    book = {
        "title": "Три сестры",
        "titleEng": "The Three Sisters",
        "author": "А. П. Чехов",
        "authorEng": "Anton Chekhov",
        "year": "1901",
        "chapters": chapters
    }
    
    # Append to data.js
    with open(os.path.join(SLOVO_DIR, "data.js"), "r") as f:
        current = f.read()
    
    m = re.search(r'const PRELOADED_BOOKS = (\[.*\]);', current, re.DOTALL)
    if m:
        books = json.loads(m.group(1))
        books.append(book)
        new_data = f"const PRELOADED_BOOKS = {json.dumps(books, ensure_ascii=False, indent=2)};\n"
        with open(os.path.join(SLOVO_DIR, "data.js"), "w") as f:
            f.write(new_data)
        print(f"\nAdded 'Три сестры' to data.js ({len(books)} books)")
        print(f"  Total: {sum(len(c['russian']) for c in book['chapters'])} paragraphs")

if __name__ == "__main__":
    main()