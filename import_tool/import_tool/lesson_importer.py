import pandas

from import_tool.bible_reference import BibleReference
from import_tool.lesson import Lesson


def first(data_frame, column):
    cleaned_column = data_frame[column].dropna()

    if not cleaned_column.any():
        return ''

    return cleaned_column.iloc[0]


class LessonImporter(object):
    def load(self, file_path='../../../jesus_commandments_website/data/biblereferences/lessons.csv'):
        df = pandas.read_csv(file_path, delimiter=';', na_filter= False)

        lessons = []

        # Handle each lesson
        for name, group in df.groupby(['lesson']):
            lesson = Lesson()
            lesson.id = first(group, 'lesson')
            lesson.title = first(group, 'title_en')
            lesson.bible_section = first(group, 'bible_section')
            lesson.category = first(group, 'category')

            # Parse bible refs
            for index, row in group.iterrows():
                if len(row['bible_ref']) == 0:
                    continue
                try:
                    reference = BibleReference.create_from_string(row['bible_ref'])

                    if row['bible_ref_type'].lower() == 'primary':
                        lesson.primary_lesson_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'direct':
                        lesson.direct_lesson_bible_references.append(reference)
                except Exception as ex:
                    print(f'Could not parse {row} due to exception {ex}')

            # Parse questions
            lesson.lessonquestions += [q for q in group['questions'] if q != '']

            lessons.append(lesson)

        return lessons
