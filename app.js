/* -----------------------------------------------------------------------------
   SLOVO READER — APP LOGIC
   ----------------------------------------------------------------------------- */

// App State
const state = {
  books: [],
  currentBookIndex: 0,
  currentChapterIndex: 0,
  vocabList: [],
  synth: window.speechSynthesis,
  ruVoice: null,
  activeAudioUtterance: null
};

// LocalStorage Keys
const STORAGE_KEYS = {
  VOCAB: "slovo_vocab_notebook",
  CUSTOM_BOOKS: "slovo_custom_library",
  THEME: "slovo_active_theme",
  PROGRESS: "slovo_reading_progress"
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadVocabList();
  initVoices();
  loadLibrary();
  bindEvents();
});

// ── Theme Management ──────────────────────────────────────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem(STORAGE_KEYS.THEME) || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(STORAGE_KEYS.THEME, next);
}

// ── Speech Synthesis Voices ───────────────────────────────────────────────────
function initVoices() {
  const setVoice = () => {
    const voices = state.synth.getVoices();
    // Prioritize high-quality Russian voices
    state.ruVoice = voices.find(v => v.lang.startsWith("ru-RU") || v.lang.startsWith("ru")) || null;
  };
  setVoice();
  if (state.synth.onvoiceschanged !== undefined) {
    state.synth.onvoiceschanged = setVoice;
  }
}

function speakText(text, lang = "ru-RU") {
  if (state.synth.speaking) {
    state.synth.cancel();
  }

  const speedSelect = document.getElementById("speed-select");
  const rate = speedSelect ? parseFloat(speedSelect.value) : 0.9;
  
  const utterance = new SpeechSynthesisUtterance(text);
  if (lang.startsWith("ru") && state.ruVoice) {
    utterance.voice = state.ruVoice;
  } else {
    utterance.lang = lang;
  }
  utterance.rate = rate;
  
  state.activeAudioUtterance = utterance;
  state.synth.speak(utterance);
}

// ── Library Loading ───────────────────────────────────────────────────────────
function loadLibrary() {
  state.books = [...PRELOADED_BOOKS];
  
  // Load custom library from localStorage
  const savedCustom = localStorage.getItem(STORAGE_KEYS.CUSTOM_BOOKS);
  if (savedCustom) {
    try {
      const customBooks = JSON.parse(savedCustom);
      state.books = [...state.books, ...customBooks];
    } catch (e) {
      console.error("Error loading custom books:", e);
    }
  }

  populateBookSelector();
  loadBook(0);
}

function populateBookSelector() {
  const bookSelect = document.getElementById("book-select");
  bookSelect.innerHTML = "";
  state.books.forEach((book, idx) => {
    const opt = document.createElement("option");
    opt.value = idx;
    opt.textContent = `${book.author} — ${book.title}`;
    bookSelect.appendChild(opt);
  });
}

function loadBook(bookIdx) {
  state.currentBookIndex = parseInt(bookIdx);
  state.currentChapterIndex = 0;
  
  const book = state.books[state.currentBookIndex];
  
  // Populate Chapter Selector
  const chSelect = document.getElementById("chapter-select");
  chSelect.innerHTML = "";
  book.chapters.forEach((ch, idx) => {
    const opt = document.createElement("option");
    opt.value = idx;
    opt.textContent = ch.titleRus || `Глава ${ch.chapterNum}`;
    chSelect.appendChild(opt);
  });

  renderChapter();
}

