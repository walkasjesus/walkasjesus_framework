import polib
from google_trans import Translator


class PoTranslator:
    def translate(self, po_file_path, source_language, destination_language):
        po = polib.pofile(po_file_path)
        translator = Translator()

        for entry in po.untranslated_entries():
            translation = translator.translate(entry.msgid, src=source_language, dest=destination_language)
            entry.msgstr = translation.text

        po.save()
