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

CSV_URLS = {
    "nouns": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/nouns.csv",
    "verbs": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/verbs.csv",
    "adjectives": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/adjectives.csv",
    "others": "https://raw.githubusercontent.com/Badestrand/russian-dictionary/master/others.csv"
}

headers = {
    "User-Agent": "SlovoReaderOfflineCompiler/3.0 (anmacmillan@gmail.com)"
}

POS_MAP = {
    'NOUN': 'noun', 'ADJF': 'adjective', 'ADJS': 'short adjective',
    'COMP': 'comparative', 'VERB': 'verb', 'INFN': 'infinitive',
    'PRTF': 'participle', 'PRTS': 'short participle', 'GRND': 'gerund',
    'NUMR': 'numeral', 'ADVB': 'adverb', 'NPRO': 'pronoun',
    'PRED': 'predicative', 'PREP': 'preposition', 'CONJ': 'conjunction',
    'PRCL': 'particle', 'INTJ': 'interjection'
}

TAG_MAP = {
    'masc': 'masculine', 'femn': 'feminine', 'neut': 'neuter',
    'sing': 'singular', 'plur': 'plural', 'nomn': 'nominative',
    'gent': 'genitive', 'datv': 'dative', 'accs': 'accusative',
    'ablt': 'instrumental', 'loct': 'prepositional', 'voct': 'vocative',
    'pres': 'present', 'past': 'past', 'futr': 'future',
    'perf': 'perfective', 'impf': 'imperfective', 'actv': 'active',
    'pssv': 'passive', 'intr': 'intransitive', 'tran': 'transitive'
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

def download_openrussian_csvs():
    open_russian_db = {}
    for cat, url in CSV_URLS.items():
        print(f"Downloading OpenRussian {cat} dataset...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SlovoReaderCompiler/3.0"})
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
                    grammar_info = []
                    if cat == "nouns":
                        g = row.get("gender")
                        if g: grammar_info.append(f"noun ({g})")
                    elif cat == "verbs":
                        asp = row.get("aspect")
                        if asp: grammar_info.append(f"verb ({asp})")
                    elif cat == "adjectives":
                        grammar_info.append("adjective")
                    else:
                        grammar_info.append("other")
                    grammar_str = ", ".join(grammar_info)
                    if word not in open_russian_db:
                        open_russian_db[word] = (en_trans, grammar_str)
        except Exception as e:
            print(f"Failed to download/parse {cat} CSV: {e}")
    return open_russian_db

def find_in_open_russian(lem, open_russian_db):
    if lem in open_russian_db:
        return open_russian_db[lem]
    
    # Check spelling variants
    variants = []
    if lem.endswith('ие'):
        variants.append(lem[:-2] + 'ье')
    elif lem.endswith('ье'):
        variants.append(lem[:-2] + 'ие')
    if lem.endswith('ия'):
        variants.append(lem[:-2] + 'ья')
    elif lem.endswith('ья'):
        variants.append(lem[:-2] + 'ия')
    if 'ё' in lem:
        variants.append(lem.replace('ё', 'е'))
    if 'е' in lem:
        variants.append(lem.replace('е', 'ё'))
        
    for var in variants:
        if var in open_russian_db:
            return open_russian_db[var]
            
    # Adjective/Noun variants
    if lem.endswith(('ой', 'ый', 'ий')):
        for ending in ['ые', 'ие']:
            cand = lem[:-2] + ending
            if cand in open_russian_db:
                return open_russian_db[cand]
    if lem.endswith(('ые', 'ие')):
        for ending in ['ый', 'ий', 'ой']:
            cand = lem[:-2] + ending
            if cand in open_russian_db:
                return open_russian_db[cand]
    return None

def fetch_wiktionary_raw(word):
    url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{urllib.parse.quote(word)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return None

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
            links = re.findall(r'href="/wiki/([^"#\s]+)(?:#[^"]+)?"', def_obj.get("definition", ""))
            for link in links:
                candidate = urllib.parse.unquote(link).replace("_", " ")
                if re.fullmatch(r'[а-яёА-ЯЁ\-]+', candidate):
                    lemma = candidate.lower()
                    break
    pos_str = " / ".join(pos_list)
    brief_def = "; ".join(definitions[:2])
    return brief_def, pos_str, lemma

def force_fetch_word(word):
    # Try fetching the word/lemma from Wiktionary directly
    data = fetch_wiktionary_raw(word)
    if not data:
        return word, None, None, None
    brief_def, pos_str, nested_lemma = parse_definition_block(data)
    
    if nested_lemma and nested_lemma != word:
        # Check if nested lemma has definition
        lemma_data = fetch_wiktionary_raw(nested_lemma)
        if lemma_data:
            l_def, l_pos, _ = parse_definition_block(lemma_data)
            if l_def:
                brief_def = f"{brief_def} (form of {nested_lemma}: {l_def})"
    return word, brief_def, pos_str, nested_lemma

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
    json_str = content[len(prefix):].strip().rstrip(";")
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
    
    # Load all word forms
    word_forms = get_unique_word_forms()
    print(f"Total unique word forms in books: {len(word_forms)}")
    
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
            
    # Load OpenRussian DB
    open_russian_db = download_openrussian_csvs()
    
    # Load Cache
    cache = get_cached_words()
    
    # Find gaps
    gaps_lemmas = set()
    for lem in all_lemmas:
        entry = cache.get(lem)
        if not entry or not entry["definition"] or (entry["definition"].startswith("(form of") and ":" not in entry["definition"]):
            gaps_lemmas.add(lem)
            
    print(f"Initial gaps count (lemmas): {len(gaps_lemmas)}")
    
    # Try resolving gaps using OpenRussian spelling/adjective variants
    resolved_or = 0
    remaining_gaps = []
    for lem in sorted(list(gaps_lemmas)):
        or_match = find_in_open_russian(lem, open_russian_db)
        if or_match:
            trans, grammar = or_match
            save_to_cache(lem, trans, grammar, "")
            resolved_or += 1
        else:
            remaining_gaps.append(lem)
            
    print(f"Resolved {resolved_or} gaps using OpenRussian variants.")
    print(f"Remaining gaps to brute-force fetch from Wiktionary: {len(remaining_gaps)}")
    
    # Brute-force fetch from Wiktionary in parallel (15 threads)
    if remaining_gaps:
        print(f"Fetching {len(remaining_gaps)} lemmas concurrently from Wiktionary...")
        completed = 0
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(force_fetch_word, lem): lem for lem in remaining_gaps}
            for fut in as_completed(futures):
                lem = futures[fut]
                try:
                    word, brief_def, pos_str, nested_lemma = fut.result()
                    if brief_def:
                        save_to_cache(word, brief_def, pos_str or "", nested_lemma or "")
                    else:
                        # Negative cache so we don't request again
                        save_to_cache(word, "", "", "")
                    completed += 1
                    if completed % 50 == 0:
                        print(f"Wiktionary Progress: {completed}/{len(remaining_gaps)} fetched...")
                except Exception as exc:
                    pass
                time.sleep(0.05)
                
    # Re-export dictionary
    print("Re-exporting dictionary_data.js...")
    cache = get_cached_words()
    final_dict = {}
    for wf in word_forms:
        lemma = forms_to_lemmas[wf]
        grammar = forms_to_grammar[wf]
        
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
        
    print(f"Successfully compiled dictionary with {len(final_dict)} words.")

if __name__ == "__main__":
    main()