// ── Parallel Sentence and Word Renderer ─────────────────────────────────────
function renderChapter() {
  const book = state.books[state.currentBookIndex];
  const chapter = book.chapters[state.currentChapterIndex];
  const container = document.getElementById("chunks-container");
  container.innerHTML = "";

  // Render Title
  const titleRow = document.createElement("div");
  titleRow.className = "chapter-row-title";
  titleRow.innerHTML = `
    <h2>${chapter.titleRus || "Глава"}</h2>
    <div style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 4px;">
      ${chapter.titleEng || ""}
    </div>
  `;
  container.appendChild(titleRow);

  // Render Parallel Chunks
  chapter.russian.forEach((rusChunkText, chunkIdx) => {
    const engChunkText = chapter.english[chunkIdx] || "";

    const row = document.createElement("div");
    row.className = "chunk-row";
    row.dataset.chunkIdx = chunkIdx;

    // Split chunks into sentences
    const rusSents = segmentSentences(rusChunkText);
    const engSents = segmentSentences(engChunkText);

    // Left Column (Russian)
    const rusCol = document.createElement("div");
    rusCol.className = "text-col rus-col";

    rusSents.forEach((sent, sentIdx) => {
      const sentSpan = document.createElement("span");
      sentSpan.className = "sentence-box";
      sentSpan.dataset.sentId = `ch-${chunkIdx}-s-${sentIdx}`;
      
      // Tokenize sentence into clickable word spans
      const words = tokenizeWords(sent);
      words.forEach(w => {
        if (w.isWord) {
          const wordSpan = document.createElement("span");
          wordSpan.className = "word-span";
          wordSpan.textContent = w.text;
          sentSpan.appendChild(wordSpan);
        } else {
          sentSpan.appendChild(document.createTextNode(w.text));
        }
      });

      // Add small TTS play button
      const playBtn = document.createElement("button");
      playBtn.className = "tts-play-btn";
      playBtn.innerHTML = "🔊";
      playBtn.title = "Speak sentence";
      playBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        speakText(sent);
      });
      sentSpan.appendChild(playBtn);

      rusCol.appendChild(sentSpan);
      rusCol.appendChild(document.createTextNode(" "));
    });

    // Right Column (English)
    const engCol = document.createElement("div");
    engCol.className = "text-col eng-col";

    engSents.forEach((sent, sentIdx) => {
      const sentSpan = document.createElement("span");
      sentSpan.className = "sentence-box";
      // Map sentIdx back to Russian sentIdx proportionally if count differs
      const mappedIdx = Math.min(sentIdx, rusSents.length - 1);
      sentSpan.dataset.sentId = `ch-${chunkIdx}-s-${mappedIdx}`;
      sentSpan.textContent = sent;
      
      engCol.appendChild(sentSpan);
      engCol.appendChild(document.createTextNode(" "));
    });

    row.appendChild(rusCol);
    row.appendChild(engCol);
    container.appendChild(row);
  });

  setupHoverHighlights();
  updateProgressBar();
}

// Sentence Segmenter (Basic RegExp for literature)
function segmentSentences(text) {
  if (!text) return [];
  // Splits by period, exclamation, or question marks followed by space or quote mark
  return text.split(/(?<=[.!?»])\s+/).map(s => s.trim()).filter(s => s.length > 0);
}

// Tokenizes sentence into words vs punctuation/spaces
function tokenizeWords(sentence) {
  const parts = [];
  // Regex matches Russian word tokens (including hyphenated ones) or punctuation
  const tokenRegex = /([а-яёА-ЯЁ\-]+)|([^а-яёА-ЯЁ\-]+)/g;
  let match;
  while ((match = tokenRegex.exec(sentence)) !== null) {
    if (match[1]) {
      parts.push({ isWord: true, text: match[1] });
    } else {
      parts.push({ isWord: false, text: match[2] });
    }
  }
  return parts;
}

// ── Hover Highlighting ────────────────────────────────────────────────────────
function setupHoverHighlights() {
  const sentenceBoxes = document.querySelectorAll(".sentence-box");

  sentenceBoxes.forEach(box => {
    const sentId = box.dataset.sentId;
    
    box.addEventListener("mouseenter", () => {
      // Find all matching sentence elements in this row
      document.querySelectorAll(`.sentence-box[data-sent-id="${sentId}"]`).forEach(el => {
        el.classList.add("active-sentence");
      });
    });

    box.addEventListener("mouseleave", () => {
      document.querySelectorAll(`.sentence-box[data-sent-id="${sentId}"]`).forEach(el => {
        el.classList.remove("active-sentence");
      });
    });
  });
}

// ── Word Interaction & Tooltip Dictionary ───────────────────────────────────
let activeWordSpan = null;

