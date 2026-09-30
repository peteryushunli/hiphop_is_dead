"""Shared lyric normalization; individual studies choose their exclusion policies."""
import re
import unicodedata

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)*")


def name_key(text):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', text).casefold())


def clean_lyrics(text):
    text = unicodedata.normalize('NFKC', text).replace('’', "'").replace('‘', "'")
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)
    text = re.sub(r'^.{0,500}?\bLyrics\s*(?=\[)', '', text, count=1, flags=re.S)
    text = re.sub(r'\[[^\]]*\]', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(?i)\d*\s*embed\s*$', '', text)
    lines = [line.strip().lower() for line in text.splitlines()]
    lines = [line for line in lines if line and not re.search(
        r'you might also like|see .+ live|get tickets|contributors?\b.*lyrics|^translations\b', line)]
    return lines


def tokens(text):
    # Fold accents without splitting loanwords such as “patrón” into two tokens.
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))
    return TOKEN.findall(text)
