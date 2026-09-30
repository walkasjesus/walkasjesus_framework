# Bible Study tool — how it works

Reference documentation for the `/bible-study/` page (`BibleStudyView` and friends). It explains
where the data comes from, how the original-language word data is built, and how the English text
is linked word-by-word to the Hebrew/Greek.

---

## 1. Page anatomy

| Piece | File |
| --- | --- |
| Page view + AJAX endpoints | [views/bible_study_view.py](views/bible_study_view.py) |
| Strong's / original-language engine | [lib/strongs_service.py](lib/strongs_service.py) |
| Page template | [templates/bible_study/bible_study.html](templates/bible_study/bible_study.html) |
| All client logic | [templates/bible_study/_bible_study_script.html](templates/bible_study/_bible_study_script.html) |
| All styling | [templates/bible_study/_bible_study_styles.html](templates/bible_study/_bible_study_styles.html) |

The page renders the first passage server-side, then everything else (changing passage,
translations, toggles, panels) happens through AJAX so the API.Bible quota is only spent on
verses that are actually shown.

### Endpoints

| URL name | Purpose |
| --- | --- |
| `bible_study` | Page render, also honours deep links (`?book=&chapter=&start_verse=…`) |
| `bible_study_verses` | Verse text for one translation and verse range (cached 6 months) |
| `bible_study_chapter_meta` | Last verse number of a chapter, from `data/bible_study_chapter_index.json` |
| `bible_study_original_text` | Original-language words + Strong's candidates for a verse range |
| `bible_study_word_alignment` | Maps the English words of a verse onto original-language word indexes |
| `bible_study_search` | Proxy for API.Bible full-text search |

### Query/state parameters

`book`, `chapter`, `start_verse`, `end_verse`, `bible_id` (repeatable, up to 4 columns),
`show_original`, `combine_verses`. `combine_verses=1` shows one block per translation;
`combine_verses=0` shows one card per verse — **word alignment only runs in this mode**.

---

## 2. Data sources

Everything below is local; no third-party call is made for word data.

| Folder | Content | Licence |
| --- | --- | --- |
| `data/stepbible/Translators Amalgamated OT+NT/` | **TAHOT** (Hebrew OT) and **TAGNT** (Greek NT): every original word with its Strong's tag, morphology and a *contextual* English gloss | CC BY 4.0 |
| `data/stepbible/Lexicons/` | **TBESH** / **TBESG** brief lexicons, **TFLSJ** full LSJ | CC BY 4.0 |
| `data/strongs/` | OpenScriptures Strong's dictionaries (`strongs_def`, `kjv_def`, `derivation`, `pron`) | Public domain |
| `data/lxx_greek_to_hebrew.json` | Greek→Hebrew equivalents derived from Septuagint usage (built by `build_lxx_greek_to_hebrew_index`) | derived |
| `data/tagged_bibles/kjv_strongs/` | **Word-level Strong's tags for the KJV**, one gzipped JSON per book | GPL (CrossWire KJV module) |

Verse text itself comes from API.Bible, from the local Complete Jewish Bible JSON, or from the
Scriptura/Sefaria integrations, depending on the selected translation.

---

## 3. The original-language panel

`original_text_payload(book, chapter, verse)` in `lib/strongs_service.py` builds one payload per
verse, cached 30 days under `bible_study:original:v15:…`:

1. Scan the TAHOT/TAGNT file for the book and pull every row whose reference matches the verse.
2. `_parse_stepbible_row` extracts per original word:
   - `surface_text` — the pointed Hebrew / accented Greek form,
   - `transliteration`,
   - `context_translation` — **the contextual English rendering of this exact occurrence**
     (TAHOT column 3, TAGNT column 2, e.g. `[the] sons of`, `loved`),
   - `translation_label` — the lexical gloss (TAGNT column 9),
   - `grammar` — the morphology code,
   - `strongs_numbers` — every Strong's tag on the word, prefixes and suffixes included.
3. For each Strong's number `_candidate_payload` merges:
   - the STEPBible brief lexicon entry (lemma, gloss, structured `__1. __2.` senses with refs),
   - the OpenScriptures entry (`strongs_def`, `kjv_def`, `derivation`, pronunciation),
   - a usage outline with reference counts, root words, and (Greek only) likely Hebrew
     equivalents from the LXX index.
4. The token also gets `context_gloss` — the deduplicated contextual rendering. This is what the
   "Direct gloss" line shows and what the fallback alignment scores against.

If a verse has no STEPBible rows (rare versification differences) the payload falls back to plain,
non-clickable tokens so the UI degrades gracefully.

---

## 4. Linking the English text to the original words

Goal: hovering *children* in the KJV highlights בְּנֵי, and clicking it opens H1121 — expanding the
original-text panel first if it is collapsed.

`english_alignment_payload(book, chapter, verse, english_text, tagged_source)` returns

```json
{"tokens": [{"text": "children", "word_index": 2}, {"text": " ", "word_index": -1}],
 "aligned_count": 19, "method": "tagged"}
```

`word_index` is the index into `original_text_payload(...)["words"]`; `-1` means unlinked. The
token list re-creates the verse verbatim (punctuation and spacing included), so the client can
replace the paragraph HTML without changing the visible text.

There are two strategies.

### 4a. `method: "tagged"` — direct Strong's lookup (KJV)

Used when the selected translation has a word-level tagging. `_tagged_source_for_bible()` returns
`'kjv'` for any edition whose abbreviation is `KJV`/`KJVCPB`/`AKJV`/`AV` or whose name contains
"King James".

`data/tagged_bibles/kjv_strongs/<Book>.json.gz` stores each verse as runs of words with the
Strong's number the KJV translators' tagging assigned to them:

