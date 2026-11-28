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
| Passage selection, translations and word alignment | [templates/bible_study/_bible_study_script.html](templates/bible_study/_bible_study_script.html) |
| Shared original-language renderer, word interactions and occurrence previews | [templates/bible_study/_study_panels_script.html](templates/bible_study/_study_panels_script.html) |
| Shared passage-preview dialog | [templates/bible_study/_study_reference_preview.html](templates/bible_study/_study_reference_preview.html) |
| Shared commentary loading/rendering and detail-page adapters | [../static/js/customjs.js](../static/js/customjs.js) |
| Bible Study and shared panel styling | [templates/bible_study/_bible_study_styles.html](templates/bible_study/_bible_study_styles.html) |

The page renders the first passage server-side, then everything else (changing passage,
translations, toggles, panels) happens through AJAX so the API.Bible quota is only spent on
verses that are actually shown. On desktop (992px and wider), the study container
uses the available screen width with small side margins; smaller layouts retain
their existing responsive behavior.
Previous/next passage controls appear above and below the verses, including
after AJAX updates and in combined and verse-by-verse modes. Navigating from
the lower controls scrolls to the beginning of the newly selected passage.

### Shared panels on other pages

Maimonides, steps, Law of Messiah and lessons use the same commentary handlers and
`WAJBibleStudyPanels` original-language controller as Bible Study. The base template
loads the shared script, preview template and styles once. Detail-page adapters only
provide the passage, selected translation and navigation destination; they do not
render their own word details.

Each original-language controller scopes DOM queries and interactions to its passage
root, so repeated verse numbers in different passages cannot affect one another.
Long original-language ranges are fetched progressively using the server's returned
verse range; cross-chapter references get a separate controller per chapter.
Occurrence buttons open the shared passage preview in the selected translation.
Its study button and Strong's links navigate to Bible Study on detail pages, while
the Bible Study page keeps its existing in-page passage navigation.

### Endpoints

| URL name | Purpose |
| --- | --- |
| `bible_study` | Page render, also honours deep links (`?book=&chapter=&start_verse=…`) |
| `bible_study_verses` | Verse text for one translation and verse range (cached 25 days) |
| `bible_study_chapter_meta` | Last verse number of a chapter, from `data/bible_study_chapter_index.json` |
| `bible_study_original_text` | Original-language words + Strong's candidates for a verse range |
| `bible_study_word_alignment` | Maps the words of a translated verse onto original-language word indexes |
| `bible_study_search` | Full-text search with reverse word study, or local Strong's dictionary/occurrence search |

### Section headings in combined text

When "Combine verses into continuous text" and "Show section headings from the
translation" are enabled, API.Bible translations show their own editorial headings
from the book `/sections` metadata endpoint. The heading checkbox defaults to on,
is disabled in per-verse mode, and retains its selection when switching modes.
The `show_sections=0` URL parameter switches it off; AJAX and browser cache keys
also distinguish the setting. This
fetches titles and verse boundaries, not additional verse text. Only sections
overlapping the displayed source verses appear, including the active heading when
the passage starts halfway through a section. Source numbering is mapped to the
displayed Hebrew references; headings are not copied between translations. Book
metadata includes sections that begin in a previous chapter, unlike chapter lists.

Book metadata (including a 404 indicating no sections) is cached for the configured
25-day API TTL. Uncombined mode and local translations do not fetch section metadata.
Transport/validation failures are logged and shown beside the translation while
leaving the verses available; failures are not cached. Metadata requests count toward
the normal device API quota.

Study verse requests explicitly exclude inline titles to avoid duplicates and titles
being appended to the preceding verse. Study caches use a new version to avoid
reusing old text with embedded titles. Headings are displayed separately and excluded
from the verse-copy controls.

In side-by-side combined columns, each displayed verse starts at the same height.
Heading slots reserve the same space in translations without that heading, and
headings within the text have a blank line above them. Combined verse ranges span
the height of the corresponding individual verses without duplicating their text.
Alignment is recalculated after loading, font loading and resizing; stacked mobile
columns use their natural heights.

### Hebrew verse numbering

Old Testament passage selection, original text and chapter navigation use TAHOT's
Hebrew references. Its paired English/KJV references provide the conversion to
source verses, including chapter changes (Hebrew Hosea 2:3 is KJV 2:1, and
Hebrew Joel 3:1 is KJV 2:28). Differing source references appear beside each
translation. The original-text and alignment caches distinguish reference systems.

