from bible_lib import Bible, Bibles


class BibleFactory:
    def create(self, bible_id: str) -> Bible:
        all_bibles = Bibles().dictionary()

        if bible_id in all_bibles:
            return all_bibles[bible_id]

        raise KeyError(f'Bible {bible_id} not found')
