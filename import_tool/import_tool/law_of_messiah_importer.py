import yaml


class LawOfMessiahImporter:
    """Importer for Law of Messiah YAML files (OT + NT)."""

    def load(self, old_testament_file, new_testament_file):
        entries = []
        entries.extend(self._load_file(old_testament_file, source_dataset='ot'))
        entries.extend(self._load_file(new_testament_file, source_dataset='nt'))
        return entries

    def _load_file(self, file_path, source_dataset):
        with open(file_path, 'r', encoding='utf-8') as handle:
            data = yaml.safe_load(handle) or []

        entries = []
        for item in data:
            row = dict(item)
            row['source_dataset'] = source_dataset
            entries.append(row)
        return entries