The local Statenvertaling uses KJV storage slots, with embedded Dutch references
such as `[01:12]`. These determine its displayed numbering and the corresponding
HSV lookup outside Psalms; this assumes HSV follows those markers and is not an
independently verified mapping for every passage. In Psalms the local SV's embedded
markers are split to separate the title and body, while HSV uses Hebrew numbering.
Naardense is treated as Hebrew-numbered for Psalms, Hosea and Joel; the local Complete
Jewish Bible is treated as Hebrew-numbered for Hosea. Other profiles are not
verified: their technical status and profile limitations appear only in the
staff-only Bible cache management overview. Unchanged references display without
a verification warning. At known numbering differences no potentially incorrect
verse is substituted; visitors see a short message asking them to choose another
translation. Actual split/merged verse-boundary notices remain visible.

Psalm 30:1 is a Hebrew title and has no numbered KJV counterpart; a dash marks
the absence. For merged or split verse boundaries the complete source verse is
shown with a warning that it can contain adjacent Hebrew text. Ambiguous source
boundaries do not produce automatic translated-word alignments.

Concordance and KJV/local-SV search references are converted from English storage
numbering; HSV search references outside Psalms use the local SV markers as an
approximation. Unknown profiles cannot be converted reliably at known numbering
differences. Dictionary occurrence results display the Hebrew reference and
translation reference, and fetch translation text using that same mapping.
Detail-page links may explicitly request `reference_system=english`.
If such a range maps across Hebrew chapters, it must be opened as separate verses.

### Automatic numbering checks and budgeted source acquisition

The staff Bible overview links to read-only automatic reports. There are no manual
checklists or approval controls. Historical checklist entries are archived by the
migration, not discarded. Reports do not automatically activate production mappings.
Console summaries show the translation ID and readable name from the already
loaded catalogue, without extra API requests. Missing catalogue names are explicitly
labelled as unavailable.

The script checks fresh cache first and acquires missing risk passages directly
using provider book, chapter and verse IDs. It does **not** use the study display
mapping, so an unverified mapping cannot prevent acquiring its source evidence.
Metadata resolves three-versus-four-chapter editions and prevents requesting
nonexistent verse numbers. Only missing risk ranges are fetched, not whole Bibles.

```bash
cd walkasjesus_website
./check_bible_numbering.sh
./check_bible_numbering.sh --language=nl
./check_bible_numbering.sh --language=nl --books=all
./check_bible_numbering.sh --language=nl --books='numbers'
./check_bible_numbering.sh --bible-ids 89f6d2447cc48fbd-01 --books Joel
./check_bible_numbering.sh --max-requests 10
./check_bible_numbering.sh --cache-only --no-save --output /tmp/bible-numbering-report.json
```

The default and maximum budget is **100 HTTP requests per run**, including
catalogues and failed attempts. There are no automatic retries or redirects.
Requests are spaced by 0.5 seconds (`--sleep` overrides). When the budget runs out,
the script stops acquisition, writes its current report and resumes from fresh
cache on the next run. Default acquisition order is Joel, Hosea, Psalms per
translation. `--bible-ids` and `--books` narrow the work. Without explicit IDs, the
script uses translations already present in the passage cache, including disabled
translations previously cached. Licence-limited translations such as NBV21/BGT
are **not automatically prefetched**; their existing cache is still checked.
`--language=nl` filters both reports and acquisition to Dutch translations from the
already loaded catalogue, without a network lookup. It intersects with `--bible-ids`
when both are given; absent catalogue languages cause an explicit error.
Book names are case-insensitive canonical names (`numbers`, `ChroniclesFirstBook`,
etc.); multiple names can follow `--books`. `--books=all` derives risk cases for all
books from the local reference mappings, including Numbers, Chronicles and Malachi.
Books without known mapping differences do not cause source acquisition. This does
not prove they have no edition-specific merged/split verses; structural checks still
inspect all fresh cached passages. Books without a local numbering mapping (the NT
and deuterocanonical books) report `no_reference_mapping`, not successful verification.
The default remains Joel, Hosea and Psalms.

The equivalent command is `python manage.py check_bible_numbering`. Both entry
points keep ordinary API.Bible access disabled **before Django starts**, including
catalogue loading by model imports. Only the dedicated, counted acquisition client
can make requests after startup. `--cache-only` or `--max-requests 0` guarantees zero
requests. `--no-save` skips database report writes, not source acquisition.