document.addEventListener("click", (e) => {
  const wordSpan = e.target.closest(".word-span");
  const tooltip = document.getElementById("word-tooltip");
  const dictDrawer = document.getElementById("dict-drawer");

  if (wordSpan) {
    e.stopPropagation();
    
    // Highlight active word
    if (activeWordSpan) {
      activeWordSpan.classList.remove("selected-word");
    }
    activeWordSpan = wordSpan;
    activeWordSpan.classList.add("selected-word");

    const rawWord = wordSpan.textContent;
    const cleanWord = rawWord.toLowerCase().replace(/[^а-яё\-]/g, "");

    // Position & Show Tooltip
    showTooltipLoading(wordSpan);
    fetchWiktionaryDetails(cleanWord, rawWord);
  } else if (!e.target.closest("#word-tooltip") && !e.target.closest("#dict-drawer")) {
    // Hide tooltip if clicked outside
    tooltip.classList.add("hidden");
    if (activeWordSpan) {
      activeWordSpan.classList.remove("selected-word");
      activeWordSpan = null;
    }
  }
});

function showTooltipLoading(anchorEl) {
  const tooltip = document.getElementById("word-tooltip");
  const content = document.getElementById("tooltip-content");
  
  content.innerHTML = `
    <div style="text-align: center; padding: 10px;">
      <span style="font-size: 0.85rem; color: var(--text-secondary);">🔍 Parsing grammar...</span>
    </div>
  `;
  
  tooltip.classList.remove("hidden");
  
  // Calculate tooltip placement
  const rect = anchorEl.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  
  const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
  
  let top = rect.bottom + scrollTop + 8;
  let left = rect.left + scrollLeft - (tooltipRect.width / 2) + (rect.width / 2);
  
  // Prevent clipping edges
  if (left < 10) left = 10;
  if (left + tooltipRect.width > window.innerWidth - 10) {
    left = window.innerWidth - tooltipRect.width - 10;
  }
  
  tooltip.style.top = `${top}px`;
  tooltip.style.left = `${left}px`;
}

function fetchWiktionaryDetails(lemma, originalText) {
  const content = document.getElementById("tooltip-content");
  const dictBody = document.getElementById("dict-body");

  // Clean original word and prepare retry forms
  const cleanOriginal = originalText.replace(/[^а-яёА-ЯЁ\-]/g, "");
  const cleanLower = cleanOriginal.toLowerCase();

  const queryApi = (wordToQuery, isRetry = false) => {
    // Wikimedia Wiktionary REST API for structured definitions
    const url = `https://en.wiktionary.org/api/rest_v1/page/definition/${encodeURIComponent(wordToQuery)}`;

    fetch(url)
      .then(r => {
        if (!r.ok) {
          throw new Error("404");
        }
        return r.json();
      })
      .then(data => {
        const ruData = data.ru || data.en || Object.values(data)[0];
        if (!ruData || ruData.length === 0) {
          throw new Error("No definition");
        }
        
        // Scan for a link to a base lemma inside the form-of definition HTML
        let detectedLemma = null;
        const tempDiv = document.createElement("div");
        
        for (const block of ruData) {
          for (const defObj of block.definitions) {
            tempDiv.innerHTML = defObj.definition;
            const link = tempDiv.querySelector(".form-of-definition-link a, .mention a, a[href*='/wiki/']");
            if (link) {
              const linkText = (link.textContent || link.innerText).trim();
              // Validate that the linked text contains Cyrillic (meaning it's the Russian lemma)
              if (/[а-яёА-ЯЁ]/.test(linkText)) {
                detectedLemma = linkText.replace(/\u0301/g, "").toLowerCase(); // strip accents and lowercase
                break;
              }
            }
          }
          if (detectedLemma) break;
        }

        // If an inflected form refers to a different base lemma, fetch its definition
        if (detectedLemma && detectedLemma !== cleanLower) {
          const lemmaUrl = `https://en.wiktionary.org/api/rest_v1/page/definition/${encodeURIComponent(detectedLemma)}`;
          fetch(lemmaUrl)
            .then(r => r.ok ? r.json() : null)
            .then(lemmaData => {
              let lemmaDefs = [];
              const cleanHtmlText = (html) => {
                const t = document.createElement("div");
                t.innerHTML = html;
                return t.textContent || t.innerText || "";
              };
              
              if (lemmaData && lemmaData.ru) {
                lemmaData.ru.forEach(b => {
                  b.definitions.slice(0, 2).forEach(d => {
                    const cleaned = cleanHtmlText(d.definition);
                    if (cleaned && !lemmaDefs.includes(cleaned)) {
                      lemmaDefs.push(cleaned);
                    }
                  });
                });
              }
              
              const translation = lemmaDefs.slice(0, 2).join("; ");
              renderRESTAnalysis(originalText, ruData, translation);
            })
            .catch(err => {
              renderRESTAnalysis(originalText, ruData);
            });
        } else {
          renderRESTAnalysis(originalText, ruData);
        }
      })
      .catch(err => {
        if (!isRetry && cleanOriginal !== wordToQuery) {
          // If lowercase query failed (e.g. proper nouns), try with original case
          queryApi(cleanOriginal, true);
        } else {
          console.error("REST Wiktionary lookup error for word:", originalText);
          showTooltipError(originalText, "No direct definition found in Wiktionary. (Russian words are grammar-sensitive).");
        }
      });
  };

  // Start with lowercase form
  queryApi(cleanLower);
}

