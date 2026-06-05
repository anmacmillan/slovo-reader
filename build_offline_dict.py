import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
import time
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

ssl._create_default_https_context = ssl._create_unverified_context

DB_PATH = "/Users/alexandermacmillan/Projects/slovo-reader/dict_cache.db"
DATA_JS = "/Users/alexandermacmillan/Projects/slovo-reader/data.js"
DICT_JS = "/Users/alexandermacmillan/Projects/slovo-reader/dictionary_data.js"

headers = {
    "User-Agent": "SlovoReaderOfflineCompiler/1.0 (anmacmillan@gmail.com)"
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS dict_cache (
            word TEXT PRIMARY KEY,
            definition TEXT,
            grammar TEXT,
            lemma TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_cached_words():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT word FROM dict_cache")
    words = {row[0] for row in c.fetchall()}
    conn.close()
    return words

def save_to_cache(word, definition, grammar, lemma=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO dict_cache VALUES (?, ?, ?, ?)", (word, definition, grammar, lemma))
    conn.commit()
    conn.close()

def fetch_wiktionary_raw(word):
    url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{urllib.parse.quote(word)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise e
    except Exception as e:
        raise e

def clean_html(html):
    return re.sub(r'<[^>]+>', '', html).strip()

def parse_definition_block(data, word):
    ru_data = data.get("ru") or data.get("en") or (list(data.values())[0] if data else None)
    if not ru_data:
        return None, None, None

    pos_list = []
    definitions = []
    lemma = None

    for block in ru_data:
        pos = block.get("partOfSpeech", "")
        if pos and pos not in pos_list:
            pos_list.append(pos)
        
        for def_obj in block.get("definitions", []):
            def_text = clean_html(def_obj.get("definition", ""))
            if def_text and def_text not in definitions:
                definitions.append(def_text)
            
            # Check for form-of link to detect lemma
            m = re.search(r'href="/wiki/([^"#]+)"', def_obj.get("definition", ""))
            if m and not lemma:
                candidate = urllib.parse.unquote(m.group(1)).replace("_", " ")
                if re.fullmatch(r'[а-яёА-ЯЁ\-]+', candidate):
                    lemma = candidate.lower()

    pos_str = " / ".join(pos_list)
    brief_def = "; ".join(definitions[:2])
    return brief_def, pos_str, lemma

def process_word(word):
    try:
        # First attempt
        data = fetch_wiktionary_raw(word)
        if not data:
            # Try cleaning trailing punctuation or non-russian
            clean_w = re.sub(r'[^а-яё\-]', '', word)
            if clean_w and clean_w != word:
                data = fetch_wiktionary_raw(clean_w)
                word = clean_w
        
        if not data:
            return word, None, None, None

        brief_def, pos_str, lemma = parse_definition_block(data, word)
        
        # If there is a lemma that is different from current word, fetch the lemma's definition
        if lemma and lemma != word:
            lemma_data = fetch_wiktionary_raw(lemma)
            if lemma_data:
                l_def, l_pos, _ = parse_definition_block(lemma_data, lemma)
                if l_def:
                    brief_def = f"{brief_def} (form of {lemma}: {l_def})"
        
        return word, brief_def, pos_str, lemma
    except Exception as e:
        print(f"Error fetching {word}: {e}")
        return word, False, None, None

def get_unique_words():
    with open(DATA_JS, "r", encoding="utf-8") as f:
        content = f.read()

    prefix = "const PRELOADED_BOOKS = "
    json_str = content[len(prefix):]
    if json_str.endswith(";\n"):
        json_str = json_str[:-2]
    elif json_str.endswith(";"):
        json_str = json_str[:-1]

    books = json.loads(json_str)
    
    unique_words = set()
    for book in books:
        for chapter in book.get("chapters", []):
            for para in chapter.get("russian", []):
                words = re.findall(r'[а-яёА-ЯЁ\-]+', para)
                for w in words:
                    cleaned = w.lower().strip("-")
                    if cleaned:
                        unique_words.add(cleaned)
    return sorted(list(unique_words))

def export_dict_js():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT word, definition, grammar FROM dict_cache WHERE definition IS NOT NULL AND definition != ''")
    rows = c.fetchall()
    conn.close()

    dict_data = {}
    for r in rows:
        dict_data[r[0]] = {
            "def": r[1],
            "grammar": r[2]
        }

    with open(DICT_JS, "w", encoding="utf-8") as f:
        f.write("const LOCAL_DICTIONARY = ")
        json.dump(dict_data, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    print(f"Exported {len(dict_data)} entries to {DICT_JS}")

def main():
    init_db()
    cached = get_cached_words()
    all_words = get_unique_words()
    
    to_fetch = [w for w in all_words if w not in cached]
    print(f"Total words: {len(all_words)}, Already cached: {len(cached)}, To fetch: {len(to_fetch)}")

    if not to_fetch:
        export_dict_js()
        return
    completed = 0
    consecutive_429 = 0
    
    print("Starting polite sequential crawl...")
    for w in to_fetch:
        # Check consecutive 429 count to abort if blocked permanently
        if consecutive_429 >= 10:
            print("Aborting crawl due to persistent 429 limits. Try running again later.")
            break
            
        res_word, brief_def, pos_str, lemma = process_word(w)
        
        if brief_def is False:
            # Indicates network/API error
            print(f"Failed to fetch {w} (network/rate limit). Sleeping 3s...")
            consecutive_429 += 1
            time.sleep(3.0)
            continue
            
        consecutive_429 = 0
        save_to_cache(res_word, brief_def, pos_str, lemma or "")
        
        completed += 1
        if completed % 10 == 0:
            print(f"Progress: cached {completed}/{len(to_fetch)} new words...")
        if completed % 50 == 0:
            export_dict_js()
            
        # Throttling delay between requests to be polite (5 requests per second max)
        time.sleep(0.25)

    export_dict_js()

if __name__ == "__main__":
    main()
