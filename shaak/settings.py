'''
Shaak Discord moderation bot
Copyright (C) 2020 Squili

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

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
    owner_id:     int

@dataclasses.dataclass
class ProductSettings:
    
    bot_name:      str
    bot_version:   str
    bot_repo:      str
    author_name:   str
    author_page:   str
    author_donate: str

raw_settings = load_from_file('settings.json', ['token', 'database_url', 'status', 'owner_id'])
app_settings = AppSettings(**raw_settings)

raw_product = load_from_file('product.json', ['bot_name', 'bot_version', 'author_name', 'author_page', 'bot_repo', 'author_donate'])
product_settings = ProductSettings(**raw_product)
