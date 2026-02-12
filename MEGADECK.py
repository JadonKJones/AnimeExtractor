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
DECK_ID_VOCAB = generate_id(show_name, salt=2)

# ==========================================
# ANKI TEMPLATES & CSS
# ==========================================
style_vocab = """
.card { font-family: "Noto Sans JP", sans-serif; text-align: center; background-color: #fdfdfd; padding: 40px 20px; }

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
.sentence { margin-top: 20px; background: #f9f9f9; padding: 15px; border-radius: 10px; font-size: 26px; border-left: 5px solid #3498db; text-align: left; }
.source-tag { font-size: 14px; color: #95a5a6; margin-top: 5px; text-align: right; font-style: italic; }
.translation { font-size: 18px; color: #666; margin-top: 10px; font-style: italic; text-align: left; }

.screenshot { margin-top: 20px; }
.screenshot img { max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.audio-btn { margin-top: 10px; }

.footer { font-size: 12px; color: #bdc3c7; margin-top: 30px; border-top: 1px dashed #ddd; padding-top: 10px; }
"""

# Updated Fields
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
word_entries = {}  # Key: Expression, Value: List of ALL rows found
total_counts = Counter()
word_shows = {}
media_files = []
media_path_map = {}  # Maps filename (e.g., 'img.jpg') to full path

print("Mapping media files (Images & Audio)...")
# We now scan for MP3s as well
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

                # IMPORTANT: Inject the specific show name into the row data
                # This allows us to say "Source: Naruto" later
                row['_source_show_name'] = show

                if expr not in word_entries:
                    word_entries[expr] = []
                word_entries[expr].append(row)

# ==========================================
# DECK GENERATION
# ==========================================
mega_deck = genanki.Deck(DECK_ID_VOCAB, show_name)

print(f"Building deck with {len(total_counts)} unique words...")
for word, count in total_counts.most_common():
    all_possible_rows = word_entries[word]

    # SELECTION LOGIC: Find the "Perfect" Card
    # Priority 1: Has Image AND Audio
    # Priority 2: Has Image
    # Priority 3: Has Audio
    # Priority 4: Random

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

    # Reading and Meaning (Use chosen_row but allow manual overrides)
    reading = chosen_row['Reading']
    meaning = chosen_row['Meaning']
    if word in MISTRANSLATION_FIXES:
        reading = MISTRANSLATION_FIXES[word]['reading']
        meaning = MISTRANSLATION_FIXES[word]['meaning']


    # --- HELPER: Extract Media Function ---
    def extract_media(tag):
        """Finds [sound:...] or src="..." and adds to package list"""
        if not tag: return ""
        # Check for Image src
        img_match = re.search(r'src="([^"]+)"', tag)
        if img_match:
            fname = img_match.group(1)
            if fname in media_path_map:
                media_files.append(media_path_map[fname])
                return tag  # Return original tag if valid

        # Check for Audio sound tag
        aud_match = re.search(r'\[sound:([^\]]+)\]', tag)
        if aud_match:
            fname = aud_match.group(1)
            if fname in media_path_map:
                media_files.append(media_path_map[fname])
                return tag
        return ""


    # Process Media Fields
    final_img_tag = extract_media(chosen_row.get('Image', ''))
    final_word_audio = extract_media(chosen_row.get('WordAudio', ''))
    final_sent_audio = extract_media(chosen_row.get('SentenceAudio', ''))

    # Get the specific show for this sentence
    source_show = chosen_row.get('_source_show_name', 'Unknown')

    # Assembly
    fields_data = [
        word,
        reading,
        meaning,
        chosen_row.get('Level', 'Unlabeled'),
        str(count),
        chosen_row['Sentence'],
        chosen_row['Translation'],
        ", ".join(sorted(list(word_shows[word]))),  # List of ALL shows
        final_img_tag,
        final_word_audio,
        final_sent_audio,
        source_show  # The specific show for this sentence
    ]
    mega_deck.add_note(genanki.Note(model=vocab_model, fields=fields_data))

# Export
os.makedirs(OUTPUT_PATH, exist_ok=True)
out_file = os.path.join(OUTPUT_PATH, 'Anime_Mega_Deck.apkg')
package = genanki.Package(mega_deck)
package.media_files = list(set(media_files))
package.write_to_file(out_file)
print(f"Export complete: {out_file}")
print(f"Total media files packaged: {len(package.media_files)}")