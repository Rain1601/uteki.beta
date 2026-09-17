"""Load one approved local key, never execute dotenv contents or log its value."""
import os
from pathlib import Path
import re
import stat


def load_aihubmix_key(root):
    if os.environ.get('AIHUBMIX_API_KEY'):
        return 'environment'
    path = Path(root) / '.env'
    if not path.exists():
        raise ValueError('Set AIHUBMIX_API_KEY in environment or local .env')
    if path.is_symlink() or path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError('Local .env must be a private regular file (mode 600)')
    found = []
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name.strip() == 'AIHUBMIX_API_KEY':
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
                value = value[1:-1]
            found.append(value)
    if len(found) != 1 or not re.fullmatch(r'[A-Za-z0-9_.-]+', found[0]):
        raise ValueError('Local .env needs exactly one nonempty AIHUBMIX_API_KEY')
    os.environ['AIHUBMIX_API_KEY'] = found[0]
    return 'local_env_file'