```json
"1": [["H7225", ["In","the","beginning"]],
      ["H430",  ["God"]],
      ["H853 H1254", ["created"]],
      ["H8064", ["the","heaven"]], …]
```

Mapping a run to an original word:

1. Build `code → [original token indexes]` from the verse payload, in reading order.
2. Inside a run, prefer a **content** code over a grammatical one
   (`H853`/`H854` object marker, `G3588` article) — that is why `H853 H1254` resolves to בָּרָא
   and not to אֵת.
3. When a code occurs several times in the verse, take the **nearest still unused** occurrence to
   the previously assigned token, preferring forward on a tie. This keeps repeated verbs
   (`came … came` in Exodus 1:1) in order while still allowing the KJV's re-ordering
   (`he gave his only begotten Son` vs. `υἱὸν αὐτοῦ τὸν μονογενῆ ἔδωκεν`).
4. The KJV edition served by API.Bible is not byte-identical to the CrossWire module
   (pilcrows, spelling, punctuation). An LCS pass transfers the mapping from the tagged word
   sequence onto the displayed word sequence. If fewer than 60 % of the displayed words are
   recovered, the tagged result is rejected and strategy 4b runs instead.

### 4b. `method: "lexicon"` — scored alignment (every other English translation)

No tags available, so the link is inferred:

1. For every original token collect the English surface forms it may appear as:
   - `gloss_words` from `context_gloss` (highest confidence),
   - `lexicon_words` from the Strong's `kjv_def` and the lexicon glosses, minus function words
     (`the`, `of`, `and`, …) because those appear in nearly every definition and would be noise.
2. Score an English word against a token: exact gloss 6.0, stemmed gloss 4.0, exact lexicon 3.0,
   stemmed lexicon 2.0, otherwise 0. Stemming strips KJV-era suffixes (`-eth`, `-est`, `-ies`, …)
   and knows a short irregular table (`children→child`, `went→go`, `spake→speak`, …).
3. Run an **order-preserving** (Needleman-Wunsch style) alignment that maximises the total score.
   Order preservation is what prevents a word like "the" matching a random token elsewhere.
4. A rescue pass then links any still-unmapped word that has exactly one unused *exact gloss*
   match anywhere in the verse — this catches words the translator moved, such as the trailing
   "Jacob" in Exodus 1:1.

Both results are cached 30 days under `bible_study:alignment:v3:<source>:<book>:<ch>:<v>:<sha>`.

---

## 5. Client behaviour

In `_bible_study_script.html`:

- After verse text is rendered (`applyBibleStudyPayloadToDom`, or on first page load),
  `loadBibleStudyWordAlignment()` posts the displayed verse text to `bible_study_word_alignment`
  and replaces the paragraph with tokenised HTML. It only runs when `combine_verses` is off and
  the translation label starts with `EN -`.
- Aligned words get `<span class="bs-aligned-word" data-verse data-word-index>`.
- `syncOriginalSentenceHover` / `syncOriginalSentenceSelection` now cover three surfaces at once:
  the original sentence tokens, the word-cloud buttons *and* the aligned English words, so
  hovering or selecting any of them highlights the others.
- Clicking an aligned word calls `openBibleStudyOriginalWordFromEnglish()`. If the verse's
  "Original text" panel is collapsed it is opened, the payload is fetched, and
  `bsPendingAlignedSelection` makes the panel select that exact word (and scroll to it) once
  loaded.

---

## 6. Regenerating the tagged KJV data

```bash
pip install pysword                      # optional, only for this command
python manage.py build_kjv_strongs_index # downloads the CrossWire KJV module and rebuilds
# or, from an already extracted module directory:
python manage.py build_kjv_strongs_index --module-path /path/to/module
```

Source: <https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/KJV.zip> —
"King James Version (1769) with Strongs Numbers and Morphology", `DistributionLicense=GPL`,
compatible with this project's GPL-3.0 licence. Output is ~2.3 MB and is committed to the repo,
so no runtime dependency on pysword.

### Adding another tagged translation

1. Produce `data/tagged_bibles/<name>/<Book>.json.gz` in the same run format.
2. Add a loader next to `_tagged_kjv_book` and branch on `tagged_source` in
   `english_alignment_payload`.
3. Teach `_tagged_source_for_bible()` which `bible_id`/abbreviation maps to the new source.

STEPBible also publishes `TTESV` (ESV, **CC BY-NC** — not usable here) and `TTAraSVD`
(Arabic Smith–Van Dyck, CC BY-SA) under `data/stepbible/Tagged-Bibles/`; the Arabic set is a
ready candidate if Arabic is ever added.

---

## 7. Caching and quota

| Key prefix | TTL | Contents |
| --- | --- | --- |
| `bible_study:v1:…` | `BIBLE_API_CACHE_TIMEOUT_SECONDS` (6 months) | verse text per translation |
| `bible_study:original:v15:…` | 30 days | original-language payload per verse |
| `bible_study:alignment:v3:…` | 30 days | English↔original token mapping |
| `bible_study:search:…` | 7 days | API.Bible search results |

Bump the `vNN` in the cache key whenever the shape of a payload changes, otherwise stale entries
are served. `BibleTranslationUsageDaily` records every API.Bible hit; `consume_bible_api_quota`
raises `BibleApiRateLimitExceeded` (HTTP 429) when the daily allowance is spent. The alignment
and original-text endpoints never touch the API, so they are free.

## 8. Attribution requirements

- STEPBible data: credit "STEP Bible" linked to <https://www.stepbible.org> (CC BY 4.0).
- CrossWire KJV tagging: CrossWire Bible Society, distributed under GPL.
- Per-translation copyright strings from API.Bible are rendered under each verse card.
