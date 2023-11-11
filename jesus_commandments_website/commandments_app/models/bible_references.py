from commandments_app.models import PrimaryBibleReference, DirectBibleReference, IndirectBibleReference, DuplicateBibleReference, ExampleBibleReference, StudyBibleReference, OTLawBibleReference, WisdomBibleReference


class BibleReferences:
    """
    This class allows for easy selection of lists of bible references,
    bible references are classified into different types.
    """
    def __init__(self):
        # The bible to use on the references that are returned
        self.bible = None

    def primary(self):
        return self._query_references(PrimaryBibleReference.objects.filter(commandment__gt=0))

    def direct(self):
        return self._query_references(DirectBibleReference.objects.filter(commandment__gt=0))

    def indirect(self):
        return self._query_references(IndirectBibleReference.objects.filter(commandment__gt=0))

    def duplicate(self):
        return self._query_references(DuplicateBibleReference.objects.filter(commandment__gt=0))

    def example(self):
        return self._query_references(ExampleBibleReference.objects.filter(commandment__gt=0))

    def study(self):
        return self._query_references(StudyBibleReference.objects.filter(commandment__gt=0))

    def otlaw(self):
        return self._query_references(OTLawBibleReference.objects.filter(commandment__gt=0))

    def wisdom(self):
        return self._query_references(WisdomBibleReference.objects.filter(commandment__gt=0))

    def _query_references(self, query):
        # This will reduce the amount of sql queries as we already know we also want the commandments
        query = query.select_related()

        # Set the bible for each reference
        [ref.set_bible(self.bible) for ref in query]

        return query
