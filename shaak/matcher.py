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

# simple word matching algorithm
# in a seperate file to help with code organization

import string
from typing import Tuple, List, Iterator

word_markers = frozenset(string.punctuation + string.whitespace)
format_markers = frozenset('*_|~')

ProcessedTextType = Tuple[List[str], int]
def text_preprocess(text: str):
    return (list(text.lower()), len(text))

ProcessedPatternType = Tuple[List[str], int]
def pattern_preprocess(pattern: str):
    return (list(pattern.lower()), len(pattern))

def word_matches(processed_text: ProcessedTextType, processed_pattern: ProcessedPatternType):

    text, text_len = processed_text
    pattern, pattern_len = processed_pattern
    found = set()
    start = None
    index = 0
    along = 0

    while along < text_len:

        char = text[along]

        if char == pattern[index]:
            if start == None:
                start = along
            index += 1
            if index == pattern_len:
                if along < text_len and text[along+1] == 's':
                    along += 1
                if (start == 0 or text[start-1] in word_markers) and (along+1 == text_len or text[along+1] in word_markers):
                    found.add((start, along+1))
                index = 0
                start = None
        elif index != 0 and char != pattern[index] and char not in format_markers:
            index = 0
            start = None

        along += 1
    
    return found

def find_all_contains(text: str, sub: str) -> Iterator[Tuple[int, int]]:
    start = 0
    sub_l = len(sub)
    while True:
        start = text.find(sub, start)
        if start == -1: return
        yield (start, start + sub_l)
        start += len(sub)