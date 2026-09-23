"""Load one approved local key, never execute dotenv contents or log its value."""
import os
from pathlib import Path
import re
import stat


PROVIDER_KEYS = {'aihubmix': 'AIHUBMIX_API_KEY', 'deepseek': 'DEEPSEEK_API_KEY'}
PROVIDER_KEY_ALIASES = {'aihubmix': ('AIHUBMIX_API_KEY', 'AI_HUB_MIX_API_KEY'),
                        'deepseek': ('DEEPSEEK_API_KEY',)}


def load_provider_key(root, provider):
    if provider not in PROVIDER_KEYS:
        raise ValueError('Unsupported credential provider')
    key_name = PROVIDER_KEYS[provider]
    aliases = PROVIDER_KEY_ALIASES[provider]
    configured = [os.environ[name] for name in aliases if os.environ.get(name)]
    if configured:
        if len(set(configured)) != 1:
            raise ValueError('Conflicting credential aliases for ' + provider)
        os.environ[key_name] = configured[0]
        return 'environment'
    path = Path(root) / '.env'
    if not path.exists():
        raise ValueError(f'Set {key_name} in environment or local .env')
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError('Local .env must be a private regular file (mode 600)')
    found = {}
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().partition('=')
        name = name.removeprefix('export ').strip()
        if sep and name in aliases:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
                value = value[1:-1]
            if name in found:
                raise ValueError('Duplicate credential entry for ' + name)
            found[name] = value
    if not found or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', value) for value in found.values()):
        raise ValueError('Local .env needs a nonempty ' + ' or '.join(aliases))
    if len(set(found.values())) != 1:
        raise ValueError('Conflicting credential aliases for ' + provider)
    os.environ[key_name] = next(iter(found.values()))
    return 'local_env_file'


def load_aihubmix_key(root):
    return load_provider_key(root, 'aihubmix')