function showTooltipError(word, msg) {
  const content = document.getElementById("tooltip-content");
  content.innerHTML = `
    <div class="tooltip-header">
      <h4>${word}</h4>
      <div class="tooltip-buttons">
        <button class="btn-tooltip-action" id="tts-word-btn" title="Speak word">🔊</button>
        <button class="btn-tooltip-action" id="save-word-btn" title="Save word">➕</button>
      </div>
    </div>
    <div class="tooltip-definition" style="color: #ef4444;">
      ${msg}
    </div>
  `;
  
  // Bind actions
  document.getElementById("tts-word-btn").addEventListener("click", () => speakText(word));
  document.getElementById("save-word-btn").addEventListener("click", () => saveWordToVocab(word, "Definition not found. Custom card.", "Unknown"));
}

function renderRESTAnalysis(originalText, ruData, lemmaTranslation = null) {
  const content = document.getElementById("tooltip-content");
  const dictBody = document.getElementById("dict-body");

  // Helper to strip HTML tags from definition
  const cleanHtml = (html) => {
    const temp = document.createElement("div");
    temp.innerHTML = html;
    return temp.textContent || temp.innerText || "";
  };

  let tooltipPosList = [];
  let tooltipDefsList = [];
  let detailedCardHtml = "";

  ruData.forEach((block) => {
    const pos = block.partOfSpeech;
    if (!tooltipPosList.includes(pos)) {
      tooltipPosList.push(pos);
    }

    // Extract first 2 definitions for the tooltip
    block.definitions.slice(0, 2).forEach(defObj => {
      const cleanDef = cleanHtml(defObj.definition);
      if (cleanDef && !tooltipDefsList.includes(cleanDef)) {
        tooltipDefsList.push(cleanDef);
      }
    });

    // Compile detailed definitions list for sidebar
    const cleanDefs = block.definitions.map(d => `<li>${cleanHtml(d.definition)}</li>`).join("");
    detailedCardHtml += `
      <div class="dict-body-section" style="margin-top: 14px;">
        <div class="dict-section-title" style="color: var(--accent-text); font-weight: 700;">${pos}</div>
        <ol class="dict-def-list" style="margin-left: 20px; margin-top: 6px;">
          ${cleanDefs}
        </ol>
      </div>
    `;
  });

  const posString = tooltipPosList.join(" / ");
  const briefDef = tooltipDefsList.slice(0, 2).join("; ");

  let meaningHtml = "";
  if (lemmaTranslation) {
    meaningHtml = `<div class="tooltip-definition" style="border-top: 1px dashed var(--border-color); padding-top: 6px; font-weight: 600; color: var(--text-primary);">Translation: ${lemmaTranslation}</div>`;
    
    detailedCardHtml += `
      <div class="dict-body-section" style="margin-top: 14px; border-top: 1px solid var(--border-color); padding-top: 8px;">
        <div class="dict-section-title" style="color: var(--accent-secondary); font-weight: 700;">Base Lemma Meaning</div>
        <p style="font-size: 0.95rem; color: var(--text-primary); margin-top: 4px;"><strong>${lemmaTranslation}</strong></p>
      </div>
    `;
  }

  // Render tooltip bubble
  content.innerHTML = `
    <div class="tooltip-header">
      <h4>${originalText}</h4>
      <div class="tooltip-buttons">
        <button class="btn-tooltip-action" id="tts-word-btn" title="Speak word">🔊</button>
        <button class="btn-tooltip-action" id="save-word-btn" title="Save word">➕</button>
        <button class="btn-tooltip-action" id="more-dict-btn" title="Detailed Analysis">🔍</button>
      </div>
    </div>
    <div class="tooltip-grammar">${posString}</div>
    <div class="tooltip-definition">${briefDef}</div>
    ${meaningHtml}
  `;

  // Render analysis sidebar card
  dictBody.innerHTML = `
    <div class="dict-entry-card">
      <div class="dict-entry-header" style="border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
        <div class="dict-word-text">${originalText}</div>
        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
          Grammar: <strong>${posString}</strong>
        </div>
      </div>
      ${detailedCardHtml}
    </div>
  `;

  // Bind actions
  document.getElementById("tts-word-btn").addEventListener("click", () => speakText(originalText));
  document.getElementById("save-word-btn").addEventListener("click", () => {
    saveWordToVocab(originalText, lemmaTranslation ? `${briefDef} (${lemmaTranslation})` : briefDef, posString);
  });
  document.getElementById("more-dict-btn").addEventListener("click", () => {
    document.getElementById("dict-drawer").classList.add("open");
    document.getElementById("vocab-drawer").classList.remove("open");
  });
}

