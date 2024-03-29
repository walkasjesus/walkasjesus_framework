import polib
from google_trans import Translator


class PoTranslator:
    def translate(self, po_file_path, source_language, destination_language):
        po = polib.pofile(po_file_path)
        translator = Translator()

        try:
            for entry in po.untranslated_entries():
                # Mark as fuzzy as it was machine translated, humans will know to check the translation
                entry.flags.append('fuzzy')
                translation = translator.translate(entry.msgid, src=source_language, dest=destination_language)
                entry.msgstr = translation.text
        except Exception as ex:
            print(ex)
            print('Could not translate all items, stopped on above error.')

        po.save()
