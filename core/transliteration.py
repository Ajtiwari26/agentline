"""
Devanagari to English (Latin script) phonetic transliterator.
Ensures zero Devanagari characters (U+0900 to U+097F) appear in transcripts or database logs.
"""

import re

NUKTA_CONSONANTS = {
    'क\u093c': 'q', 'ख\u093c': 'kh', 'ग\u093c': 'gh', 'ज\u093c': 'z',
    'ड\u093c': 'r', 'ढ\u093c': 'rh', 'फ\u093c': 'f',
    '\u0958': 'q', '\u0959': 'kh', '\u095a': 'gh', '\u095b': 'z',
    '\u095c': 'r', '\u095d': 'rh', '\u095e': 'f',
}

VOWELS = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ri', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
    'अं': 'an', 'अः': 'ah', 'ऑ': 'o', 'ऍ': 'e'
}

MATRAS = {
    'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
    'ॉ': 'o', 'ॅ': 'e'
}

CONSONANTS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h'
}

NUMERALS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

DEVANAGARI_REGEX = re.compile(r'[\u0900-\u097F]')
WORD_BREAK_CHARS = set(r" \t\n\r.,!?;:-()'\"/\[]{}|`~@#$%^&*+=<>।॥")
LABIAL_CHARS = set("पफबभमpbmPBM")


def devanagari_to_english(text: str) -> str:
    """
    Transliterates any Devanagari characters in text into natural English / Latin script (Hinglish).
    Leaves English letters, numbers, punctuation, and email addresses intact.
    Guarantees no Devanagari codepoints remain in the output string.
    """
    if not text:
        return ""
    if not DEVANAGARI_REGEX.search(text):
        return text

    res = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''

        # Handle composite nukta (e.g. क + nukta)
        if i + 1 < n and text[i:i + 2] in NUKTA_CONSONANTS:
            base = NUKTA_CONSONANTS[text[i:i + 2]]
            i += 1
            nxt = text[i + 1] if i + 1 < n else ''
            if nxt == '्':
                res.append(base)
                i += 1
            elif nxt in MATRAS:
                res.append(base + MATRAS[nxt])
                i += 1
            elif nxt in ('ं', 'ँ'):
                nxt2 = text[i + 2] if i + 2 < n else ''
                nasal = 'am' if nxt2 in LABIAL_CHARS else 'an'
                res.append(base + nasal)
                i += 1
            else:
                is_word_end = (not nxt) or (nxt in WORD_BREAK_CHARS)
                res.append(base if is_word_end else base + 'a')

        elif c in NUKTA_CONSONANTS:
            base = NUKTA_CONSONANTS[c]
            if nxt == '्':
                res.append(base)
                i += 1
            elif nxt in MATRAS:
                res.append(base + MATRAS[nxt])
                i += 1
            elif nxt in ('ं', 'ँ'):
                nxt2 = text[i + 2] if i + 2 < n else ''
                nasal = 'am' if nxt2 in LABIAL_CHARS else 'an'
                res.append(base + nasal)
                i += 1
            else:
                is_word_end = (not nxt) or (nxt in WORD_BREAK_CHARS)
                res.append(base if is_word_end else base + 'a')

        elif c in NUMERALS:
            res.append(NUMERALS[c])

        elif c in VOWELS:
            res.append(VOWELS[c])

        elif c in CONSONANTS:
            base = CONSONANTS[c]
            if nxt == '्':
                res.append(base)
                i += 1
            elif nxt in MATRAS:
                res.append(base + MATRAS[nxt])
                i += 1
            elif nxt in ('ं', 'ँ'):
                nxt2 = text[i + 2] if i + 2 < n else ''
                nasal = 'am' if nxt2 in LABIAL_CHARS else 'an'
                res.append(base + nasal)
                i += 1
            else:
                is_word_end = (not nxt) or (nxt in WORD_BREAK_CHARS)
                res.append(base if is_word_end else base + 'a')

        elif c in MATRAS:
            res.append(MATRAS[c])

        elif c in ('ं', 'ँ'):
            res.append('n')

        elif c == 'ः':
            res.append('h')

        elif c in ('।', '॥'):
            res.append('.')

        elif c == '्':
            pass

        elif '\u0900' <= c <= '\u097F':
            # Drop any unhandled Devanagari accents/combining marks
            pass

        else:
            res.append(c)

        i += 1

    out = ''.join(res)
    # Strip any trailing or consecutive Devanagari remnants if any exist
    out = DEVANAGARI_REGEX.sub('', out)
    return out