// ── Vocabulary Notebook ──────────────────────────────────────────────────────
function loadVocabList() {
  const saved = localStorage.getItem(STORAGE_KEYS.VOCAB);
  if (saved) {
    try {
      state.vocabList = JSON.parse(saved);
    } catch (e) {
      console.error(e);
      state.vocabList = [];
    }
  }
  updateVocabUI();
}

function saveWordToVocab(word, definition, grammar) {
  // Prevent duplicate additions
  if (state.vocabList.some(item => item.word.toLowerCase() === word.toLowerCase())) {
    alert(`"${word}" is already saved in your notebook.`);
    return;
  }

  const newItem = {
    word: word,
    definition: definition,
    grammar: grammar,
    timestamp: Date.now()
  };

  state.vocabList.unshift(newItem);
  localStorage.setItem(STORAGE_KEYS.VOCAB, JSON.stringify(state.vocabList));
  updateVocabUI();
  
  // Highlight UI count feedback
  const vocabBtn = document.getElementById("vocab-toggle");
  vocabBtn.style.transform = "scale(1.08)";
  setTimeout(() => vocabBtn.style.transform = "", 200);
}

function deleteVocabWord(timestamp) {
  state.vocabList = state.vocabList.filter(item => item.timestamp !== timestamp);
  localStorage.setItem(STORAGE_KEYS.VOCAB, JSON.stringify(state.vocabList));
  updateVocabUI();
}

function clearVocabList() {
  if (confirm("Are you sure you want to delete all saved vocabulary cards?")) {
    state.vocabList = [];
    localStorage.removeItem(STORAGE_KEYS.VOCAB);
    updateVocabUI();
  }
}

