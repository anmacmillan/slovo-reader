import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
import time
import ssl
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymorphy3

ssl._create_default_https_context = ssl._create_unverified_context

DB_PATH = "/Users/alexandermacmillan/Projects/slovo-reader/dict_cache.db"
DATA_JS = "/Users/alexandermacmillan/Projects/slovo-reader/data.js"
DICT_JS = "/Users/alexandermacmillan/Projects/slovo-reader/dictionary_data.js"

headers = {
    "User-Agent": "SlovoReaderOfflineCompiler/2.0 (anmacmillan@gmail.com)"
}

CSV_URLS = {
    "nouns": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/nouns.csv",
    "verbs": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/verbs.csv",
    "adjectives": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/adjectives.csv",
    "others": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/others.csv"
}

POS_MAP = {
    'NOUN': 'noun',
    'ADJF': 'adjective',
    'ADJS': 'short adjective',
    'COMP': 'comparative',
    'VERB': 'verb',
    'INFN': 'infinitive',
    'PRTF': 'participle',
    'PRTS': 'short participle',
    'GRND': 'gerund',
    'NUMR': 'numeral',
    'ADVB': 'adverb',
    'NPRO': 'pronoun',
    'PRED': 'predicative',
    'PREP': 'preposition',
    'CONJ': 'conjunction',
    'PRCL': 'particle',
    'INTJ': 'interjection'
}

TAG_MAP = {
    'masc': 'masculine',
    'femn': 'feminine',
    'neut': 'neuter',
    'sing': 'singular',
    'plur': 'plural',
    'nomn': 'nominative',
    'gent': 'genitive',
    'datv': 'dative',
    'accs': 'accusative',
    'ablt': 'instrumental',
    'loct': 'prepositional',
    'voct': 'vocative',
    'pres': 'present',
    'past': 'past',
    'futr': 'future',
    'perf': 'perfective',
    'impf': 'imperfective',
    'actv': 'active',
    'pssv': 'passive',
    'intr': 'intransitive',
    'tran': 'transitive'
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
    c.execute("SELECT word, definition, grammar, lemma FROM dict_cache")
    rows = c.fetchall()
    conn.close()
    
    cache = {}
    for row in rows:
        cache[row[0]] = {
            "definition": row[1],
            "grammar": row[2],
            "lemma": row[3]
        }
    return cache

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
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise e
    except Exception as e:
        raise e

def clean_html(html):
    return re.sub(r'<[^>]+>', '', html).strip()

def parse_definition_block(data):
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
            
            # Check links to detect lemma
            links = re.findall(r'href="/wiki/([^"#\s]+)(?:#[^"]+)?"', def_obj.get("definition", ""))
            for link in links:
                candidate = urllib.parse.unquote(link).replace("_", " ")
                if re.fullmatch(r'[а-яёА-ЯЁ\-]+', candidate):
                    lemma = candidate.lower()
                    break

    pos_str = " / ".join(pos_list)
    brief_def = "; ".join(definitions[:2])
    return brief_def, pos_str, lemma

def fetch_lemma_from_wiktionary(lemma):
    try:
        data = fetch_wiktionary_raw(lemma)
        if not data:
            clean_w = re.sub(r'[^а-яё\-]', '', lemma)
            if clean_w and clean_w != lemma:
                data = fetch_wiktionary_raw(clean_w)
                lemma = clean_w
        
        if not data:
            return lemma, None, None, None

        brief_def, pos_str, nested_lemma = parse_definition_block(data)
        
        if nested_lemma and nested_lemma != lemma:
            lemma_data = fetch_wiktionary_raw(nested_lemma)
            if lemma_data:
                l_def, l_pos, _ = parse_definition_block(lemma_data)
                if l_def:
                    brief_def = f"{brief_def} (form of {nested_lemma}: {l_def})"
        
        return lemma, brief_def, pos_str, nested_lemma
    except Exception as e:
        if "429" in str(e):
            return lemma, "429", None, None
        return lemma, None, None, None

def download_openrussian_csvs():
    open_russian_db = {}
    
    for cat, url in CSV_URLS.items():
        print(f"Downloading OpenRussian {cat} dataset...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SlovoReaderCompiler/2.0"})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8').splitlines()
                reader = csv.DictReader(content, delimiter='\t')
                
                for row in reader:
                    word = row.get("bare")
                    if not word:
                        continue
                    word = word.lower().strip()
                    
                    en_trans = row.get("translations_en", "").strip()
                    if not en_trans:
                        continue
                        
                    # Extract grammar helper
                    grammar_info = []
                    if cat == "nouns":
                        g = row.get("gender")
                        if g:
                            grammar_info.append(f"noun ({g})")
                        if row.get("animate") == "1":
                            grammar_info.append("animate")
                    elif cat == "verbs":
                        asp = row.get("aspect")
                        if asp:
                            grammar_info.append(f"verb ({asp})")
                    elif cat == "adjectives":
                        grammar_info.append("adjective")
                    else:
                        grammar_info.append("other")
                        
                    grammar_str = ", ".join(grammar_info)
                    
                    # Store
                    if word not in open_russian_db:
                        open_russian_db[word] = (en_trans, grammar_str)
        except Exception as e:
            print(f"Failed to download or parse {cat} CSV: {e}")
            
    return open_russian_db

