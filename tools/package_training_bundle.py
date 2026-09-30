"""Build the local regional training ZIP without modifying source CSVs or manifests."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from prepare_monthly_training import INPUTS

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research_data/five_province_history'
FOLDER = BASE / 'training'


def main():
    target = FOLDER / 'training_bundle.zip'
    if target.exists():
        with ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError('Existing ZIP is damaged; preserve it and rename it before rebuilding.')
        print('Existing training ZIP preserved.')
        return
    sources = [(BASE / name, 'sources/' + name) for name in INPUTS]
    sources.extend((path, path.name) for path in sorted(FOLDER.iterdir())
                   if path.is_file() and path.suffix.lower() in {'.csv', '.json', '.md'})
    sources.append((ROOT / 'PUBLIC_SHARE_NOTES_TH.md', 'PUBLIC_SHARE_NOTES_TH.md'))
    for path, _ in sources:
        if not path.is_file():
            raise FileNotFoundError(path)
    with ZipFile(target, 'x', ZIP_DEFLATED) as archive:
        for path, name in sources:
            archive.write(path, name)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
    print(f'Created regional-only local ZIP with {len(sources)} files. See data-rights notes before sharing.')


if __name__ == '__main__':
    main()