function updateVocabUI() {
  const countEl = document.getElementById("vocab-count");
  const listEl = document.getElementById("vocab-list");
  
  countEl.textContent = state.vocabList.length;
  listEl.innerHTML = "";

  if (state.vocabList.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 40px 0;">
        <p style="font-size: 2.5rem; margin-bottom: 8px;">📓</p>
        <p style="font-size: 0.85rem;">Vocabulary notebook is currently empty. Click "+" on word popups to save words.</p>
      </div>
    `;
    return;
  }

  state.vocabList.forEach(item => {
    const card = document.createElement("div");
    card.className = "vocab-item";
    card.innerHTML = `
      <div class="vocab-word-row">
        <h4>${item.word}</h4>
        <button class="vocab-delete" data-ts="${item.timestamp}" title="Delete word">&times;</button>
      </div>
      <p>${item.definition}</p>
      <span>${item.grammar}</span>
    `;

    card.querySelector(".vocab-delete").addEventListener("click", (e) => {
      e.stopPropagation();
      const ts = parseInt(e.target.dataset.ts);
      deleteVocabWord(ts);
    });

    listEl.appendChild(card);
  });
}

function exportVocabAsMarkdown() {
  if (state.vocabList.length === 0) {
    alert("No vocabulary words saved yet.");
    return;
  }

  let md = "# Saved Vocabulary List\n\n| Word | Definition | Grammar |\n|---|---|---|\n";
  state.vocabList.forEach(item => {
    md += `| **${item.word}** | ${item.definition} | *${item.grammar}* |\n`;
  });

  const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "russian_vocabulary.md";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ── Client-side Sentence Aligner (For Custom Texts) ──────────────────────────
function alignCustomTexts(title, author, rusText, engText) {
  // Strip Carriage Returns
  const rusClean = rusText.replace(/\r/g, "");
  const engClean = engText.replace(/\r/g, "");

  // Naive parser: Split chapters on double newlines that look like chapter indicators
  // or simply split into paragraphs
  const rusChaptersRaw = parseTextIntoChapters(rusClean);
  const engChaptersRaw = parseTextIntoChapters(engClean);

  const maxCh = Math.max(Object.keys(rusChaptersRaw).length, Object.keys(engChaptersRaw).length);
  const chaptersData = [];
  const TARGET_WORDS_PER_CHUNK = 80;

  for (let chNum = 1; chNum <= maxCh; chNum++) {
    const rp = rusChaptersRaw[chNum] || [];
    const ep = engChaptersRaw[chNum] || [];

    const rusW = rp.reduce((acc, p) => acc + p.split(/\s+/).length, 0);
    const engW = ep.reduce((acc, p) => acc + p.split(/\s+/).length, 0);

    const n = Math.max(1, Math.round((rusW + engW) / 2 / TARGET_WORDS_PER_CHUNK));
    const rusChunks = splitEqualChunks(rp, n);
    const engChunks = splitEqualChunks(ep, n);

    chaptersData.append ? null : chaptersData.push({
      chapterNum: chNum,
      titleRus: `Глава ${chNum}`,
      titleEng: `Chapter ${chNum}`,
      russian: rusChunks,
      english: engChunks
    });
  }

  const newBook = {
    title: title || "Custom Text",
    titleEng: title || "Custom Text",
    author: author || "Unknown",
    authorEng: author || "Unknown",
    year: new Date().getFullYear().toString(),
    chapters: chaptersData
  };

  // Add to state and persistence
  state.books.push(newBook);
  
  // Save custom library items to localStorage (filtering out preloaded book)
  const customBooks = state.books.slice(PRELOADED_BOOKS.length);
  localStorage.setItem(STORAGE_KEYS.CUSTOM_BOOKS, JSON.stringify(customBooks));

  populateBookSelector();
  
  // Load the newly added book
  const newBookIdx = state.books.length - 1;
  const bookSelect = document.getElementById("book-select");
  bookSelect.value = newBookIdx;
  loadBook(newBookIdx);

  alert(`"${newBook.title}" aligned successfully into ${maxCh} chapters!`);
}

function parseTextIntoChapters(text) {
  const paragraphs = text.split(/\n\s*\n/).map(p => p.trim()).filter(p => p);
  const chapters = {};
  let currentCh = 1;
  let currentBuffer = [];

  for (const para of paragraphs) {
    // Basic test if paragraph is a chapter header: e.g. "Chapter 1", "Глава II", "I."
    const isHeader = /^(chapter|глава|chapter\s+\d+|глава\s+[ivxldcm]+|[ivxldcm]+\.|\d+)$/i.test(para);
    if (isHeader) {
      if (currentBuffer.length > 0) {
        chapters[currentCh] = currentBuffer;
        currentBuffer = [];
        currentCh++;
      }
    } else {
      currentBuffer.push(para);
    }
  }
  if (currentBuffer.length > 0) {
    chapters[currentCh] = currentBuffer;
  }
  return chapters;
}

function splitEqualChunks(paragraphs, n) {
  const text = paragraphs.join(" ");
  // Split on sentence punctuation followed by space
  const sents = text.split(/(?<=[.!?»])\s+/).map(s => s.trim()).filter(s => s.length > 0);
  if (sents.length === 0) return Array(n).fill("");

  const totalWords = sents.reduce((acc, s) => acc + s.split(/\s+/).length, 0);
  const target = totalWords / n;

  const chunks = [];
  let cur = [];
  let curW = 0;

  for (const sent of sents) {
    const w = sent.split(/\s+/).length;
    cur.push(sent);
    curW += w;
    if (curW >= target && chunks.length < n - 1) {
      chunks.push(cur.join(" "));
      cur = [];
      curW = 0;
    }
  }
  if (cur.length > 0) {
    chunks.push(cur.join(" "));
  }

  while (chunks.length > n) {
    chunks[chunks.length - 2] += " " + chunks[chunks.length - 1];
    chunks.pop();
  }
  while (chunks.length < n) {
    chunks.push("");
  }
  return chunks;
}

// ── Progress & Footer Updates ───────────────────────────────────────────────
function updateProgressBar() {
  const bar = document.getElementById("reading-progress-bar");
  const pctText = document.getElementById("progress-percent");
  
  const book = state.books[state.currentBookIndex];
  
  const totalChapters = book.chapters.length;
  const currentChapter = state.currentChapterIndex + 1;
  const pct = Math.round((currentChapter / totalChapters) * 100);

  bar.style.width = `${pct}%`;
  pctText.textContent = `${pct}%`;
}

// ── Event Bindings ────────────────────────────────────────────────────────────
function bindEvents() {
  // Theme Toggle
  document.getElementById("theme-toggle").addEventListener("click", toggleTheme);

  // Selector Changes
  document.getElementById("book-select").addEventListener("change", (e) => {
    loadBook(e.target.value);
  });
  document.getElementById("chapter-select").addEventListener("change", (e) => {
    state.currentChapterIndex = parseInt(e.target.value);
    renderChapter();
  });

  // Drawer Toggles
  const vocabDrawer = document.getElementById("vocab-drawer");
  const dictDrawer = document.getElementById("dict-drawer");

  document.getElementById("vocab-toggle").addEventListener("click", () => {
    vocabDrawer.classList.toggle("open");
    dictDrawer.classList.remove("open"); // close dictionary if vocab opened
  });

  document.getElementById("close-vocab-drawer").addEventListener("click", () => {
    vocabDrawer.classList.remove("open");
  });

  document.getElementById("close-dict-drawer").addEventListener("click", () => {
    dictDrawer.classList.remove("open");
  });



  // Vocab Actions
  document.getElementById("export-vocab").addEventListener("click", exportVocabAsMarkdown);
  document.getElementById("clear-vocab").addEventListener("click", clearVocabList);

  // Custom Book Modal Loader
  const modal = document.getElementById("custom-loader-modal");
  document.getElementById("custom-loader-trigger").addEventListener("click", () => {
    modal.classList.remove("hidden");
  });

  document.getElementById("close-modal").addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  // Load Book Click
  document.getElementById("btn-load-text").addEventListener("click", () => {
    const title = document.getElementById("custom-title").value.trim();
    const author = document.getElementById("custom-author").value.trim();
    const rus = document.getElementById("custom-russian-text").value.trim();
    const eng = document.getElementById("custom-english-text").value.trim();

    if (!rus || !eng) {
      alert("Please enter both the Russian original text and English translation.");
      return;
    }

    alignCustomTexts(title, author, rus, eng);
    modal.classList.add("hidden");
    
    // Reset Form
    document.getElementById("custom-title").value = "";
    document.getElementById("custom-author").value = "";
    document.getElementById("custom-russian-text").value = "";
    document.getElementById("custom-english-text").value = "";
  });
}
