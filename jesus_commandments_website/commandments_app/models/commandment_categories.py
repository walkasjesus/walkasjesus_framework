from enum import Enum

from django.utils.translation import gettext_lazy


class CommandmentCategories(Enum):
    firstcommandment = gettext_lazy('First Commandment')
    secondcommandment = gettext_lazy('Second Commandment')
    thirdcommandment = gettext_lazy('Third Commandment')
    fourthcommandment = gettext_lazy('Fourth Commandment')
    fifthcommandment = gettext_lazy('Fifth Commandment')
    sixthcommandment = gettext_lazy('Sixth Commandment')
    # seventhcommandment = gettext_lazy('Seventh Commandment')
    eighthcommandment = gettext_lazy('Eighth Commandment')
    ninthcommandment = gettext_lazy('Ninth Commandment')
    tenthcommandment = gettext_lazy('Tenth Commandment')