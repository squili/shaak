import dataclasses
import json
from pathlib import Path
from typing import List

def load_from_file(file_name: str, required_fields: List[str]):

    file_path = Path(file_name)
    try:
        with file_path.open() as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print('settings.json not found')
        exit(1)
    except json.JSONDecodeError as e:
        print(f'error decoding settings.json: {e.msg} in {file_path.absolute()}:{e.lineno}:{e.colno}')
        exit(1)

    for item in required_fields:
        if item not in raw_data:
            print(f'{item} field missing from {file_path.absolute()}')
            exit(1)
    
    return raw_data

@dataclasses.dataclass
class AppSettings:
    
    token:        str
    database_url: str
    status:       str
    redis_host:   str
    redis_port:   int
    redis_db:     int

@dataclasses.dataclass
class ProductSettings:
    
    bot_name:      str
    bot_version:   str
    bot_repo:      str
    author_name:   str
    author_page:   str
    author_donate: str

raw_settings = load_from_file('settings.json', ['token', 'database_url', 'status', 'redis_host', 'redis_port', 'redis_db'])
app_settings = AppSettings(
    token        = raw_settings['token'],
    database_url = raw_settings['database_url'],
    status       = raw_settings['status'],
    redis_host   = raw_settings['redis_host'],
    redis_port   = raw_settings['redis_port'],
    redis_db     = raw_settings['redis_db']
)

raw_product = load_from_file('product.json', ['bot_name', 'bot_version', 'author_name', 'author_page', 'bot_repo', 'author_donate'])
product_settings = ProductSettings(
    bot_name      = raw_product['bot_name'],
    bot_version   = raw_product['bot_version'],
    bot_repo      = raw_product['bot_repo'],
    author_name   = raw_product['author_name'],
    author_page   = raw_product['author_page'],
    author_donate = raw_product['author_donate']
)