The command reads `bible_api_cache.json`; acquired source responses are stored there
with the configured 25-day TTL. `--cache-path` selects another existing file.
Only fresh, expiry-bearing text-passage entries are examined; expired
entries, legacy entries without a usable expiry, unsupported content formats and
entries whose remaining TTL exceeds the configured 25-day lifetime are excluded.
Missing data remains incomplete when the budget or licence prevents acquisition. The
command does not inspect Django's derived text cache because it often lacks the
original provider verse markers.

Reports identify missing requested verses, malformed/overlapping verse markers,
empty verse text, conflicting cached boundaries and merged ranges. Fresh provider
chapter catalogues supply chapter coverage counts where available; missing cached
chapters are not treated as missing chapters in the translation. For selected OT books the
local STEPBible mapping supplies expected risk cases; cached Hebrew or English
references are only **available source evidence**, not proof of correct
translation boundaries. Fresh book catalogues can mark OT checks inapplicable to
NT-only editions. Equal counts do not prove equal verse boundaries.

By default the latest text-free report is stored in the read-only admin overview.
`--no-save` avoids database writes;
`--output` also writes JSON without scripture text. `--fail-on-findings` exits
nonzero when structural findings need attention. No finding, missing cache data,
or successful scan automatically confirms a translation.

Naardense Joel was explicitly checked against provider metadata and passages:
four numbered chapters, Joel 3:1–5 containing the Spirit-outpouring passage, and
Joel 4:1–21 containing the nations/judgement passage. Its study mapping uses Hebrew
chapter numbering, rather than KJV Joel 2:28–32 / 3:1–21. Regression tests cover
both chapter transitions and final verses.

### Text search and dictionary word study

Three matching search boxes are shown in Settings:
**Search Bible passage**, **Search words in Bible translation**, and
**Search words in Strong's Dictionary**.
The three boxes sit side by side on desktop and stack on smaller screens. Each has
its own input and Search button. **Search words in Bible translation** has Options
beside its search button; dictionary results have separate Bible occurrence Options.
Passage search retains
autocomplete and Enter-to-open behavior. The other boxes retain independent query
text and route directly to their respective search methods on Search or Enter.
The second box always uses `mode=text`: it searches the first selected translation
without original-word analysis, candidate filtering, or an alignment warning. The
word-study checkbox and Search method selector have been removed. Options and Apply
apply only to this text search (scope, page size, sorting, fuzziness, exact phrase).
Dictionary occurrence options reuse the same template and scope controls, with
independent Bible section/book range, page size and canonical/reverse-canonical
order settings. Spelling, exact-phrase and relevance controls appear only in text
search, since occurrence search matches Strong's codes rather than translation text.
Defaults remain the whole Bible in canonical order, 50 results per page. The Original
language checkboxes are directly in the third box: Hebrew (initially checked) and
Greek. Check either or both; searching with neither selected shows an explicit
validation message. There is no dropdown or extra dictionary description below Search.
Word study is shown only by the third box's dictionary search.
**Also search Strong in Bible** is checked by default, preserving automatic
occurrence fetching. Unchecking it uses the existing local dictionary endpoint
without `study_scope=all`: dictionary matches are paged locally, and selected
lemma details use only local Strong's data. Selection changes in this mode do
not fetch Bible verses. **Search selected words in Bible** explicitly fetches
occurrences of all selected codes in the first selected translation, without
changing the checkbox preference. Clicking it scrolls to the loading panel and then
the verse results (or an error), below the dictionary details, with room for the
fixed navigation bar. The loading message distinguishes local dictionary searches
from Bible occurrence searches. Existing dictionary details are kept when this
button fetches verses, preventing detail-loading layout shifts from moving the
verse results out of view. The button is disabled when nothing is selected.
Only this explicit button activates result scrolling and late-detail scroll
correction. Selecting or deselecting word buttons resets that behavior and restores
keyboard focus without scrolling. Applying occurrence options searches the same
selected codes without activating result scrolling. Scope filters apply to verses,
not to the validity of selected dictionary entries: selections with no occurrences
in the chosen scope produce an empty result rather than a selection error.
Dictionary result summaries show the query followed by each selected Strong's code
and its dictionary lemma. The pagination line shows the reference range without
repeating those codes. Multiple selections keep each code paired with its own lemma.
The introductory paragraph is omitted to keep Settings compact. A compact Legend
button sits at the right of the Settings heading, moving onto a separate line on
phones. Its accessible label and tooltip retain the longer explanation. The full-width,
initially collapsed legend explains the three searches, text options, dictionary
selection and paging, translations, passage navigation, combined/per-verse display,
original-word details, word-link limitations, commentary and data sources.

