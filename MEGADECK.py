import sys
import os
import csv
import json
import hashlib
import genanki
import re
import random
from collections import Counter

# ==========================================
# CONFIGURATION
# ==========================================
show_name = "Anime Mega Deck"
CSV_FOLDER = "react-anime/public/csv"
MEDIA_ROOT = "react-anime/public/anki/media"
OUTPUT_PATH = "react-anime/public/anki"

# Your Master Fixes
MISTRANSLATION_FIXES = {
    'ッ': {'reading': 'ッ', 'meaning': '(Emphasis marker / Glottal stop)'},
    'メ': {'reading': 'め', 'meaning': 'Part of "Dame" (No) or part of a word'},
    'リ': {'reading': 'り', 'meaning': '(Stuttering sound / Part of a name)'},
    '・': {'reading': '・', 'meaning': '(Punctuation / Name separator)'},
    'ねえ': {'reading': 'ねえ', 'meaning': 'Hey / Look / (Seeking agreement) / No (Slang "nai")'},
    '奴': {'reading': 'やつ', 'meaning': 'Guy / Person / That thing / Fellow'},
    'てる': {'reading': 'てる', 'meaning': 'is... -ing (Contraction of te-iru)'},
    'いえ': {'reading': 'いえ', 'meaning': 'No / Not at all (Polite interjection)'},
    '前': {'reading': 'まえ', 'meaning': 'Before / Front / Previous'},
    '僕': {'reading': 'ぼく', 'meaning': 'I / Me (Male pronoun)'},
    '様': {'reading': 'さま', 'meaning': 'Sama (Honorific suffix)'},
    '人': {'reading': 'ひと', 'meaning': 'Person / People'},
    '分': {'reading': 'ぶん', 'meaning': 'Part / Portion / Share / Amount'},
    '決闘': {'reading': 'けっとう', 'meaning': 'Duel (Card Games)'},
    '召喚': {'reading': 'しょうかん', 'meaning': 'Summon / Summoning'},
    '術': {'reading': 'じゅつ', 'meaning': 'Jutsu / Ninja Technique'},
    '喪女': {'reading': 'もじょ', 'meaning': 'Mojo (Unpopular woman slang)'},
    'おっふ': {'reading': 'おっふ', 'meaning': 'Offu! (Awestruck sound)'},
    '部長': {'reading': 'ぶちょう', 'meaning': 'Club President (School Context)'},
}


def generate_id(name, salt=0):
    hash_obj = hashlib.sha256((name + str(salt)).encode())
    return int(hash_obj.hexdigest(), 16) % 10 ** 10


MODEL_ID_VOCAB = generate_id(show_name, salt=1)

# ==========================================
# ANKI TEMPLATES & CSS
# ==========================================
style_vocab = """
/* BASE STYLES */
.card { font-family: "Noto Sans JP", sans-serif; text-align: center; background-color: #fdfdfd; padding: 40px 20px; color: #333; }

/* Furigana Hover Logic */
.expression { 
    font-size: 60px; 
    cursor: help; 
    position: relative; 
    display: inline-block; 
    font-weight: bold;
    margin-top: 20px;
}

.reading-hover { 
    visibility: hidden; 
    font-size: 24px; 
    color: #3498db; 
    position: absolute; 
    width: 100%; 
    top: -40px; 
    left: 0; 
    font-weight: normal;
}

.expression:hover .reading-hover { visibility: visible; }

.level { display: inline-block; padding: 2px 12px; border-radius: 5px; background: #3498db; color: white; font-size: 14px; margin-top: 10px; }
.meaning { text-align: left; margin-top: 30px; font-size: 20px; border-top: 2px solid #eee; padding-top: 15px; line-height: 1.5; }
.sentence { margin-top: 20px; background: #f9f9f9; padding: 15px; border-radius: 10px; font-size: 26px; border-left: 5px solid #3498db; text-align: left; color: #2c3e50; }
.source-tag { font-size: 14px; color: #95a5a6; margin-top: 5px; text-align: right; font-style: italic; }
.translation { font-size: 18px; color: #666; margin-top: 10px; font-style: italic; text-align: left; }

.screenshot { margin-top: 20px; }
.screenshot img { max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.audio-btn { margin-top: 10px; }
.footer { font-size: 12px; color: #bdc3c7; margin-top: 30px; border-top: 1px dashed #ddd; padding-top: 10px; }

/* DARK MODE OVERRIDES */
.nightMode.card { background-color: #2c2c2c; color: #fdfdfd; }
.nightMode .meaning { border-top: 2px solid #444; }
.nightMode .sentence { background: #383838; color: #ecf0f1; border-left: 5px solid #5dade2; }
.nightMode .translation { color: #bdc3c7; }
.nightMode .source-tag { color: #7f8c8d; }
.nightMode .reading-hover { color: #5dade2; }
.nightMode .footer { border-top: 1px dashed #555; color: #7f8c8d; }
.nightMode .screenshot img { box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
"""

