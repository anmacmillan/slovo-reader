import json
import re

DICT_JS = "/Users/alexandermacmillan/Projects/slovo-reader/dictionary_data.js"
DATA_JS = "/Users/alexandermacmillan/Projects/slovo-reader/data.js"

def main():
    # Load dictionary
    with open(DICT_JS, "r", encoding="utf-8") as f:
        text = f.read()
    prefix = "const LOCAL_DICTIONARY = "
    d = json.loads(text[len(prefix):].rstrip(";\n"))
    
    # Load books
    with open(DATA_JS, "r", encoding="utf-8") as f:
        content = f.read()
    prefix_books = "const PRELOADED_BOOKS = "
    json_str = content[len(prefix_books):].strip().rstrip(";")
    books = json.loads(json_str)
    
    # Get all unique words from Lermontov specifically
    lermontov_words = set()
    for book in books:
        if "Лермонтов" in book.get("title", "") or "Герой нашего времени" in book.get("title", "") or "Бэла" in book.get("title", "") or "Кавказский пленник" in book.get("title", "") or True:
            # Check all books just to be thorough
            for chapter in book.get("chapters", []):
                for para in chapter.get("russian", []):
                    words = re.findall(r'[а-яёА-ЯЁ\-]+', para)
                    for w in words:
                        cleaned = w.lower().strip("-")
                        if cleaned:
                            lermontov_words.add(cleaned)
                            
    print(f"Total unique words in corpus: {len(lermontov_words)}")
    
    # Check for gaps
    gaps = []
    for w in sorted(list(lermontov_words)):
        entry = d.get(w)
        if not entry:
            gaps.append((w, "Not in dictionary_data.js"))
            continue
            
        definition = entry.get("def", "")
        # Checks if definition is empty, or just "(form of X)" with no colon or meaning inside
        if not definition or definition.strip() == "" or (definition.startswith("(form of") and ":" not in definition):
            gaps.append((w, definition))
            
    print(f"Total words with missing definitions / gaps: {len(gaps)}")
    print("\nFirst 50 gaps:")
    for w, val in gaps[:50]:
        print(f"  {w} : {val}")
        
    # Write gaps to a JSON for processing
    with open("/Users/alexandermacmillan/Projects/slovo-reader/gaps.json", "w", encoding="utf-8") as f:
        json.dump(gaps, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
