"""Load one approved local key, never execute dotenv contents or log its value."""
import os
from pathlib import Path
import re
import stat


PROVIDER_KEYS = {'aihubmix': 'AIHUBMIX_API_KEY', 'deepseek': 'DEEPSEEK_API_KEY'}


def load_provider_key(root, provider):
    if provider not in PROVIDER_KEYS:
        raise ValueError('Unsupported credential provider')
    key_name = PROVIDER_KEYS[provider]
    if os.environ.get(key_name):
        return 'environment'
    path = Path(root) / '.env'
    if not path.exists():
        raise ValueError(f'Set {key_name} in environment or local .env')
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError('Local .env must be a private regular file (mode 600)')
    found = []
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name.removeprefix('export ').strip() == key_name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
                value = value[1:-1]
            found.append(value)
    if len(found) != 1 or not re.fullmatch(r'[A-Za-z0-9_.-]+', found[0]):
        raise ValueError(f'Local .env needs exactly one nonempty {key_name}')
    os.environ[key_name] = found[0]
    return 'local_env_file'


def load_aihubmix_key(root):
    return load_provider_key(root, 'aihubmix')
