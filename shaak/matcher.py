# simple word matching algorithm
# in a seperate file to help with code organization

import string
from typing import Tuple, List

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
                if (start == 0 or text[start-1] in word_markers) and (along+1 == text_len or text[along+1] in word_markers):
                    found.add((start, along+1))
                index = 0
                start = None
        elif index != 0 and char != pattern[index] and char not in format_markers:
            index = 0
            start = None

        along += 1
    
    return found