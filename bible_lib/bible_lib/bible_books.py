from enum import Enum, EnumMeta


class EnumWithSpaces(EnumMeta):
    """
    This is a workaround for the following issue:
    You can look up a python enum by value like this:
    my_enum['enum_value'],
    however it turns out it does not work if the value contains spaces!
    Ths metaclass is made to have a workaround for this issue.
    """
    def __getitem__(cls, key):
        for member in cls.__members__.values():
            # Match on value name or value text, so both SamuelFirstBook and '1 Samuel' work
            if member.value.replace("_", " ") == key or member.name == key:
                return member
        raise KeyError(f"No member named '{key}' in {cls.__name__}")


class BibleBooks(Enum, metaclass=EnumWithSpaces):
    Genesis = 'Genesis'
    Exodus = 'Exodus'
    Leviticus = 'Leviticus'
    Numbers = 'Numbers'
    Deuteronomy = 'Deuteronomy'
    Joshua = 'Joshua'
    Judges = 'Judges'
    Ruth = 'Ruth'
    SamuelFirstBook = '1 Samuel'
    SamuelSecondBook = '2 Samuel'
    KingsFirstBook = '1 Kings'
    KingsSecondBook = '2 Kings'
    ChroniclesFirstBook = '1 Chronicles'
    ChroniclesSecondBook = '2 Chronicles'
    Ezra = 'Ezra'
    Nehemiah = 'Nehemiah'
    Tobit = 'Tobit'
    Judith = 'Judith'
    Esther = 'Esther'
    Wisdom = 'Wisdom'
    Sirach = 'Sirach'
    Job = 'Job'
    Psalms = 'Psalms'
    Proverbs = 'Proverbs'
    Ecclesiastes = 'Ecclesiastes'
    SongOfSolomon = 'Song of Solomon'
    Isaiah = 'Isaiah'
    Jeremiah = 'Jeremiah'
    Lamentations = 'Lamentations'
    Baruch = 'Baruch'
    Ezekiel = 'Ezekiel'
    Daniel = 'Daniel'
    Hosea = 'Hosea'
    Joel = 'Joel'
    Amos = 'Amos'
    Obadiah = 'Obadiah'
    Jonah = 'Jonah'
    Micah = 'Micah'
    Nahum = 'Nahum'
    Habakkuk = 'Habakkuk'
    Zephaniah = 'Zephaniah'
    Haggai = 'Haggai'
    Zechariah = 'Zechariah'
    Malachi = 'Malachi'
    MaccabeesFirstBook = '1 Maccabees'
    MaccabeesSecondBook = '2 Maccabees'
    Matthew = 'Matthew'
    Mark = 'Mark'
    Luke = 'Luke'
    John = 'John'
    Acts = 'Acts'
    Romans = 'Romans'
    CorinthiansFirstBook = '1 Corinthians'
    CorinthiansSecondBook = '2 Corinthians'
    Galatians = 'Galatians'
    Ephesians = 'Ephesians'
    Philippians = 'Philippians'
    Colossians = 'Colossians'
    ThessaloniansFirstBook = '1 Thessalonians'
    ThessaloniansSecondBook = '2 Thessalonians'
    TimothyFirstBook = '1 Timothy'
    TimothySecondBook = '2 Timothy'
    Titus = 'Titus'
    Philemon = 'Philemon'
    Hebrews = 'Hebrews'
    James = 'James'
    PeterFirstBook = '1 Peter'
    PeterSecondBook = '2 Peter'
    JohnFirstBook = '1 John'
    JohnSecondBook = '2 John'
    JohnThirdBook = '3 John'
    Jude = 'Jude'
    Revelation = 'Revelation'

    @staticmethod
    def abbreviation(book):
        assert isinstance(book, BibleBooks)

        mapping = {
            BibleBooks.Genesis: 'GEN',
            BibleBooks.Exodus: 'EXO',
            BibleBooks.Leviticus: 'LEV',
            BibleBooks.Numbers: 'NUM',
            BibleBooks.Deuteronomy: 'DEU',
            BibleBooks.Joshua: 'JOS',
            BibleBooks.Judges: 'JDG',
            BibleBooks.Ruth: 'RUT',
            BibleBooks.SamuelFirstBook: '1SA',
            BibleBooks.SamuelSecondBook: '2SA',
            BibleBooks.KingsFirstBook: '1KI',
            BibleBooks.KingsSecondBook: '2KI',
            BibleBooks.ChroniclesFirstBook: '1CH',
            BibleBooks.ChroniclesSecondBook: '2CH',
            BibleBooks.Ezra: 'EZR',
            BibleBooks.Nehemiah: 'NEH',
            BibleBooks.Tobit: 'TOB',
            BibleBooks.Judith: 'JDT',
            BibleBooks.Esther: 'EST',
            BibleBooks.Job: 'JOB',
            BibleBooks.Psalms: 'PSA',
            BibleBooks.Proverbs: 'PRO',
            BibleBooks.Ecclesiastes: 'ECC',
            BibleBooks.SongOfSolomon: 'SNG',
            BibleBooks.Wisdom: 'WIS',
            BibleBooks.Sirach: 'SIR',
            BibleBooks.Isaiah: 'ISA',
            BibleBooks.Jeremiah: 'JER',
            BibleBooks.Lamentations: 'LAM',
            BibleBooks.Baruch: 'BAR',
            BibleBooks.Ezekiel: 'EZK',
            BibleBooks.Daniel: 'DAN',
            BibleBooks.Hosea: 'HOS',
            BibleBooks.Joel: 'JOL',
            BibleBooks.Amos: 'AMO',
            BibleBooks.Obadiah: 'OBA',
            BibleBooks.Jonah: 'JON',
            BibleBooks.Micah: 'MIC',
            BibleBooks.Nahum: 'NAM',
            BibleBooks.Habakkuk: 'HAB',
            BibleBooks.Zephaniah: 'ZEP',
            BibleBooks.Haggai: 'HAG',
            BibleBooks.Zechariah: 'ZEC',
            BibleBooks.Malachi: 'MAL',
            BibleBooks.MaccabeesFirstBook: '1MA',
            BibleBooks.MaccabeesSecondBook: '2MA',
            BibleBooks.Matthew: 'MAT',
            BibleBooks.Mark: 'MRK',
            BibleBooks.Luke: 'LUK',
            BibleBooks.John: 'JHN',
            BibleBooks.Acts: 'ACT',
            BibleBooks.Romans: 'ROM',
            BibleBooks.CorinthiansFirstBook: '1CO',
            BibleBooks.CorinthiansSecondBook: '2CO',
            BibleBooks.Galatians: 'GAL',
            BibleBooks.Ephesians: 'EPH',
            BibleBooks.Philippians: 'PHP',
            BibleBooks.Colossians: 'COL',
            BibleBooks.ThessaloniansFirstBook: '1TH',
            BibleBooks.ThessaloniansSecondBook: '2TH',
            BibleBooks.TimothyFirstBook: '1TI',
            BibleBooks.TimothySecondBook: '2TI',
            BibleBooks.Titus: 'TIT',
            BibleBooks.Philemon: 'PHM',
            BibleBooks.Hebrews: 'HEB',
            BibleBooks.James: 'JAS',
            BibleBooks.PeterFirstBook: '1PE',
            BibleBooks.PeterSecondBook: '2PE',
            BibleBooks.JohnFirstBook: '1JN',
            BibleBooks.JohnSecondBook: '2JN',
            BibleBooks.JohnThirdBook: '3JN',
            BibleBooks.Jude: 'JUD',
            BibleBooks.Revelation: 'REV'}

        return mapping[book]
