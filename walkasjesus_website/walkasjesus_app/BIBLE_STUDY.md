# Bible Study tool — how it works

Reference documentation for the `/bible-study/` page (`BibleStudyView` and friends). It explains
where the data comes from, how the original-language word data is built, and how the translated
text is linked word-by-word to the Hebrew/Greek.

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
| `bible_study_word_alignment` | Maps the words of a translated verse onto original-language word indexes |
| `bible_study_search` | Proxy for API.Bible full-text search |

### Query/state parameters

`book`, `chapter`, `start_verse`, `end_verse`, `bible_id` (repeatable, up to 4 columns),
`show_original`, `combine_verses`. `combine_verses=1` shows one block per translation;
`combine_verses=0` shows one card per verse — **word linking only runs in this mode**.

---

## 2. Data sources

Everything below is local; no third-party call is made for word data.

| Folder | Content | Licence |
| --- | --- | --- |
| `data/stepbible/Translators Amalgamated OT+NT/` | **TAHOT** (Hebrew OT) and **TAGNT** (Greek NT): every original word with its Strong's tag, morphology and a *contextual* English gloss | CC BY 4.0 |
| `data/stepbible/Lexicons/` | **TBESH** / **TBESG** brief lexicons, **TFLSJ** full LSJ | CC BY 4.0 |
| `data/strongs/` | OpenScriptures Strong's dictionaries (`strongs_def`, `kjv_def`, `derivation`, `pron`) | Public domain |
| `data/lxx_greek_to_hebrew.json` | Greek→Hebrew equivalents derived from Septuagint usage (built by `build_lxx_greek_to_hebrew_index`) | derived |
| `data/tagged_bibles/kjv/` | **Word-level Strong's tags for the KJV**, one gzipped JSON per book, plus `_usage.json.gz` | GPL (CrossWire `KJV` module) |
| `data/tagged_bibles/svv/` | **Word-level Strong's tags for the Dutch Statenvertaling**, same format | Public domain (CrossWire `DutSVVA` module) |
| `data/local_bibles/statenvertaling/` | The plain Statenvertaling verse text, served as a selectable translation | Public domain |

Verse text itself comes from API.Bible, from the local Complete Jewish Bible JSON, from the bundled
Statenvertaling, or from the Scriptura/Sefaria integrations, depending on the selected translation.
Bibles that carry `is_local_source = True` never consume API.Bible quota. `data/tagged_bibles`
is a separate Git submodule; its own [README](../data/tagged_bibles/README.md) documents the
sources and regeneration. Run `./update_tagged_bibles.sh` from `walkasjesus_website` to initialise
the pinned revision and print the data version currently in use.

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

### Glosses in the interface language

`localized_original_text_payload(book, chapter, verse, language_code)` wraps the payload above and,
for languages listed in `GLOSS_SOURCE_BY_LANGUAGE` (currently `nl` → `svv`), adds two things the
word-level tagging makes possible:

- `word['local_gloss']` — how that tagged edition renders **this exact occurrence**, resolved with
  the same run→token logic as the word links (§4a). Words the edition left untagged fall back to
  the most frequent rendering of their Strong's number, so the panel is never half English.
- `candidate['local_usage']` — the concordance `[{label, count, references}, …]` of every rendering of that
  Strong's number in the tagged edition, most frequent first (`_usage.json.gz`, top 15 per code,
  ~14 000 codes per source). For H1121 the Dutch list reads *zoon 1774, kinderen 1773, zonen 810,
  oud 133, mensenkind 98, …* — the Dutch equivalent of the KJV usage line.

The client then prefers `local_gloss` for the word-cloud label and the "Direct gloss" line, and
renders `local_usage` as an ordered list headed with `payload['local_source_name']`. Each item in
`local_usage` and each node in the *Outline of Biblical Usage* carries a count button (e.g. `(203x)`).
Clicking it opens the integrated **Occurrence Viewer** dialog:
- The upper area displays the text for the currently selected verse in the active translation.
- The lower area displays range buttons chunked in blocks of 25 (e.g. `1. Gen.1:11–Gen.24:60 (25x)`),
  along with all 25 verse buttons for that chunk.
