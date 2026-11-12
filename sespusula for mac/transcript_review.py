"""Build readable, bounded transcript lines without changing word timestamps."""
import re

from silence_core import US


def transcript_sentences(words: list[dict]) -> list[dict]:
    result=[];current=[]

    def finish():
        if current:
            result.append({'start':min(w['start'] for w in current),
                           'end':max(w['end'] for w in current),
                           'words':list(current)})
            current.clear()

    for word in sorted(words,key=lambda w:(w['start'],w['end'])):
        if not word['word'].strip():continue
        if current and (word['start']-current[-1]['end']>US or
                        word['end']-current[0]['start']>12*US or len(current)>=24):
            finish()
        current.append(word)
        if re.search(r'[.!?…]["\u201d\u2019]?\s*$',word['word']):finish()
    finish()
    return result