#### Legacy reverse-word endpoint

The API still supports `mode=verses` for existing clients, but the page no longer
uses it. In this legacy mode, **Original-word study** appears above verse results.
The candidates come from the words matched across the complete search, not from a
generic dictionary guess. KJV and compatible Dutch editions use the existing local
Strong's tagging and word alignment; untagged English editions use lexicon-scoring
estimates. Other editions, or Dutch text that differs too much from the tagged
Statenvertaling, may remain unaligned. The UI says so rather than inventing a root.
The panel reports how many search results could not be aligned reliably, including when
some candidates were found. No candidates is not proof that no Hebrew/Greek equivalent
exists. API.Bible's default `AUTO` fuzziness can return many verses without the literal
query word; reverse study only links literal query words (and English inflections).
Thus a search for Dutch `leef` does not automatically analyse every occurrence of `leven`.
Combined-verse results (such as BGT's `GEN.6.3-GEN.6.4`) are aligned as one passage,
while candidate details retain the individual verse and original token index.
Hebrew service prefixes are not presented as root candidates. NT results retain
their actual Greek originals. Multiple Strong's words can match the same search term.
Candidate buttons are multi-select filters and load the same full Strong's renderer
used by the original-text panels. Their Hebrew lemmas reuse the shared root/service
classification and colors: dark brown (`#3d2f08`) for roots and gray (`#757575`) for
service words, matching the Strong's details. Analysis uses local STEPBible/tagged data and does
not fetch an original Bible translation or auto-translate definitions.

Only the first candidate starts selected, filtering verses immediately.
Selecting additional words includes their related verses. Deselecting one removes verses linked
only to that word, across every result page; verses linked to another selected
word remain. Only verses linked to selected candidates remain. Deselecting all
shows no verses. Selection is retained during pagination and resets on a new search.
Every page button shows the range of verses actually present on that page, including
after filtering and in dictionary mode.

Verse-backed candidates retain matched token indexes. Their details use the exact
STEPBible form from a displayed verse (or the first matching occurrence if none is on
the page), components,
grammar and letter total, just like clicking the original text. The candidate button
uses that same occurrence form, without transliteration; dictionary-only buttons
show the lemma. On the Dutch site, candidate labels and dictionary word components
prefer the local Statenvertaling rendering over the English lexicon gloss.
Complete-search snapshots are cached separately by interface language.
English lexicon definitions remain source text unless explicitly translated.
Dictionary-only
details explicitly show a lemma, with its tagged lexical component but no invented
verse-specific morphology. Lexicon searches preserve the matched extended Strong's
variant instead of always loading the first variant of the base number.
For example, H2416A has the lemma `חַי` (18), but Genesis 1:20 uses the feminine
singular adjective `חַיָּ֑ה` (23). Neither form is an error; lemma and inflected form
must not be presented as interchangeable. H2416 also groups other lexical variants.
Search details open **parts and letters** by default, with a top-right close button
inside a shared border enclosing both the large Hebrew word and its analysis;
click its summary to reopen. An outer border groups the word analysis and its Strong's
cards. Hebrew details omit the duplicate standalone direct gloss and grammar lines,
as does search word study; Greek original-text details retain them.
Hover synchronization preserves token index zero, including the first word in a verse.
Each Strong's card is a keyboard-accessible collapsible
disclosure with a plus/minus indicator. Duplicate verse buttons, the occurrence-form
caption, and the "Show verses with this Strong's number" button have been removed.

The third box's **Hebrew** and **Greek** checkboxes filter
dictionary matches before pagination, without removing translated full-text
verse results. Select Greek or both to include NT original-word candidates.
The endpoint parameter is `original_language=hebrew|greek|both`, defaulting to
`hebrew`; occurrence searches must match the selected language.

Use the third box, **Search words in Strong's Dictionary**, to search
local lemmas (also without vowel marks), transliterations, English short glosses,
Strong's numbers, and available Dutch tagged renderings. Only the first match is
selected automatically. Selected words show their details and the union of their occurrence
verses in the first
selected translation. These are occurrences of the original Strong's number, so the
displayed translation need not contain the originally typed search word. The API still
supports book scopes, page size and reverse-canonical sorting, exposed by the
dictionary results' Options button. Verse retrieval uses the existing cache and quota
accounting; unavailable verses and quota failures are reported explicitly.
Concordance references are sorted canonically and deduplicated. STEPBible's KJV
alternate numbering is used for KJV/SVV editions (for example 2 Corinthians 13:14);
other NT editions use its NRSV numbering. Unnumbered Psalm headings (verse 0) are
excluded from the numbered-verse results.

The search endpoint accepts `mode=verses` (default), `text` (text only), `lexicon`, `detail`, or `strongs`.
`detail` and `strongs` require a valid H/G number in `query`. Full details are loaded
for selected candidates. The page sends `study_scope=all` for dictionary selection;
text-only search uses ordinary result pages and performs no alignment. Legacy
`mode=verses&study_scope=all` retrieves all API result pages in batches of 100 and
caches the complete result/alignment snapshot. Dictionary mode
accepts `selected_strongs` (comma-separated base codes, empty for none), keeps all
candidate buttons visible, and fetches only the requested page of occurrence texts.
Omitting `selected_strongs` selects the first dictionary candidate.
The union uses the extended lexical variants matched by the dictionary rather than
unrelated senses sharing a base number. Legacy calls without `study_scope=all`
retain their page-based behavior. Quota exhaustion during collection returns an
explicit error, never a partial result claimed to cover the complete search.

Local Statenvertaling and CJB full-text searches read their bundled verse data and never
call API.Bible or consume API quota. They support case-insensitive whole words (all
query words must occur), quoted contiguous phrases, ranges, sorting and pagination.
For local translations `AUTO` and `0` both use literal matching; numeric fuzziness above
zero is explicitly unsupported. Local result snapshots are cached before pagination.

The two search modes deliberately need not return the same original words. Full-text
search analyses the selected translation (and API spelling/fuzziness options);
dictionary search matches lexical labels and original forms. Previously, reverse
word study only analysed the first/current page, which hid candidates found later
in the Bible. For "tree", dictionary examples include H5158B (palm-tree, Numbers
24:6, rendered "valleys" in KJV) and H363 (Aramaic tree, Daniel 4); different lexical
meanings and translation choices still explain differences after whole-search analysis.

The shipped primary KJV chapter index covers all 1,189 chapters, including Psalm 77
and three-digit Psalm numbers. Rebuild it without spending API quota using the bundled
tagged KJV data:

```sh
python manage.py build_bible_study_chapter_index --local-kjv
```

Translation-specific chapter metadata takes precedence over this primary fallback.
Explicit passage ranges can also be submitted before autocomplete metadata has loaded.
API.Bible text markers such as `[1-4]` (for example BGT Titus 1:1-4) are treated as a
single combined text block, not discarded or artificially split into separate verses.
When requesting an individual member of such a group, the API's combined text is shown.

### Query/state parameters

`book`, `chapter`, `start_verse`, `end_verse`, `bible_id` (repeatable, up to 4 columns),
`show_original`, `combine_verses`. `combine_verses=1` shows one block per translation;
`combine_verses=0` shows one card per verse — **word linking only runs in this mode**.
The info icon next to the "Combine verses" checkbox (`.bs-combine-help`, CSS-only tooltip with
`white-space: pre-line`) explains this on/off difference to users; keep it in sync when the modes change.

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
verse, cached 30 days under `bible_study:original:v21:…`:

TAHOT references use the primary English/NRSV verse numbering, with differing Hebrew
numbers in parentheses (for example `Psa.51.7(51.9)`). Word lookup and occurrence links
use the primary reference; the parenthetical annotation must not prevent a match.

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
`local_usage` and each node in the *Outline of Biblical Usage* with Bible references carries a count
button (e.g. `(203x)`); entries without references remain plain list items.
Clicking it opens the integrated **Occurrence Viewer** dialog:
- The upper area displays the text for the currently selected verse in the active translation.
- The lower area displays range buttons chunked in blocks of 25 (e.g. `1. Gen.1:11–Gen.24:60 (25x)`),
  along with all 25 verse buttons for that chunk.
- Clicking any verse button immediately retrieves and displays its text in the upper preview area
  without leaving or duplicating the popup.
- The summary accurately states total occurrences and verse count (e.g. `203x (in 185 verzen)`).
- The existing **Translate** button still machine-translates lexicon definitions. Translation requests
  are versioned and queued sequentially to avoid provider rate-limit bursts.

Cached 30 days under `bible_study:original-local:v35:<reference-system>:<source>:<book>:<ch>:<v>`.

### Hebrew composition and letter information

Hebrew word surfaces use the dark original-text brown (`#3d2f08`) for the lexical root/stem component and gray
for tagged or confidently inferred prefixes, suffixes and grammatical components. This applies to the verse
sentence, word buttons and selected-word details; a legend explains the colors.
Coloring follows STEPBible component boundaries, supplemented by the morphology and
lemma checks described below. If the components do not cover the displayed word exactly, it stays
unsegmented. Vowel points, accents, punctuation and copyable text are preserved.
The lexical component is not necessarily a reconstructed three-consonant root.
Hebrew lemmas beside Strong's numbers use the same colors in Bible Study and inline
details: lexical lemmas are brown, tagged service/grammatical lemmas are gray.

Strong's usage outlines explain the Hebrew verb stems Qal, Niphal, Piel, Pual,
Hiphil, Hophal and Hithpael/Hitpael in hover/focus tooltips. Explanations are Dutch
for the Dutch interface and English otherwise, and describe typical functions
rather than a fixed translation. The same helper is used in inline Strong's
details and retains tooltips when definitions are translated or restored.

For Hebrew TAHOT rows, column 11 encodes the tagged pieces of a word, for example
`H9003=ב=in/{H9036=Op2m=you}`. The parser aligns those pieces with the slash-separated Hebrew
surface in column 1 and labels the STEPBible grammatical codes as prefixes, roots or suffixes.
TEHMC supplies explanations for morphology codes such as `HRd` (definite preposition) and `Op2m`
(object suffix, second-person masculine plural). For Dutch, each piece uses its exact Statenvertaling
rendering when available; otherwise its short gloss is localized. A word can consist only of
attached grammatical parts, with no separate lexical root tagged.
For common service prefixes and directional/emphatic suffixes, the component also shows
possible meanings separately from the occurrence gloss. These are contextual possibilities,
not interchangeable translations of the current verse. A final waw is interpreted using
its tagged morphology or a confidently inferred verb ending: possessive, object, subject
and plural verb endings do not have the same meaning.
When the morphology aligns one-to-one with the tagged components, standalone prepositions,
relative and subordinating particles, and negation are also classified as grammatical.
STEPBible's internal component-origin/analysis-boundary note and repeated lexicon
lemma attribution are not shown in word details; dataset attribution remains
available in the legend.

Hebrew punctuation, including the verse-ending `׃`, is gray rather than part of the lexical word.
Tagged section markers `ס` and `פ` are also gray and excluded from letter tooltips and gematria.
The component details show the actual STEPBible-tagged punctuation and explain its function,
including maqqef, paseq, sof pasuq, section markers and inverted nun.
The dictionary
lemma is retained separately while the component shows the actual pointed form in the verse.
For Hitpael verbs, morphology plus an exact consonantal lemma match identifies the regular
two-letter stem prefix (for example `הִתְ`, `מִתְ`, or `יִתְ`). This prefix has no separate
Strong's number: it is verb-stem formation, not an independent service word or a fixed translation.
Imperfect and consecutive verb forms are split at their person prefix (Aleph, Nun, Tav or
Yod) when morphology and the consonants support the tagged lemma, including matching
weak final-he lemmas. Recognizable second-person feminine singular `י`, feminine-plural
`נה`/`ןָ` and masculine-plural `וּ` endings are separated when the remaining stem still matches.
Feminine singular construct
nouns ending in `ת` are split when their lemma ends in `ה` and the other consonants match.
The same lemma and morphology checks recognize selected Qal, Piel and Hiphil perfect endings,
Niphal perfect prefixes and endings where the stem matches the lemma, including selected
initial-nun, initial-yod, final-he and doubled-root weak forms. The checks also recognize regular
Niphal participle prefixes and plural endings, selected masculine Hiphil participle
prefixes and plural endings, selected Qal participle and imperative endings, and matching noun
plural endings, including some lemmas already recorded in the plural. For example, Exodus 6:7
separates the Hiphil participle prefix in `הַמּוֹצִ֣יא`, and Job 12:6 separates the Hiphil
perfect prefix in `הֵבִ֖יא`. Matching Piel masculine singular participle prefixes, selected
feminine perfect and imperative endings, selected Niphal infinitive prefixes, regular dual noun
endings, and matching adjective gender and number endings are also separated. The irregular
plural stems of `בַּת` (H1323), `אָחוֹת` (H0269), and
`חַטָּאת` (H2403) are recognized, including construct and possessive forms such as
`בְּנוֹת` and `אַחְיוֹתֵיהֶם`. In Ezekiel 16:52 the distinctive `אַחְיוֹתֵךְ` is
treated as plural despite the singular STEPBible tag, consistent with the plural form
in BDB and the Bible Hub interlinear; other ambiguous singular forms retain their source tag.
Some Qal weak-verb forms are recognized when assimilation is supported by the pointed
spelling, and regular feminine construct-plural endings can precede a tagged possessive.
For example, Genesis 26:35 separates the person prefix and ending of `וַתִּהְיֶ֖יןָ`
and the construct ending of `מֹ֣רַת`. Uncertain forms remain unsplit: a brown lexical
component may therefore still include an inflection that the data cannot reliably isolate.

The original-text data retains heuristic flags for potentially incomplete analyses and selected
possible overlaps between a stem and an ending. These flags are not displayed as question marks
or underlines. They are editorial inferences, not confidence scores or explicit STEPBible letter
boundaries, and do not detect every uncertain form.

Each component's details identify whether it comes from a STEPBible tag, was inferred from the
word form and morphology, or is a STEPBible lexicon lemma. A source tag does not certify the
displayed boundaries or role: the analysis can adapt them.

The manually assessed test cases in
[`testdata/hebrew_segmentation_reference.json`](testdata/hebrew_segmentation_reference.json)
record expected letter roles for 16 words and cite interlinear or lexicon sources. The Django
test compares each pointed Hebrew letter and role with this fixed fixture. The sources support
the forms and morphology, but the letter boundaries are editorial judgments, not independently
certified annotations or proof of Old Testament-wide accuracy. Run the test from
`walkasjesus_website`:

```shell
./venv/bin/python manage.py test walkasjesus_app.tests.DutchOriginalTextTestCase.test_reference_set_preserves_reviewed_letter_roles --noinput
```

The large Hebrew word distinguishes lexical roots from attached grammatical parts by color.
Clicking the word or its question-mark icon expands the parts-and-letters panel.
Hovering or focusing a Hebrew letter uses the shared brown tooltip to show its name, approximate
pointed sound, standard numerical value, and a traditional pictorial association. Vowels are
included (for example, shin with qamats is `shā`); macrons describe vowels, not word stress.
Sheva is shown as `ə / ∅` because its pronunciation depends on context. This is a letter-level
reading aid, not a complete phonological transcription. The association is explicitly labeled as interpretive background, not the
meaning or translation of that letter. The word total uses standard Hebrew gematria (mispar
hechrechi): consonants count, vowel points and cantillation marks do not, and final forms use the
same values as their regular forms (for example, final mem ם = 40). Gematria is a letter-value sum,
not a method for deriving the word's translation.

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
`bible_study:alignment:v5:<source>:<scoring>:<book>:<ch>:<v>:<sha>`.

---

## 5. Client behaviour

In `_bible_study_script.html`:

- Opening an original-text panel requests only that verse. Results are cached in the browser
  per verse and reference system; already-open panels keep their selected word when another
  verse is opened. Concurrent requests for the same range share one request.
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
| `bible_study:original:v21:…` | 30 days | original-language payload per verse |
| `bible_study:original-local:v11:…` | 30 days | same payload enriched with interface-language glosses |
| `bible_study:alignment:v5:…` | 30 days | translated↔original token mapping |
| `bible_study:search:…` | 7 days | API.Bible search results |

Bump the `vNN` in the cache key whenever the shape of a payload changes, otherwise stale entries
are served. `BibleTranslationUsageDaily` records every API.Bible hit; `consume_bible_api_quota`
raises `BibleApiRateLimitExceeded` (HTTP 429) when the daily allowance is spent. The alignment
and original-text endpoints never touch the API, so they are free.

## 8. Attribution requirements

- STEPBible data: credit "STEP Bible" linked to <https://www.stepbible.org> (CC BY 4.0).
- CrossWire tagging: CrossWire Bible Society — `KJV` under GPL, `DutSVVA` public domain.
- Per-translation copyright strings from API.Bible are rendered under each verse card.
