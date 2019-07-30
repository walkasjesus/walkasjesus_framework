from import_tool import CommandmentImporter
from commandments_app.models import Commandment, SecondaryBibleReference

importer = CommandmentImporter()
commandments = importer.load('./data/commandments.csv')

print('Adding %s commandments' % len(commandments))


def add_bible_ref(commandment_id, reference):
    model_reference = SecondaryBibleReference(commandment_id=commandment_id)
    model_reference.book = reference.book.name
    model_reference.chapter = reference.start_chapter
    model_reference.verse = reference.start_verse
    model_reference.save()


def add(commandment):
    model_commandment = Commandment()
    model_commandment.title = commandment.title
    model_commandment.save()
    print(f'Added commandment {model_commandment.id}')
    [add_bible_ref(model_commandment.id, ref) for ref in commandment.bible_references]


[add(commandment) for commandment in commandments]
