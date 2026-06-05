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
  frVoice: null,
  activeAudioUtterance: null,
  audioPlayer: null,
  isPlayingChapter: false,
  syncGistId: null
};

// LocalStorage Keys
const STORAGE_KEYS = {
  VOCAB: "slovo_vocab_notebook",
  CUSTOM_BOOKS: "slovo_custom_library",
  THEME: "slovo_active_theme",
  PROGRESS: "slovo_reading_progress",
  GIST_FILE: "slovo_progress.json",
  GIST_ID: "slovo_gist_id"
,
  AUDIOBOOK_DIR: "slovo_audiobook_dir"
};

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  loadVocabList();
  initVoices();
  
  // Try to sync progress from Gist
  await loadProgressFromGist();
  
  loadLibrary();
  
  // Check if returning from a book
  const savedBook = localStorage.getItem("_selected_book");
  if (savedBook !== null) {
    document.getElementById("splash-screen").classList.add("hidden");
    document.getElementById("app-workspace").hidden = false;
    enterBook(parseInt(savedBook));
  }
  
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
    // Also find a French voice for French sections
    state.frVoice = voices.find(v => v.lang.startsWith("fr-FR") || v.lang.startsWith("fr")) || null;
  };
  setVoice();
  if (state.synth.onvoiceschanged !== undefined) {
    state.synth.onvoiceschanged = setVoice;
  }
}

function detectLanguage(text) {
  // Detect the language of the text
  // French: contains accented chars (à, é, è, etc.) and no Cyrillic
  if (/[а-яёА-ЯЁ]/.test(text)) return "ru-RU";
  if (/[àâçéèêëîïôùûœ]/.test(text)) return "fr-FR";
  // Default to Russian
  return "ru-RU";
}

function speakText(text, lang) {
  if (state.synth.speaking) {
    state.synth.cancel();
  }
  
  // Auto-detect language if not provided
  if (!lang) lang = detectLanguage(text);

  const speedSelect = document.getElementById("speed-select");
  const rate = speedSelect ? parseFloat(speedSelect.value) : 0.9;
  
  const utterance = new SpeechSynthesisUtterance(text);
  
  // Use the correct voice for the detected language
  if (lang.startsWith("ru") && state.ruVoice) {
    utterance.voice = state.ruVoice;
  } else if (lang.startsWith("fr") && state.frVoice) {
    utterance.voice = state.frVoice;
  } else {
    utterance.lang = lang;
  }
  
  utterance.rate = rate;
  
  state.activeAudioUtterance = utterance;
  state.synth.speak(utterance);
}

// ── Library Loading ───────────────────────────────────────────────────────────
function loadLibrary() {
  // Load the preloaded books into state
  state.books = [...PRELOADED_BOOKS];
  
  // Also load any custom books from localStorage
  const savedCustom = localStorage.getItem(STORAGE_KEYS.CUSTOM_BOOKS);
  if (savedCustom) {
    try {
      const customBooks = JSON.parse(savedCustom);
      state.books = [...state.books, ...customBooks];
    } catch (e) {
      console.error("Error loading custom books:", e);
    }
  }
  
  // Render splash screen with book tiles
  renderSplash();
}

function renderSplash() {
  const grid = document.getElementById("book-grid");
  if (!grid) return;
  grid.innerHTML = "";
  
  state.books.forEach((book, idx) => {
    const card = document.createElement("div");
    card.className = "book-card";
    
    const totalCh = book.chapters.length;
    const completedCh = parseInt(localStorage.getItem(`book_${idx}_progress`) || "0");
    const pct = Math.round((completedCh / totalCh) * 100);
    
    card.innerHTML = `
      <div class="book-icon">📚</div>
      <h3>${book.title}</h3>
      <div class="book-meta">
        <span>${book.author}</span>
        <span>· ${book.year}</span>
        <span>· ${totalCh} chapters</span>
      </div>
      <div class="book-progress">
        <div class="progress-track">
          <div class="progress-bar" style="width: ${pct}%"></div>
        </div>
        <span class="progress-text">${pct}%</span>
      </div>
    `;
    
    card.addEventListener("click", () => {
      localStorage.setItem("_selected_book", idx);
      document.getElementById("splash-screen").classList.add("hidden");
      document.getElementById("app-workspace").hidden = false;
      enterBook(idx);
    });
    
    grid.appendChild(card);
  });
}