- Clicking any verse button immediately retrieves and displays its text in the upper preview area
  without leaving or duplicating the popup.
- The summary accurately states total occurrences and verse count (e.g. `203x (in 185 verzen)`).
- The existing **Translate** button still machine-translates lexicon definitions. Translation requests
  are versioned and queued sequentially to avoid provider rate-limit bursts.

Cached 30 days under `bible_study:original-local:v1:<source>:<book>:<ch>:<v>`.

---

## 4. Linking the translated text to the original words

Goal: hovering *children* in the KJV highlights בְּנֵי, and clicking it opens H1121 — expanding the
original-text panel first if it is collapsed.

`english_alignment_payload(book, chapter, verse, verse_text, tagged_source, allow_scoring)` returns

```json
{"tokens": [{"text": "children", "word_index": 2}, {"text": " ", "word_index": -1}],
 "aligned_count": 19, "method": "tagged"}
```

`word_index` is the index into `original_text_payload(...)["words"]`; `-1` means unlinked. The
token list re-creates the verse verbatim (punctuation and spacing included), so the client can
replace the paragraph HTML without changing the visible text.

There are two strategies.

### 4a. `method: "tagged"` — direct Strong's lookup

Used when the selected translation can be matched against a word-level tagged edition.
`TAGGED_BIBLE_SOURCES` in `lib/strongs_service.py` lists them and
`_tagged_source_for_bible()` decides which one applies:

| Key | Tagged edition | Applied to |
| --- | --- | --- |
| `kjv` | CrossWire `KJV` — King James Version (1769) with Strong's Numbers and Morphology | abbreviation `KJV`/`KJVCPB`/`AKJV`/`AV`, or a name containing "King James" |
| `svv` | CrossWire `DutSVVA` — Statenvertaling met Strong-nummers | every `nl` translation |

`data/tagged_bibles/<source>/<Book>.json.gz` stores each verse as runs of words with the Strong's
number that edition's tagging assigned to them:

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
   and not to אֵת. Old Online-Bible parsing codes (`H8804`, `G5656`, …) are already dropped at
   build time because they are above the highest real dictionary entry (H8674 / G5624).
3. When a code occurs several times in the verse, take the **nearest still unused** occurrence to
   the previously assigned token, preferring forward on a tie. This keeps repeated verbs
   (`came … came` in Exodus 1:1) in order while still allowing the translator's re-ordering
   (`he gave his only begotten Son` vs. `υἱὸν αὐτοῦ τὸν μονογενῆ ἔδωκεν`).
4. The shown edition is never byte-identical to the tagged module — the API.Bible KJV differs in
   pilcrows and punctuation, and the HSV is a whole revision of the Statenvertaling. An LCS pass
   transfers the mapping from the tagged word sequence onto the displayed word sequence, matching
   words after stripping diacritics and allowing a short suffix difference (`beginne` ↔ `begin`).
   If fewer than 60 % of the displayed words are recovered the tagged result is discarded — so a
   free paraphrase silently gets no links instead of wrong ones.

### 4b. `method: "lexicon"` — scored alignment (English only, no tags)

Only used for English translations without a tagging (`allow_scoring`), because the scoring data
is English. The link is inferred:

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

A translation that is neither tagged nor English gets no alignment at all; the endpoint answers
`supported: false` and the verse renders as plain text.

Both results are cached 30 days under
`bible_study:alignment:v4:<source>:<scoring>:<book>:<ch>:<v>:<sha>`.

---

## 5. Client behaviour

In `_bible_study_script.html`:

- After verse text is rendered (`applyBibleStudyPayloadToDom`, or on first page load),
  `loadBibleStudyWordAlignment()` posts the displayed verse text to `bible_study_word_alignment`
  and replaces the paragraph with tokenised HTML. It only runs when `combine_verses` is off and
  the translation label starts with `EN -` or `NL -` (`bibleStudySupportsAlignment`).
- Aligned words get `<span class="bs-aligned-word" data-verse data-word-index>`.
- `syncOriginalSentenceHover` / `syncOriginalSentenceSelection` now cover three surfaces at once:
  the original sentence tokens, the word-cloud buttons *and* the aligned translated words, so
  hovering or selecting any of them highlights the others.
