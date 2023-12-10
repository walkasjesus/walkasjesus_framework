import pandas

from import_tool.bible_reference import BibleReference
from import_tool.lesson import Lesson
from commandments_app.models import Commandment


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
            lesson.story = first(group, 'story_en')
            lesson.category = first(group, 'category')
            lesson.activities = first(group, 'activities')
            lesson.lesson_bible_section = []
            lesson.primary_lesson_bible_references = []
            lesson.direct_lesson_bible_references = []
            lesson.related_step_description = first(group, 'related_step_description_en')

            # Parse 'related_step' column
            related_step = first(group, 'related_step')
            if related_step:
                try:
                    # Look up the related commandment based on the 'related_step' value
                    related_commandment = Commandment.objects.get(id=int(related_step))
                    lesson.commandment = related_commandment  # Set the related commandment in the existing field
                    print(f"Related commandment {related_step} found for lesson {lesson.id}")
                except Commandment.DoesNotExist:
                    print(f"Related commandment with ID {related_step} not found for lesson {lesson.id}")

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
                    raise ex
                    print(f'Could not parse {row} due to exception {ex}')

            # Parse bible_section
            for index, row in group.iterrows():
                if len(row['bible_section']) == 0:
                    continue
                try:
                    reference = BibleReference.create_from_string(row['bible_section'])
                    lesson.lesson_bible_section.append(reference)

                except Exception as ex:
                    raise ex
                    print(f'Could not parse {row} due to exception {ex}')

            # Parse questions
            lesson.lessonquestions += [q for q in group['questions'] if q != '']

            lessons.append(lesson)

        return lessons
