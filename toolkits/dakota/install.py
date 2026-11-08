#!/usr/bin/env python3
"""Install the repository's reviewed toolkit into local Codex and Copilot directories."""
import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home(), help='User home directory')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2] / '.github' / 'skills'
    skills = sorted(p for p in source.iterdir() if (p / 'SKILL.md').is_file())
    targets = [args.home / '.agents' / 'skills', args.home / '.copilot' / 'skills']
    conflicts = [root / skill.name for root in targets for skill in skills
                 if (root / skill.name).exists() or (root / skill.name).is_symlink()]
    if conflicts:
        parser.exit(1, 'Existing skills were preserved; installation stopped:\n'
                    + '\n'.join(str(p) for p in conflicts) + '\n')
    for root in targets:
        root.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            shutil.copytree(skill, root / skill.name)
        print(f'Installed {len(skills)} skills in {root}')
    print('Restart Codex and Copilot and check their skill lists.')


if __name__ == '__main__':
    main()
