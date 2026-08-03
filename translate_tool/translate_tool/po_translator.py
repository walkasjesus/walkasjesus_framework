import re
import time

import polib
import requests


class PoTranslator:
    MASK_PATTERN = re.compile(r'%(?:\([^)]+\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs]|\{\{.*?\}\}|\{%.*?%\}|<[^>]+>', re.DOTALL)
    MAX_CHUNK_LENGTH = 5500

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
        return ''.join(segment[0] for segment in segments if isinstance(segment, list) and segment and segment[0])

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
                time.sleep(0.05)
            translated_paragraphs.append(' '.join(translated_chunks))

        translated = '\n\n'.join(translated_paragraphs)
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

    def translate(self, po_file_path, source_language, destination_language):
        po = polib.pofile(po_file_path)

        entries = [
            entry for entry in po
            if not entry.obsolete and ('fuzzy' in entry.flags or (not entry.msgstr and not entry.msgstr_plural))
        ]

        for entry in entries:
            try:
                entry.msgstr = self._translate_text(entry.msgid, source_language, destination_language)
                if entry.msgstr and 'fuzzy' in entry.flags:
                    entry.flags.remove('fuzzy')
            except Exception as ex:
                print(ex)
                print(f'Could not translate entry: {entry.msgid[:120]}')

        po.save()
