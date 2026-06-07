#!/usr/bin/env python3
import json
import os
import re

RU_FILE = "/Users/alexandermacmillan/Projects/slovo-reader/texts/russian/lermontov_ru.txt"
EN_FILE = "/Users/alexandermacmillan/Projects/slovo-reader/texts/russian/lermontov_en.txt"
DATA_JS = "/Users/alexandermacmillan/Projects/slovo-reader/data.js"

def load_ru_sections():
    with open(RU_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # БЭЛА: line 50 (index 49)
    # МАКСИМ МАКСИМЫЧ: line 1119 (index 1118)
    # ТАМАНЬ: line 1455 (index 1454)
    # КНЯЖНА МЕРИ: line 1790 (index 1789)
    # ФАТАЛИСТ: line 4106 (index 4105)
    
    bela_text = "".join(lines[49:1118])
    maksim_text = "".join(lines[1118:1454])
    taman_text = "".join(lines[1454:1789])
    mary_text = "".join(lines[1789:4105])
    fatalist_text = "".join(lines[4105:])
    
    return {
        "Bela": bela_text,
        "Maksim": maksim_text,
        "Taman": taman_text,
        "Mary": mary_text,
        "Fatalist": fatalist_text
    }

def load_en_sections():
    with open(EN_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    bela_text = "".join(lines[50:1833])
    maksim_text = "".join(lines[1833:2361])
    taman_text = "".join(lines[2361:3005])
    fatalist_text = "".join(lines[3005:3480])
    mary_text = "".join(lines[3480:])
    
    return {
        "Bela": bela_text,
        "Maksim": maksim_text,
        "Taman": taman_text,
        "Mary": mary_text,
        "Fatalist": fatalist_text
    }

def split_equal_chunks(text, n):
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
    ru = load_ru_sections()
    en = load_en_sections()
    
    chapters_data = []
    sections = [
        ("Bela", "Бэла", "Bela", 1),
        ("Maksim", "Максим Максимыч", "Maksim Maksimych", 2),
        ("Taman", "Тамань", "Taman", 3),
        ("Mary", "Княжна Мери", "Princess Mary", 4),
        ("Fatalist", "Фаталист", "The Fatalist", 5),
    ]
    
    TARGET_WORDS = 85
    
    for key, title_ru, title_en, num in sections:
        ru_text = ru[key]
        en_text = en[key]
        
        # Calculate optimal chunks
        rus_w = len(ru_text.split())
        eng_w = len(en_text.split())
        n = max(1, round((rus_w + eng_w) / 2 / TARGET_WORDS))
        
        rus_chunks = split_equal_chunks(ru_text, n)
        eng_chunks = split_equal_chunks(en_text, n)
        
        chapters_data.append({
            "chapterNum": num,
            "titleRus": title_ru,
            "titleEng": title_en,
            "russian": rus_chunks,
            "english": eng_chunks
        })
        print(f"Aligned section '{title_en}' into {n} chunks.")

    book = {
        "title": "Герой нашего времени",
        "titleEng": "A Hero of Our Time",
        "author": "М. Ю. Лермонтов",
        "authorEng": "Mikhail Lermontov",
        "year": "1840",
        "chapters": chapters_data
    }

    # Append to data.js
    with open(DATA_JS, "r", encoding="utf-8") as f:
        current = f.read()

    m = re.search(r"const PRELOADED_BOOKS = (\[.*\]);", current, re.DOTALL)
    if m:
        books = json.loads(m.group(1))
        books.append(book)
        new_data = f"const PRELOADED_BOOKS = {json.dumps(books, ensure_ascii=False, indent=2)};\n"
        with open(DATA_JS, "w", encoding="utf-8") as f:
            f.write(new_data)
        print(f"Successfully added '{book['title']}' to data.js!")
    else:
        print("Error: Could not parse data.js format.")

if __name__ == "__main__":
    main()
