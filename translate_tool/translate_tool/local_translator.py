import json
import re
from pathlib import Path

from .po_translator import PoTranslator


class LocalPoTranslator(PoTranslator):
    """Run an installed Argos CTranslate2 model without network access."""

    def __init__(self, model_path):
        super().__init__(request_interval=0)
        self.model_path = Path(model_path).expanduser()
        self._translator = None
        self._tokenizer = None
        self._languages = None
        self.draft_marker = 'Machine translation draft: local Argos; review in Rosetta.'

    def _load_model(self):
        metadata_path = self.model_path / 'metadata.json'
        if not metadata_path.is_file():
            raise ValueError(f'Local model metadata not found: {metadata_path}')
        metadata = json.loads(metadata_path.read_text())
        self._languages = (metadata['from_code'], metadata['to_code'])
        try:
            import ctranslate2
            import sentencepiece
        except ImportError as exc:
            raise ValueError(
                'Local inference dependencies are missing. Install translate_tool/requirements-local.txt '
                'in your translation environment.'
            ) from exc
        self._tokenizer = sentencepiece.SentencePieceProcessor(
            model_file=str(self.model_path / 'sentencepiece.model'),
        )
        self._translator = ctranslate2.Translator(
            str(self.model_path / 'model'), device='cpu', compute_type='int8',
            inter_threads=1, intra_threads=2,
        )

    def _translate_chunk(self, text, source_language, destination_language):
        if self._translator is None:
            self._load_model()
        if self._languages != (source_language, destination_language):
            raise ValueError(f'Installed model supports {self._languages}, not {source_language}->{destination_language}.')
        tokens = self._tokenizer.encode(text, out_type=str)
        if len(tokens) > 512:
            raise ValueError('Local translation segment exceeds 512 tokens; shorten it before translating.')
        result = self._translator.translate_batch(
            [tokens], beam_size=4, max_input_length=0, max_decoding_length=1024,
        )[0]
        translated = self._tokenizer.decode(result.hypotheses[0])
        if not translated.strip():
            raise ValueError('Local model returned no translated text.')
        return translated

    def _translate_text(self, text, source_language, destination_language):
        # Small translation models corrupt synthetic mask tokens. Keep markup
        # and placeholders out of inference, retaining them byte-for-byte.
        pieces = []
        offset = 0
        for match in self.MASK_PATTERN.finditer(text):
            pieces.append(self._translate_plain(text[offset:match.start()], source_language, destination_language))
            pieces.append(match.group(0))
            offset = match.end()
        pieces.append(self._translate_plain(text[offset:], source_language, destination_language))
        return ''.join(pieces)

    def _translate_plain(self, text, source_language, destination_language):
        parts = re.split(r'(\n+)', text)
        for index, part in enumerate(parts):
            if not re.search(r'[^\W\d_]', part):
                continue
            leading = part[:len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            translated = [
                self._translate_chunk(chunk, source_language, destination_language)
                for chunk in self._split_chunks(part.strip())
            ]
            parts[index] = leading + ' '.join(translated) + trailing
        return ''.join(parts)

    MAX_CHUNK_LENGTH = 1000