- Clicking an aligned word calls `openBibleStudyOriginalWordFromEnglish()`. If the verse's
  "Original text" panel is collapsed it is opened, the payload is fetched, and
  `bsPendingAlignedSelection` makes the panel select that exact word (and scroll to it) once
  loaded.

The collapsible **"Legend — how does this page work?"** block in `bible_study.html` explains the
same behaviour in plain language for readers, including where all data comes from.

---

## 6. Tagged data submodule and regeneration

The parent project tracks only a pinned gitlink for `data/tagged_bibles`; generated data belongs in
the `walkasjesus_tagged_bibles` repository. After cloning the parent project, initialise it with:

```bash
./walkasjesus_website/update_tagged_bibles.sh
```

The script runs `git submodule update --init --recursive` and prints the exact revision. See the
submodule README for publishing and regeneration details.

```bash
pip install pysword                             # optional, only for this command
python manage.py build_tagged_strongs_index     # all sources
python manage.py build_tagged_strongs_index kjv # one source
python manage.py build_tagged_strongs_index svv --module-path /path/to/extracted/module
```

Without `--module-path` the command downloads the SWORD module listed in `TAGGED_BIBLE_SOURCES`.
Notes and psalm headings are stripped, parsing codes are filtered out, and the result is committed
to the tagged-data submodule — so there is no runtime dependency on pysword. Per source it writes:

- `data/tagged_bibles/<source>/<Book>.json.gz` — the tagged word runs,
- `data/tagged_bibles/<source>/_usage.json.gz` — the Strong's → renderings concordance,
- `data/local_bibles/<key>/<Book>.json.gz` — the plain verse text, only when the source definition
  has a `local_bible` key (the Statenvertaling does; the KJV does not, since API.Bible serves it).

Licences: the CrossWire `KJV` module is `DistributionLicense=GPL` (compatible with this project's
GPL-3.0); `DutSVVA` is `DistributionLicense=Public Domain`.

### Adding another tagged translation

1. Find a SWORD module with `Feature=StrongsNumbers` and an acceptable `DistributionLicense` in
   <https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/>.
2. Add an entry to `TAGGED_BIBLE_SOURCES` (key, label, module name, URL, optional `local_bible`)
   and run the build command.
3. Teach `_tagged_source_for_bible()` which translations map to the new key, add the language
   prefix to `bibleStudySupportsAlignment` in the client script, and — if the glosses should drive
   the interface language — add the language to `GLOSS_SOURCE_BY_LANGUAGE`.
4. To expose the edition itself as a selectable Bible, mirror `LocalStatenvertalingBible` in
   `models/bibles.py` and register it in `BibleTranslation._build_all_bibles`.

Known remaining options: STEPBible publishes `TTESV` (ESV, **CC BY-NC** — not usable here) and
`TTAraSVD` (Arabic Smith–Van Dyck, CC BY-SA, already in `data/stepbible/Tagged-Bibles/`).
CrossWire also ships tagged German/French/Spanish/Russian editions if those languages are added.

---

## 7. Caching and quota

| Key prefix | TTL | Contents |
| --- | --- | --- |
| `bible_study:v1:…` | `BIBLE_API_CACHE_TIMEOUT_SECONDS` (6 months) | verse text per translation |
| `bible_study:original:v15:…` | 30 days | original-language payload per verse |
| `bible_study:original-local:v1:…` | 30 days | same payload enriched with interface-language glosses |
| `bible_study:alignment:v4:…` | 30 days | translated↔original token mapping |
| `bible_study:search:…` | 7 days | API.Bible search results |

Bump the `vNN` in the cache key whenever the shape of a payload changes, otherwise stale entries
are served. `BibleTranslationUsageDaily` records every API.Bible hit; `consume_bible_api_quota`
raises `BibleApiRateLimitExceeded` (HTTP 429) when the daily allowance is spent. The alignment
and original-text endpoints never touch the API, so they are free.

## 8. Attribution requirements

- STEPBible data: credit "STEP Bible" linked to <https://www.stepbible.org> (CC BY 4.0).
- CrossWire tagging: CrossWire Bible Society — `KJV` under GPL, `DutSVVA` public domain.
- Per-translation copyright strings from API.Bible are rendered under each verse card.
