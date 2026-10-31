import re
import time
from collections import Counter

import polib
import requests


class PoTranslator:
    MASK_PATTERN = re.compile(r'%(?:\([^)]+\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs]|\{\{.*?\}\}|\{%.*?%\}|<[^>]+>', re.DOTALL)
    MAX_CHUNK_LENGTH = 5500
    draft_marker = None

    @staticmethod
    def needs_translation(entry):
        has_draft = bool(entry.msgstr) or bool(entry.msgstr_plural) and all(entry.msgstr_plural.values())
        return not entry.obsolete and not entry.translated() and not (
            has_draft and 'Machine translation draft:' in entry.tcomment
        )

    def __init__(self, request_interval=1.0):
        if request_interval < 0:
            raise ValueError('Request interval must not be negative.')
        self.request_interval = request_interval
        self._last_request_at = None

    def _mask_tokens(self, text):
        replacements = []

        def replace(match):
            token = f'__WAJ_TOKEN_{len(replacements)}__'
            replacements.append((token, match.group(0)))
            return token

        masked = self.MASK_PATTERN.sub(replace, text)
        return masked, replacements

    def _unmask_tokens(self, text, replacements):
        result = text
        for token, original in replacements:
            result = result.replace(token, original)
        return result

    def _translate_chunk(self, text, source_language, destination_language):
        if self._last_request_at is not None:
            wait = self.request_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()
        response = requests.get(
            'https://translate.googleapis.com/translate_a/single',
            params={
                'client': 'gtx',
                'sl': source_language,
                'tl': destination_language,
                'dt': 't',
                'q': text,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        segments = data[0] if isinstance(data, list) and data else []
        translated = ''.join(segment[0] for segment in segments if isinstance(segment, list) and segment and segment[0])
        if not translated.strip():
            raise ValueError('Translation service returned no translated text.')
        return translated

    def _translate_text(self, text, source_language, destination_language):
        masked_text, replacements = self._mask_tokens(text)
        paragraphs = masked_text.split('\n\n')
        translated_paragraphs = []

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                translated_paragraphs.append('')
                continue

            translated_chunks = []
            for chunk in self._split_chunks(paragraph):
                translated_chunks.append(self._translate_chunk(chunk, source_language, destination_language))
            translated_paragraphs.append(' '.join(translated_chunks))

        translated = '\n\n'.join(translated_paragraphs)
        expected_tokens = Counter(token for token, _ in replacements)
        actual_tokens = Counter(re.findall(r'__WAJ_TOKEN_\d+__', translated))
        if actual_tokens != expected_tokens:
            raise ValueError('Translation service changed protected placeholders or HTML tokens.')
        if text.startswith('\n') and not translated.startswith('\n'):
            translated = '\n' + translated
        if text.endswith('\n') and not translated.endswith('\n'):
            translated += '\n'
        return self._unmask_tokens(translated, replacements)

    def _split_chunks(self, text):
        text = text.strip()
        if len(text) <= self.MAX_CHUNK_LENGTH:
            return [text]

        chunks = []
        current = []
        current_length = 0

        for word in text.split():
            projected_length = current_length + len(word) + (1 if current else 0)
            if current and projected_length > self.MAX_CHUNK_LENGTH:
                chunks.append(' '.join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length = projected_length

        if current:
            chunks.append(' '.join(current))

        return chunks

    def translate(self, po_file_path, source_language, destination_language, *, entry_filter=None, limit=None):
        if limit is not None and limit < 1:
            raise ValueError('Entry limit must be positive.')
        po = polib.pofile(po_file_path)
        po.metadata['Language'] = destination_language

        entries = [
            entry for entry in po
            if self.needs_translation(entry)
            and (entry_filter is None or entry_filter(entry))
        ]
        if limit is not None:
            entries = entries[:limit]

        completed = 0
        try:
            for index, entry in enumerate(entries, 1):
                if entry.msgid_plural:
                    plural_forms = po.metadata.get('Plural-Forms', '')
                    match = re.search(r'nplurals\s*=\s*(\d+)', plural_forms)
                    if not match:
                        raise ValueError(f'Missing nplurals metadata in {po_file_path}')
                    singular = self._translate_text(entry.msgid, source_language, destination_language)
                    plural = self._translate_text(entry.msgid_plural, source_language, destination_language)
                    entry.msgstr_plural = {
                        form: singular if form == 0 else plural
                        for form in range(int(match.group(1)))
                    }
                else:
                    entry.msgstr = self._translate_text(entry.msgid, source_language, destination_language)
                if 'fuzzy' in entry.flags:
                    entry.flags.remove('fuzzy')
                if self.draft_marker:
                    entry.flags.append('fuzzy')
                    entry.tcomment = '\n'.join(filter(None, [entry.tcomment, self.draft_marker]))
                completed += 1
                po.save()
                if index % 25 == 0 or index == len(entries):
                    print(f'Translated {index}/{len(entries)} entries.', flush=True)
        finally:
            # Keep completed work resumable, but propagate failures to the caller.
            po.save()
        return completed
