import re

from bible_lib.bible_books import BibleBooks


class BibleReference:
    def __init__(self):
        self.book = BibleBooks.Genesis
        self.start_chapter = 0
        self.start_verse = 0
        self.end_chapter = 0
        self.end_verse = 0

    @staticmethod
    def create_from_string(verse_string : str):
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
            'LEV': BibleBooks.Leviticus,
            'NUM': BibleBooks.Numbers,
            'DEUT': BibleBooks.Deuteronomy,
            'JOZ': BibleBooks.Joshua,
            'RI': BibleBooks.Judges,
            'RICHT': BibleBooks.Judges,
            'RUTH': BibleBooks.Ruth,
            '1 SAM': BibleBooks.SamuelFirstBook,
            '2 SAM': BibleBooks.SamuelSecondBook,
            '1 KON': BibleBooks.KingsFirstBook,
            '2 KON': BibleBooks.KingsSecondBook,
            '1 KR': BibleBooks.ChroniclesFirstBook,
            '1 KRO': BibleBooks.ChroniclesFirstBook,
            '1 KRON': BibleBooks.ChroniclesFirstBook,
            '2 KR': BibleBooks.ChroniclesSecondBook,
            '2 KRO': BibleBooks.ChroniclesSecondBook,
            '2 KRON': BibleBooks.ChroniclesSecondBook,
            'EZRA': BibleBooks.Ezra,
            'NEH': BibleBooks.Nehemiah,
            'EST': BibleBooks.Esther,
            'JOB': BibleBooks.Job,
            'PS': BibleBooks.Psalms,
            'SPR': BibleBooks.Proverbs,
            'PR': BibleBooks.Ecclesiastes,
            'PRED': BibleBooks.Ecclesiastes,
            'HOOGL': BibleBooks.SongOfSolomon,
            'JES': BibleBooks.Isaiah,
            'JER': BibleBooks.Jeremiah,
            'KLAAGL': BibleBooks.Lamentations,
            'EZE': BibleBooks.Ezekiel,
            'EZECH': BibleBooks.Ezekiel,
            'DAN': BibleBooks.Daniel,
            'HOS': BibleBooks.Hosea,
            'JOEL': BibleBooks.Joel,
            'AM': BibleBooks.Amos,
            'OB': BibleBooks.Obadiah,
            'JONA': BibleBooks.Jonah,
            'MI': BibleBooks.Micah,
            'NAH': BibleBooks.Nahum,
            'HAB': BibleBooks.Habakkuk,
            'ZEF': BibleBooks.Zephaniah,
            'SEF': BibleBooks.Zephaniah,
            'HAG': BibleBooks.Haggai,
            'ZACH': BibleBooks.Zechariah,
            'MAL': BibleBooks.Malachi,
            'MAT': BibleBooks.Matthew,
            'MATT': BibleBooks.Matthew,
            'MAR': BibleBooks.Mark,
            'MARC': BibleBooks.Mark,
            'LUC': BibleBooks.Luke,
            'LUK': BibleBooks.Luke,
            'JOH': BibleBooks.John,
            'HAN': BibleBooks.Acts,
            'HAND': BibleBooks.Acts,
            'ROM': BibleBooks.Romans,
            '1 COR': BibleBooks.CorinthiansFirstBook,
            '1 KOR': BibleBooks.CorinthiansFirstBook,
            '2 COR': BibleBooks.CorinthiansSecondBook,
            '2 KOR': BibleBooks.CorinthiansSecondBook,
            'GAL': BibleBooks.Galatians,
            'EF': BibleBooks.Ephesians,
            'FIL': BibleBooks.Philippians,
            'COL': BibleBooks.Colossians,
            'KOL': BibleBooks.Colossians,
            '1 THES': BibleBooks.ThessaloniansFirstBook,
            '2 THES': BibleBooks.ThessaloniansSecondBook,
            '1 TIM': BibleBooks.TimothyFirstBook,
            '2 TIM': BibleBooks.TimothySecondBook,
            'TIT': BibleBooks.Titus,
            'FILEM': BibleBooks.Philemon,
            'HEB': BibleBooks.Hebrews,
            'HEBR': BibleBooks.Hebrews,
            'JAC': BibleBooks.James,
            'JAK': BibleBooks.James,
            '1 PET': BibleBooks.PeterFirstBook,
            '1 PETR': BibleBooks.PeterFirstBook,
            '2 PET': BibleBooks.PeterSecondBook,
            '2 PETR': BibleBooks.PeterSecondBook,
            '1 JOH': BibleBooks.JohnFirstBook,
            '1 JON': BibleBooks.JohnFirstBook,
            '2 JOH': BibleBooks.JohnSecondBook,
            '2 JON': BibleBooks.JohnSecondBook,
            '3 JOH': BibleBooks.JohnThirdBook,
            '3 JON': BibleBooks.JohnThirdBook,
            'JUD': BibleBooks.Jude,
            'OP': BibleBooks.Revelation,
            'OPB': BibleBooks.Revelation,
            'OPENB': BibleBooks.Revelation,
        }

        return mapping[book_normalized]

