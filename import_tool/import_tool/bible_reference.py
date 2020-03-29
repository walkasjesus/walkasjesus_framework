import re

from bible_lib.bible_books import BibleBooks


class BibleReference:
    def __init__(self):
        self.book = BibleBooks.Genesis
        self.start_chapter = 0
        self.start_verse = 0
        self.end_chapter = 0
        self.end_verse = 0
        self.ot_nr = ''
        self.ot_rambam_id = ''
        self.ot_rambam_title = ''
        self.author = ''
        self.positive_negative = ''

    @staticmethod
    def create_from_string(verse_string: str):
        reference = BibleReference()

        pattern = r'(.*) (\d+):(\d+)-?(\d+)?:?(\d+)?'
        # translate things like 1 Joh 2:1-3
        match = re.match(pattern, verse_string)
        groups = match.groups()

        reference.book = BibleReference.parse_book(groups[0])

        reference.start_chapter = int(groups[1])
        reference.start_verse = int(groups[2])
        reference.end_chapter = int(reference.start_chapter)
        reference.end_verse = int(reference.start_verse)

        # Extra verse like 1:2-3
        if groups[3] is not None and groups[4] is None:
            reference.end_verse = int(groups[3])

        # Extra chapter like 1:2-2:3
        if groups[3] is not None and groups[4] is not None:
            reference.end_chapter = int(groups[3])
            reference.end_verse = int(groups[4])

        return reference

    @staticmethod
    def parse_book(book: str) -> BibleBooks:
        book_normalized = book.upper().strip().replace('.', '')

        mapping = {
            'GEN': BibleBooks.Genesis,
            'EX': BibleBooks.Exodus,
            'EXO': BibleBooks.Exodus,
            'LEV': BibleBooks.Leviticus,
            'NUM': BibleBooks.Numbers,
            'DEU': BibleBooks.Deuteronomy,
            'DEUT': BibleBooks.Deuteronomy,
            'JOS': BibleBooks.Joshua,
            'JOZ': BibleBooks.Joshua,
            'JDG': BibleBooks.Judges,
            'RI': BibleBooks.Judges,
            'RICHT': BibleBooks.Judges,
            'RUTH': BibleBooks.Ruth,
            'RUT': BibleBooks.Ruth,
            '1 SAM': BibleBooks.SamuelFirstBook,
            '1SA': BibleBooks.SamuelFirstBook,
            '2 SAM': BibleBooks.SamuelSecondBook,
            '2SA': BibleBooks.SamuelSecondBook,
            '1 KON': BibleBooks.KingsFirstBook,
            '1KI': BibleBooks.KingsFirstBook,
            '2 KON': BibleBooks.KingsSecondBook,
            '2KI': BibleBooks.KingsSecondBook,
            '1 KR': BibleBooks.ChroniclesFirstBook,
            '1CH': BibleBooks.ChroniclesFirstBook,
            '1 KRO': BibleBooks.ChroniclesFirstBook,
            '1 KRON': BibleBooks.ChroniclesFirstBook,
            '2 KR': BibleBooks.ChroniclesSecondBook,
            '2CH': BibleBooks.ChroniclesSecondBook,
            '2 KRO': BibleBooks.ChroniclesSecondBook,
            '2 KRON': BibleBooks.ChroniclesSecondBook,
            'EZRA': BibleBooks.Ezra,
            'EZR': BibleBooks.Ezra,
            'NEH': BibleBooks.Nehemiah,
            'TOB': BibleBooks.Tobit,
            'JDT': BibleBooks.Judith,
            'EST': BibleBooks.Esther,
            'JOB': BibleBooks.Job,
            'PS': BibleBooks.Psalms,
            'PSA': BibleBooks.Psalms,
            'SPR': BibleBooks.Proverbs,
            'PRO': BibleBooks.Proverbs,
            'PR': BibleBooks.Ecclesiastes,  # Due to Dutch 'Prediker'
            'ECC': BibleBooks.Ecclesiastes,
            'PRED': BibleBooks.Ecclesiastes,
            'HOOGL': BibleBooks.SongOfSolomon,
            'SNG': BibleBooks.SongOfSolomon,
            'WIS': BibleBooks.Wisdom,
            'SIR': BibleBooks.Sirach,
            'JES': BibleBooks.Isaiah,
            'ISA': BibleBooks.Isaiah,
            'JER': BibleBooks.Jeremiah,
            'KLAAGL': BibleBooks.Lamentations,
            'LAM': BibleBooks.Lamentations,
            'BAR': BibleBooks.Baruch,
            'EZE': BibleBooks.Ezekiel,
            'EZECH': BibleBooks.Ezekiel,
            'EZK': BibleBooks.Ezekiel,
            'DAN': BibleBooks.Daniel,
            'HOS': BibleBooks.Hosea,
            'JOEL': BibleBooks.Joel,
            'JOL': BibleBooks.Joel,
            'AM': BibleBooks.Amos,
            'AMO': BibleBooks.Amos,
            'OB': BibleBooks.Obadiah,
            'OBA': BibleBooks.Obadiah,
            'JONA': BibleBooks.Jonah,
            'JON': BibleBooks.Jonah,
            'MI': BibleBooks.Micah,
            'MIC': BibleBooks.Micah,
            'NAH': BibleBooks.Nahum,
            'NAM': BibleBooks.Nahum,
            'HAB': BibleBooks.Habakkuk,
            'ZEF': BibleBooks.Zephaniah,
            'SEF': BibleBooks.Zephaniah,
            'ZEP': BibleBooks.Zephaniah,
            'HAG': BibleBooks.Haggai,
            'ZACH': BibleBooks.Zechariah,
            'ZEC': BibleBooks.Zechariah,
            'MAL': BibleBooks.Malachi,
            '1MA': BibleBooks.MaccabeesFirstBook,
            '2MA': BibleBooks.MaccabeesSecondBook,
            'MAT': BibleBooks.Matthew,
            'MATT': BibleBooks.Matthew,
            'MAR': BibleBooks.Mark,
            'MARC': BibleBooks.Mark,
            'MRK': BibleBooks.Mark,
            'LUC': BibleBooks.Luke,
            'LUK': BibleBooks.Luke,
            'JOH': BibleBooks.John,
            'JHN': BibleBooks.John,
            'HAN': BibleBooks.Acts,
            'HAND': BibleBooks.Acts,
            'ACT': BibleBooks.Acts,
            'ROM': BibleBooks.Romans,
            '1 COR': BibleBooks.CorinthiansFirstBook,
            '1CO': BibleBooks.CorinthiansFirstBook,
            '1 KOR': BibleBooks.CorinthiansFirstBook,
            '2 COR': BibleBooks.CorinthiansSecondBook,
            '2CO': BibleBooks.CorinthiansSecondBook,
            '2 KOR': BibleBooks.CorinthiansSecondBook,
            'GAL': BibleBooks.Galatians,
            'EF': BibleBooks.Ephesians,
            'EPH': BibleBooks.Ephesians,
            'FIL': BibleBooks.Philippians,
            'PHP': BibleBooks.Philippians,
            'COL': BibleBooks.Colossians,
            'KOL': BibleBooks.Colossians,
            '1 THES': BibleBooks.ThessaloniansFirstBook,
            '1TH': BibleBooks.ThessaloniansFirstBook,
            '2 THES': BibleBooks.ThessaloniansSecondBook,
            '2TH': BibleBooks.ThessaloniansSecondBook,
            '1 TIM': BibleBooks.TimothyFirstBook,
            '1TI': BibleBooks.TimothyFirstBook,
            '2 TIM': BibleBooks.TimothySecondBook,
            '2TI': BibleBooks.TimothySecondBook,
            'TIT': BibleBooks.Titus,
            'FILEM': BibleBooks.Philemon,
            'PHM': BibleBooks.Philemon,
            'HEB': BibleBooks.Hebrews,
            'HEBR': BibleBooks.Hebrews,
            'JAC': BibleBooks.James,
            'JAK': BibleBooks.James,
            '1 PET': BibleBooks.PeterFirstBook,
            '1PE': BibleBooks.PeterFirstBook,
            '1 PETR': BibleBooks.PeterFirstBook,
            '2 PET': BibleBooks.PeterSecondBook,
            '2PE': BibleBooks.PeterSecondBook,
            '2 PETR': BibleBooks.PeterSecondBook,
            '1 JOH': BibleBooks.JohnFirstBook,
            '1JN': BibleBooks.JohnFirstBook,
            '1 JON': BibleBooks.JohnFirstBook,
            '2 JOH': BibleBooks.JohnSecondBook,
            '2JN': BibleBooks.JohnSecondBook,
            '2 JON': BibleBooks.JohnSecondBook,
            '3 JOH': BibleBooks.JohnThirdBook,
            '3JN': BibleBooks.JohnThirdBook,
            '3 JON': BibleBooks.JohnThirdBook,
            'JUD': BibleBooks.Jude,
            'OP': BibleBooks.Revelation,
            'OPB': BibleBooks.Revelation,
            'OPENB': BibleBooks.Revelation,
            'REV': BibleBooks.Revelation,
        }

        return mapping[book_normalized]
