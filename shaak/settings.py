'''
This file is part of Shaak.

Shaak is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Shaak is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Shaak.  If not, see <https://www.gnu.org/licenses/>.
'''

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing  import List

logger = logging.getLogger('shaak_settings')

def load_from_env(field_name: str):
    key = f'SHAAK_{field_name.upper()}'
    try:
        return os.environ[key]
    except IndexError:
        try:
            return os.environ[field_name.upper()]
        except IndexError:
            logging.fatal(f'{field_name} field missing and {key} var not present')
            exit(1)

def load_from_file(file_name: str, required_fields: List[str]):

    file_path = Path(file_name)
    raw_data = {}
    try:
        with file_path.open() as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        for field in required_fields:
            raw_data[field] = load_from_env(field)
    except json.JSONDecodeError:
        for field in required_fields:
            raw_data[field] = load_from_env(field)

    for item in required_fields:
        if item not in raw_data:
            raw_data[item] = load_from_env(item)
    
    return raw_data

@dataclasses.dataclass
class AppSettings:
    
    token:        str
    database_url: str
    status:       str
    owner_id:     int
    max_guilds:   bool

@dataclasses.dataclass
class ProductSettings:
    
    bot_name:      str
    bot_version:   str
    bot_repo:      str
    bot_docs:      str
    author_name:   str
    author_page:   str
    author_donate: str

raw_settings = load_from_file('settings.json', ['token', 'database_url', 'status', 'owner_id'])
app_settings = AppSettings(**raw_settings)

raw_product = load_from_file('product.json', ['bot_name', 'bot_version', 'bot_docs', 'author_name', 'author_page', 'bot_repo', 'author_donate'])
product_settings = ProductSettings(**raw_product)
