#!/usr/bin/env python3
import urllib.request
import urllib.parse
import json
import random
import re
import ssl
import time

# Bypass SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

LANG_DIR = "/Users/alexandermacmillan/Google Drive/My Drive/Personal/Languages"
rus_path = f"{LANG_DIR}/kavkazsky_plennik_russian.txt"

def clean_html(html):
    cleaned = re.sub(r'<[^<]+?>', '', html)
    cleaned = re.sub(r'\[with.*?\]|\.mw-.*', '', cleaned)
    return cleaned.strip()

def lookup(word, original_case, is_retry=False):
    # Match browser logic: first query lowercase, then original case on 404
    word_encoded = urllib.parse.quote(word)
    url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{word_encoded}"
    
    headers = {
        'User-Agent': 'SlovoReaderTest/1.0 (anmacmillan@gmail.com; educational study)'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            ru_data = data.get('ru') or data.get('en') or list(data.values())[0]
            if not ru_data:
                return False, "No Russian data block"
            
            first_block = ru_data[0]
            first_def_html = first_block['definitions'][0]['definition']
            part_of_speech = first_block.get('partOfSpeech', 'Word')
            
            # Check if this definition is an inflection link referring to another page
            lemma_match = re.search(r'href="/wiki/([^"#]+)(?:#[Rr]ussian)?\"', first_def_html)
            
            if lemma_match:
                lemma = urllib.parse.unquote(lemma_match.group(1))
                if re.search(r'[а-яёА-ЯЁ]', lemma) and lemma.lower() != word.lower():
                    # Secondary lookup for base lemma
                    time.sleep(0.5) # small delay before secondary fetch
                    lemma_encoded = urllib.parse.quote(lemma)
                    lemma_url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{lemma_encoded}"
                    try:
                        lemma_req = urllib.request.Request(lemma_url, headers=headers)
                        with urllib.request.urlopen(lemma_req, timeout=8) as l_resp:
                            l_data = json.loads(l_resp.read().decode('utf-8'))
                            l_ru = l_data.get('ru') or list(l_data.values())[0]
                            l_first_def = clean_html(l_ru[0]['definitions'][0]['definition'])
                            return True, f"({part_of_speech} of {lemma}) → Translation: {l_first_def}"
                    except Exception as le:
                        return True, f"({part_of_speech} of {lemma}) [Lemma fetch failed: {le}]"
            
            return True, f"({part_of_speech}) → Translation: {clean_html(first_def_html)}"
            
    except urllib.error.HTTPError as e:
        if e.code == 404 and not is_retry and original_case != word:
            # Retry with original case (for proper nouns like Жилин)
            time.sleep(0.5)
            return lookup(original_case, original_case, is_retry=True)
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    with open(rus_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Find all words
    words = re.findall(r'[а-яёА-ЯЁ\-]+', text)
    cleaned_words = []
    
    # Store original text casings
    original_casings = {}
    for w in words:
        w_clean = w.replace('\u0301', '').strip()
        if len(w_clean) >= 3:
            cleaned_words.append(w_clean)
            original_casings[w_clean.lower()] = w_clean

    unique_words_lower = list(set([w.lower() for w in cleaned_words]))
    print(f"Total unique words in story: {len(unique_words_lower)}")

    # Pick 30 random words
    random.seed(42)  # Fixed seed to ensure repeatable test runs
    sample_words_lower = random.sample(unique_words_lower, 30)
    
    print("Selected 30 random words for testing:")
    print(", ".join(original_casings[w] for w in sample_words_lower) + "\n")

    success_count = 0
    results = []

    for i, word_lower in enumerate(sample_words_lower):
        original = original_casings[word_lower]
        print(f"[{i+1}/30] Testing '{original}' (query: '{word_lower}')... ", end="", flush=True)
        
        # Call lookup with lowercase first, passing the original case as fallback
        success, detail = lookup(word_lower, original)
        
        if success:
            success_count += 1
            print(f"SUCCESS {detail}")
        else:
            print(f"FAILED ({detail})")
            
        results.append((original, success, detail))
        time.sleep(1.0) # 1 second delay between words to satisfy rate limits

    rate = (success_count / 30) * 100
    print(f"\n======================================")
    print(f"TEST RESULTS: {success_count}/30 Successes")
    print(f"SUCCESS RATE: {rate:.1f}%")
    print(f"======================================")

if __name__ == "__main__":
    main()
