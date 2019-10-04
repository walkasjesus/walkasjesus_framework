from enum import Enum

from django.utils.translation import gettext_lazy


class CommandmentCategories(Enum):
    Salvation = gettext_lazy('Salvation Commands')
    Discipleship = gettext_lazy('Discipleship Commands')
    Worship = gettext_lazy('Worship Commands')
    Blessings = gettext_lazy('Blessings')
    JudgmentSeat = gettext_lazy('Judgment Seat Commands')
    Relationship = gettext_lazy('Relationship Commands')
    Marriage = gettext_lazy('Marriage Commands')
    Persecution = gettext_lazy('Persecution Commands')
    Thinking = gettext_lazy('Thinking Commands')
    Prayer = gettext_lazy('Prayer Commands')
    FalseTeachers = gettext_lazy('False Teachers Commands')
    Witnessing = gettext_lazy('Witnessing Commands')
    Greatest = gettext_lazy('Greatest Commands')
    Finance = gettext_lazy('Finance Commands')
    Holiness = gettext_lazy('Holiness Commands')
