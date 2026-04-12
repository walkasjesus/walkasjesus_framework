from enum import Enum

from django.utils.translation import gettext_lazy


class LessonCategories(Enum):
    oldtestament = gettext_lazy('Old Testament')
    newtestament = gettext_lazy('New Testament')