def translate_pymorphy_tag(tag):
    parts = []
    pos = tag.POS
    if pos in POS_MAP:
        parts.append(POS_MAP[pos])
    for key in ['perf', 'impf', 'pres', 'past', 'futr', 'actv', 'pssv', 'tran', 'intr']:
        if key in tag.grammemes:
            parts.append(TAG_MAP[key])
    for key in ['masc', 'femn', 'neut', 'sing', 'plur', 'nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']:
        if key in tag.grammemes:
            parts.append(TAG_MAP[key])
    return ", ".join(parts)

def get_unique_word_forms():
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

def main():
    init_db()
    
    morph = pymorphy3.MorphAnalyzer()
    
    # 1. Get all unique word forms from books
    print("Extracting unique word forms from books...")
    word_forms = get_unique_word_forms()
    print(f"Total unique word forms in books: {len(word_forms)}")
    
    # 2. Analyze word forms to get lemmas
    print("Lemmatizing all word forms...")
    forms_to_lemmas = {}
    forms_to_grammar = {}
    all_lemmas = set()
    
    for wf in word_forms:
        parsed = morph.parse(wf)
        if parsed:
            p = parsed[0]
            lemma = p.normal_form
            forms_to_lemmas[wf] = lemma
            forms_to_grammar[wf] = translate_pymorphy_tag(p.tag)
            all_lemmas.add(lemma)
        else:
            forms_to_lemmas[wf] = wf
            forms_to_grammar[wf] = "unknown"
            all_lemmas.add(wf)
            
    print(f"Total unique lemmas: {len(all_lemmas)}")
    
    # 3. Download OpenRussian dictionary to populate cache offline
    open_russian_db = download_openrussian_csvs()
    print(f"Loaded {len(open_russian_db)} words from OpenRussian dataset.")
    
    # Check cache
    cache = get_cached_words()
    print(f"Loaded {len(cache)} words from local sqlite cache.")
    
    # 4. Resolve missing lemmas using OpenRussian first
    missing_lemmas = sorted(list(all_lemmas - cache.keys()))
    print(f"Lemmas missing from local cache: {len(missing_lemmas)}")
    
    still_missing = []
    resolved_count = 0
    
    for lem in missing_lemmas:
        if lem in open_russian_db:
            trans, grammar = open_russian_db[lem]
            save_to_cache(lem, trans, grammar, "")
            resolved_count += 1
        else:
            still_missing.append(lem)
            
    print(f"Resolved {resolved_count} missing lemmas using OpenRussian dataset.")
    print(f"Lemmas still missing (will fetch from Wiktionary): {len(still_missing)}")
    
    # 5. Fetch the remaining few missing lemmas from Wiktionary sequentially
    if still_missing:
        print(f"Fetching {len(still_missing)} remaining lemmas from Wiktionary sequentially (polite crawl)...")
        completed = 0
        for lem in still_missing:
            # Polite crawl
            res_lem, brief_def, pos_str, nested_lemma = fetch_lemma_from_wiktionary(lem)
            
            if brief_def == "429":
                print("Rate limited by Wiktionary. Sleeping 3s...")
                time.sleep(3.0)
                res_lem, brief_def, pos_str, nested_lemma = fetch_lemma_from_wiktionary(lem)
                
            if brief_def and brief_def != "429":
                save_to_cache(res_lem, brief_def, pos_str or "", nested_lemma or "")
                completed += 1
            else:
                # Cache negative result to avoid re-querying
                save_to_cache(lem, "", "", "")
                
            if completed % 10 == 0 and completed > 0:
                print(f"Fetched {completed}/{len(still_missing)} from Wiktionary...")
            time.sleep(0.3)
            
        print("Completed Wiktionary fallbacks.")
        
    # 6. Build final dictionary_data.js containing ALL word forms in the books
    print("Building dictionary_data.js...")
    
    # Refresh cache
    cache = get_cached_words()
    
    final_dict = {}
    for wf in word_forms:
        lemma = forms_to_lemmas[wf]
        grammar = forms_to_grammar[wf]
        
        # Determine definition
        wf_entry = cache.get(wf)
        lemma_entry = cache.get(lemma)
        
        definition = None
        if wf_entry and wf_entry["definition"]:
            definition = wf_entry["definition"]
        elif lemma_entry and lemma_entry["definition"]:
            if wf != lemma:
                definition = f"(form of {lemma}: {lemma_entry['definition']})"
            else:
                definition = lemma_entry["definition"]
        
        if not definition:
            if wf != lemma:
                definition = f"(form of {lemma})"
            else:
                definition = ""
                
        final_dict[wf] = {
            "def": definition,
            "grammar": grammar
        }
        
    with open(DICT_JS, "w", encoding="utf-8") as f:
        f.write("const LOCAL_DICTIONARY = ")
        json.dump(final_dict, f, ensure_ascii=False, indent=2)
        f.write(";\n")
        
    print(f"Exported {len(final_dict)} word forms to {DICT_JS} (size: {os.path.getsize(DICT_JS) // 1024} KB)")

if __name__ == "__main__":
    main()