fields = [
    {'name': 'Expression'}, {'name': 'Reading'}, {'name': 'Meaning'},
    {'name': 'Level'}, {'name': 'Frequency'}, {'name': 'Sentence'},
    {'name': 'Translation'}, {'name': 'Shows'}, {'name': 'Image'},
    {'name': 'WordAudio'}, {'name': 'SentenceAudio'}, {'name': 'SourceShow'}
]

vocab_model = genanki.Model(
    MODEL_ID_VOCAB, 'Anime Mega Vocab v4 (Audio + Source)', fields=fields,
    templates=[{
        'name': 'Vocab Card',
        'qfmt': '''
            <div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div>
            <div class="audio-btn">{{WordAudio}}</div>
            <br><div class="level">{{Level}}</div>
        ''',
        'afmt': '''{{FrontSide}}<hr id="answer">
                <div class="meaning">{{Meaning}}</div>

                <div class="sentence">
                    {{Sentence}}
                    <div class="audio-btn">{{SentenceAudio}}</div>
                    <div class="source-tag">Source: {{SourceShow}}</div>
                </div>

                <div class="translation">{{Translation}}</div>
                <div class="screenshot">{{Image}}</div>
                <div class="footer">Appears in: {{Shows}} | Total Count: {{Frequency}}x</div>'''
    }], css=style_vocab
)

# ==========================================
# DATA PROCESSING
# ==========================================
word_entries = {}
total_counts = Counter()
word_shows = {}
media_files = []
media_path_map = {}

print("Mapping media files (Images & Audio)...")
allowed_exts = ('.jpg', '.jpeg', '.png', '.webp', '.mp3')
for root, dirs, files in os.walk(MEDIA_ROOT):
    for f in files:
        if f.lower().endswith(allowed_exts):
            media_path_map[f] = os.path.join(root, f)