function enterBook(bookIdx) {
  state.currentBookIndex = parseInt(bookIdx);
  state.currentChapterIndex = 0;
  
  // Populate book and chapter selectors
  populateBookSelector();
  
  const chSelect = document.getElementById("chapter-select");
  chSelect.innerHTML = "";
  const book = state.books[state.currentBookIndex];
  book.chapters.forEach((ch, idx) => {
    const opt = document.createElement("option");
    opt.value = idx;
    opt.textContent = ch.titleRus || `Глава ${ch.chapterNum}`;
    chSelect.appendChild(opt);
  });

  // Hide splash, show reader
  document.getElementById("splash-screen").classList.add("hidden");
  document.getElementById("app-workspace").hidden = false;

  renderChapter();
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

// ── Parallel Sentence and Word Renderer ─────────────────────────────────────
function renderChapter() {
  const book = state.books[state.currentBookIndex];
  const chapter = book.chapters[state.currentChapterIndex];
  const container = document.getElementById("chunks-container");
  container.innerHTML = "";
  
  // Sync progress
  const pct = Math.round((state.currentChapterIndex / book.chapters.length) * 100);
  syncProgressToGist();
  
  // Update local progress marker
  localStorage.setItem(`book_${state.currentBookIndex}_progress`, state.currentChapterIndex);

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

    const maxSents = Math.max(rusSents.length, engSents.length);
    for (let sIdx = 0; sIdx < maxSents; sIdx++) {
      const rusSent = rusSents[sIdx];
      const engSent = engSents[sIdx];

      const sentRow = document.createElement("div");
      sentRow.className = "sentence-row";

      // Russian Sentence
      if (rusSent) {
        const rusSpan = document.createElement("span");
        rusSpan.className = "sentence-box rus-sent";
        rusSpan.dataset.sentId = `ch-${chunkIdx}-s-${sIdx}`;

        const words = tokenizeWords(rusSent);
        words.forEach(w => {
          if (w.isWord) {
            const wordSpan = document.createElement("span");
            wordSpan.className = "word-span";
            wordSpan.textContent = w.text;
            rusSpan.appendChild(wordSpan);
          } else {
            rusSpan.appendChild(document.createTextNode(w.text));
          }
        });

        // Add small TTS play button
        const playBtn = document.createElement("button");
        playBtn.className = "tts-play-btn";
        playBtn.innerHTML = "🔊";
        playBtn.title = "Speak sentence";
        playBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          speakText(rusSent);
        });
        rusSpan.appendChild(playBtn);
        sentRow.appendChild(rusSpan);
      } else {
        const emptySpan = document.createElement("span");
        emptySpan.className = "sentence-box empty-sent";
        sentRow.appendChild(emptySpan);
      }

      // English Sentence
      if (engSent) {
        const engSpan = document.createElement("span");
        engSpan.className = "sentence-box eng-sent";
        engSpan.dataset.sentId = `ch-${chunkIdx}-s-${sIdx}`;
        engSpan.textContent = engSent;
        sentRow.appendChild(engSpan);
      } else {
        const emptySpan = document.createElement("span");
        emptySpan.className = "sentence-box empty-sent";
        sentRow.appendChild(emptySpan);
      }

      row.appendChild(sentRow);
    }
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

    // Highlight active sentence
    document.querySelectorAll(".sentence-box.active-sentence").forEach(el => {
      el.classList.remove("active-sentence");
    });
    const sentenceBox = wordSpan.closest(".sentence-box");
    if (sentenceBox) {
      const sentId = sentenceBox.dataset.sentId;
      document.querySelectorAll(`.sentence-box[data-sent-id="${sentId}"]`).forEach(el => {
        el.classList.add("active-sentence");
      });
    }

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
    document.querySelectorAll(".sentence-box.active-sentence").forEach(el => {
      el.classList.remove("active-sentence");
    });
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

  // Clean original word
  const cleanOriginal = originalText.replace(/[^а-яёА-ЯЁ\-]/g, "");
  const cleanLower = cleanOriginal.toLowerCase();

  // Find the English translation from the book's parallel data
  const book = state.books[state.currentBookIndex];
  const chapter = book.chapters[state.currentChapterIndex];
  
  // Look through all chunks to find the sentence containing this word
  let englishTranslation = null;
  let russianSentence = null;
  let chunkIndex = -1;
  
  // Find the clicked word's parent sentence
  const wordSpan = document.querySelector(".selected-word");
  if (wordSpan) {
    const sentenceBox = wordSpan.closest(".sentence-box");
    if (sentenceBox) {
      const sentId = sentenceBox.dataset.sentId;
      const chunkMatch = sentId.match(/ch-(\d+)-s-(\d+)/);
      if (chunkMatch) {
        chunkIndex = parseInt(chunkMatch[1]);
        const englishChunk = chapter.english[chunkIndex];
        if (englishChunk) {
          englishTranslation = englishChunk;
          russianSentence = chapter.russian[chunkIndex];
        }
      }
    }
  }

  // Fallback to Wiktionary lookup
  const queryApi = (wordToQuery, isRetry = false) => {
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
        
        let detectedLemma = null;
        const tempDiv = document.createElement("div");
        
        for (const block of ruData) {
          for (const defObj of block.definitions) {
            tempDiv.innerHTML = defObj.definition;
            const link = tempDiv.querySelector(".form-of-definition-link a, .mention a, a[href*='/wiki/']");
            if (link) {
              const linkText = (link.textContent || link.innerText).trim();
              if (/[а-яёА-ЯЁ]/.test(linkText)) {
                detectedLemma = linkText.replace(/\u0301/g, "").toLowerCase();
                break;
              }
            }
          }
          if (detectedLemma) break;
        }

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
              renderRESTAnalysis(originalText, ruData, translation, englishTranslation);
            })
            .catch(err => {
              renderRESTAnalysis(originalText, ruData, null, englishTranslation);
            });
        } else {
          renderRESTAnalysis(originalText, ruData, null, englishTranslation);
        }
      })
      .catch(err => {
        if (!isRetry && cleanOriginal !== wordToQuery) {
          queryApi(cleanOriginal, true);
        } else {
          console.error("REST Wiktionary lookup error for word:", originalText);
          showTooltipError(originalText, "No direct definition found in Wiktionary. (Russian words are grammar-sensitive).");
        }
      });
  };

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

