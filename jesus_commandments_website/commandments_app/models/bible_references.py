from commandments_app.models import PrimaryBibleReference, SecondaryBibleReference, TertiaryBibleReference


class BibleReferences:
    def __init__(self):
        self.bible = None
        self._data = None

    def primary(self):
        return self._query_references(PrimaryBibleReference.objects.filter(commandment__gt=0))

    def secondary(self):
        return self._query_references(SecondaryBibleReference.objects.filter(commandment__gt=0))

    def tertiary(self):
        return self._query_references(TertiaryBibleReference.objects.filter(commandment__gt=0))

    def _query_references(self, query):
        # This will reduce the amount of sql queries as we already know we also want the commandments
        query = query.select_related()

        # Set the bible for each reference
        [ref.set_bible(self.bible) for ref in query]

        return query
