import dataclasses, json
from pathlib import Path

@dataclasses.dataclass
class AppSettings:
    
    token: str
    database_url: str

settings_path = Path('./settings.json')
try:
    with settings_path.open() as f:
        raw_settings = json.load(f)
except FileNotFoundError:
    print('settings.json not found')
    exit(1)
except json.JSONDecodeError as e:
    print(f'error decoding settings.json: {e.msg} in {settings_path.absolute()}:{e.lineno}:{e.colno}')
    exit(1)

for item in ['token', 'database_url']:
    if item not in raw_settings:
        print(f'{item} field missing from {settings_path.absolute()}')
        exit(1)

app_settings = AppSettings(
    token=raw_settings['token'],
    database_url=raw_settings['database_url']
)