function renderRESTAnalysis(originalText, ruData, lemmaTranslation = null, contextTranslation = null) {
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

  let contextHtml = "";
  if (contextTranslation) {
    const displayContext = contextTranslation.length > 100 ? contextTranslation.slice(0, 97) + "..." : contextTranslation;
    contextHtml = `<div class="tooltip-context" style="border-top: 1px dashed var(--border-color); padding-top: 6px; margin-top: 6px; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.3;">Context: "${displayContext}"</div>`;
    
    detailedCardHtml += `
      <div class="dict-body-section" style="margin-top: 14px; border-top: 1px solid var(--border-color); padding-top: 8px;">
        <div class="dict-section-title" style="color: var(--text-muted); font-weight: 700;">Sentence Context</div>
        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 4px; line-height: 1.4;">"${contextTranslation}"</p>
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
    ${contextHtml}
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

// ── Gist Synchronisation (Cross-device progress) ────────────────────────────────
const GIST_FILE = STORAGE_KEYS.GIST_FILE;

async function githubFetch(url, options = {}) {
  const pat = localStorage.getItem("slovo_github_pat");
  const calciferPat = localStorage.getItem("calcifer_github_pat");
  const effectivePat = pat || calciferPat;
  if (!effectivePat) return null;
  
  const headers = {
    "Authorization": `token ${effectivePat}`,
    "Accept": "application/vnd.github.v3+json",
    ...options.headers
  };
  return fetch(url, { ...options, headers });
}

async function syncProgressToGist() {
  const gistId = localStorage.getItem(STORAGE_KEYS.GIST_ID);
  
  // Build progress data
  const progressData = {
    version: 2,
    lastUpdated: new Date().toISOString(),
    books: state.books.map((book, idx) => ({
      title: book.title,
      currentChapter: idx === state.currentBookIndex ? state.currentChapterIndex : 0,
      chaptersRead: parseInt(localStorage.getItem(`book_${idx}_progress`) || "0"),
      totalChapters: book.chapters.length
    })),
    vocab: state.vocabList
  };

  try {
    // Write to gist via GitHub API
    const url = gistId 
      ? `https://api.github.com/gists/${gistId}`
      : "https://api.github.com/gists";
    
    const method = gistId ? "PATCH" : "POST";
    
    const res = await githubFetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description: "Slovo Reader reading progress",
        files: { [GIST_FILE]: { content: JSON.stringify(progressData, null, 2) } }
      })
    });
    
    if (!res) {
      throw new Error("No GitHub Access Token configured. Please set a Personal Access Token (PAT).");
    }
    
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`GitHub API error (${res.status}): ${errText}`);
    }
    
    if (!gistId && res.ok) {
      const gist = await res.json();
      localStorage.setItem(STORAGE_KEYS.GIST_ID, gist.id);
    }
  } catch (e) {
    console.error("Gist sync failed:", e);
    throw e;
  }
}