print("Scanning CSVs...")
for filename in os.listdir(CSV_FOLDER):
    if filename.endswith("_Vocabulary_Full.csv"):
        show = filename.replace("_Vocabulary_Full.csv", "")
        with open(os.path.join(CSV_FOLDER, filename), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                expr = row['Expression']
                freq = int(row.get('Frequency', 1))
                total_counts[expr] += freq
                if expr not in word_shows: word_shows[expr] = set()
                word_shows[expr].add(show)
                row['_source_show_name'] = show
                if expr not in word_entries:
                    word_entries[expr] = []
                word_entries[expr].append(row)

# ==========================================
# DECK SETUP (MEGA + SUBDECKS)
# ==========================================
mega_deck = genanki.Deck(generate_id(show_name, salt=2), show_name)

# Dictionary to hold our specific level decks
level_decks = {
    'N5': genanki.Deck(generate_id("N5_Deck"), "Anime Vocabulary::N5"),
    'N4': genanki.Deck(generate_id("N4_Deck"), "Anime Vocabulary::N4"),
    'N3': genanki.Deck(generate_id("N3_Deck"), "Anime Vocabulary::N3"),
    'N2': genanki.Deck(generate_id("N2_Deck"), "Anime Vocabulary::N2"),
    'N1': genanki.Deck(generate_id("N1_Deck"), "Anime Vocabulary::N1"),
    'Unlabeled': genanki.Deck(generate_id("Unlabeled_Deck"), "Anime Vocabulary::Unlabeled")
}

print(f"Building decks with {len(total_counts)} unique words...")
for word, count in total_counts.most_common():
    all_possible_rows = word_entries[word]

    # Selection Logic
    perfect_rows = [r for r in all_possible_rows if
                    (r.get('Image') and '<img' in r['Image']) and (r.get('WordAudio') and '[sound:' in r['WordAudio'])]
    image_rows = [r for r in all_possible_rows if r.get('Image') and '<img' in r['Image']]
    audio_rows = [r for r in all_possible_rows if r.get('WordAudio') and '[sound:' in r['WordAudio']]

    if perfect_rows:
        chosen_row = random.choice(perfect_rows)
    elif image_rows:
        chosen_row = random.choice(image_rows)
    elif audio_rows:
        chosen_row = random.choice(audio_rows)
    else:
        chosen_row = random.choice(all_possible_rows)

    reading = chosen_row['Reading']
    meaning = chosen_row['Meaning']
    if word in MISTRANSLATION_FIXES:
        reading = MISTRANSLATION_FIXES[word]['reading']
        meaning = MISTRANSLATION_FIXES[word]['meaning']


    def extract_media(tag):
        if not tag: return ""
        img_match = re.search(r'src="([^"]+)"', tag)
        if img_match:
            fname = img_match.group(1)
            if fname in media_path_map:
                media_files.append(media_path_map[fname])
                return tag
        aud_match = re.search(r'\[sound:([^\]]+)\]', tag)
        if aud_match:
            fname = aud_match.group(1)
            if fname in media_path_map:
                media_files.append(media_path_map[fname])
                return tag
        return ""


    final_img_tag = extract_media(chosen_row.get('Image', ''))
    final_word_audio = extract_media(chosen_row.get('WordAudio', ''))
    final_sent_audio = extract_media(chosen_row.get('SentenceAudio', ''))
    source_show = chosen_row.get('_source_show_name', 'Unknown')

    # Determine the level for sorting
    raw_level = chosen_row.get('Level', 'Unlabeled')
    # Normalize level strings (e.g. "JLPT N5" -> "N5")
    clean_level = "Unlabeled"
    for lvl in ['N5', 'N4', 'N3', 'N2', 'N1']:
        if lvl in raw_level.upper():
            clean_level = lvl
            break

    fields_data = [
        word, reading, meaning, raw_level, str(count),
        chosen_row['Sentence'], chosen_row['Translation'],
        ", ".join(sorted(list(word_shows[word]))),
        final_img_tag, final_word_audio, final_sent_audio, source_show
    ]

    # Create the note
    note = genanki.Note(model=vocab_model, fields=fields_data)

    # Add to the Mega Deck
    mega_deck.add_note(note)

    # Add to the specific Level Deck
    if clean_level in level_decks:
        level_decks[clean_level].add_note(note)
    else:
        level_decks['Unlabeled'].add_note(note)

# ==========================================
# EXPORT
# ==========================================
os.makedirs(OUTPUT_PATH, exist_ok=True)
out_file = os.path.join(OUTPUT_PATH, 'Anime_Multi_Deck_Package.apkg')

# Package all decks together into one file
all_decks = [mega_deck] + list(level_decks.values())
package = genanki.Package(all_decks)
package.media_files = list(set(media_files))

package.write_to_file(out_file)
print(f"Export complete: {out_file}")
print(f"Notes added to Megadeck and Level-specific subdecks.")
print(f"Total media files packaged: {len(package.media_files)}")