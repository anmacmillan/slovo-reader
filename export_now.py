import os
import re
import json
import sqlite3
import pymorphy3

DB_PATH = "/Users/alexandermacmillan/Projects/slovo-reader/dict_cache.db"
DATA_JS = "/Users/alexandermacmillan/Projects/slovo-reader/data.js"
DICT_JS = "/Users/alexandermacmillan/Projects/slovo-reader/dictionary_data.js"

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
    morph = pymorphy3.MorphAnalyzer()
    word_forms = get_unique_word_forms()
    print(f"Exporting dictionary for {len(word_forms)} unique word forms...")
    
    forms_to_lemmas = {}
    forms_to_grammar = {}
    for wf in word_forms:
        parsed = morph.parse(wf)
        if parsed:
            p = parsed[0]
            forms_to_lemmas[wf] = p.normal_form
            forms_to_grammar[wf] = translate_pymorphy_tag(p.tag)
        else:
            forms_to_lemmas[wf] = wf
            forms_to_grammar[wf] = "unknown"
            
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
        
    print(f"Successfully exported {len(final_dict)} words to {DICT_JS}")

if __name__ == "__main__":
    main()