async function loadProgressFromGist() {
  const gistId = localStorage.getItem(STORAGE_KEYS.GIST_ID);
  if (!gistId) {
    // Try to find an existing gist
    const res = await githubFetch("https://api.github.com/gists");
    if (res && res.ok) {
      const gists = await res.json();
      const found = gists.find(g => g.files && g.files[GIST_FILE]);
      if (found) {
        localStorage.setItem(STORAGE_KEYS.GIST_ID, found.id);
        const content = JSON.parse(found.files[GIST_FILE].content);
        mergeGistProgress(content);
      }
    }
  }
}

function mergeGistProgress(cloudData) {
  if (!cloudData || !cloudData.books) return;
  
  // Merge book progress
  cloudData.books.forEach((cloudBook, idx) => {
    const localRead = parseInt(localStorage.getItem(`book_${idx}_progress`) || "0");
    if (cloudBook.chaptersRead > localRead) {
      localStorage.setItem(`book_${idx}_progress`, cloudBook.chaptersRead);
    }
  });
  
  // Update progress bars
  renderSplash();
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
    enterBook(e.target.value);
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

  // Sync progress to Gist
  document.getElementById("sync-gist").addEventListener("click", async () => {
    let pat = localStorage.getItem("slovo_github_pat") || localStorage.getItem("calcifer_github_pat");
    if (!pat) {
      pat = prompt("To enable progress sync across devices, enter your GitHub Personal Access Token (PAT) with 'gist' scope:");
      if (pat) {
        localStorage.setItem("slovo_github_pat", pat.trim());
      } else {
        return;
      }
    }
    
    try {
      await syncProgressToGist();
      alert("Progress synced to GitHub Gist!");
    } catch (err) {
      alert("Sync failed: " + err.message);
    }
  });

  // Back to Library
  document.getElementById("back-to-splash").addEventListener("click", () => {
    document.getElementById("splash-screen").classList.remove("hidden");
    document.getElementById("app-workspace").hidden = true;
    // Restore chapter selector and progress
    renderSplash();
  });



  // Vocab Actions
  document.getElementById("export-vocab").addEventListener("click", exportVocabAsMarkdown);
  document.getElementById("clear-vocab").addEventListener("click", clearVocabList);

}
