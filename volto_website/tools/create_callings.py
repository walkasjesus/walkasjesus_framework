from import_tool import CallingImporter
from callings_app.models import Calling, SecondaryBibleReference

importer = CallingImporter()
callings = importer.load('./data/callings.csv')

print('Adding %s callings' % len(callings))


def add_bible_ref(calling_id, reference):
    model_reference = SecondaryBibleReference(calling_id=calling_id)
    model_reference.book = reference.book
    model_reference.chapter = reference.start_chapter
    model_reference.verse = reference.start_verse
    model_reference.save()


def add(calling):
    model_calling = Calling()
    model_calling.quote = calling.quote
    model_calling.save()
    [add_bible_ref(model_calling.id, ref) for ref in calling.bible_references]


[add(calling) for calling in callings]
