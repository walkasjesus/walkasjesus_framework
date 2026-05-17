import re
import time

import polib
import requests


class PoTranslator:
    MASK_PATTERN = re.compile(r'%(?:\([^)]+\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs]|\{\{.*?\}\}|\{%.*?%\}|<[^>]+>', re.DOTALL)

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

            translated_paragraphs.append(self._translate_chunk(paragraph, source_language, destination_language))
            time.sleep(0.05)

        translated = '\n\n'.join(translated_paragraphs)
        return self._unmask_tokens(translated, replacements)

    def translate(self, po_file_path, source_language, destination_language):
        po = polib.pofile(po_file_path)

        for entry in po.untranslated_entries():
            try:
                if 'fuzzy' not in entry.flags:
                    entry.flags.append('fuzzy')
                entry.msgstr = self._translate_text(entry.msgid, source_language, destination_language)
            except Exception as ex:
                print(ex)
                print(f'Could not translate entry: {entry.msgid[:120]}')

        po.save()
