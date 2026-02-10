import sys
import os
import csv
import json
import hashlib
import genanki
from collections import Counter

# --- SETUP ---
show_name = "Anime Mega Deck"


def generate_id(name, salt=0):
    hash_obj = hashlib.sha256((name + str(salt)).encode())
    return int(hash_obj.hexdigest(), 16) % 10 ** 10


MODEL_ID_VOCAB = generate_id(show_name, salt=1)
DECK_ID_VOCAB = generate_id(show_name, salt=2)

# --- ANKI TEMPLATES ---
hover_css = """
.expression { font-size: 50px; cursor: pointer; position: relative; display: inline-block; font-weight: bold; }
.expression .reading-hover { visibility: hidden; font-size: 20px; color: #7f8c8d; position: absolute; width: 100%; top: -25px; left: 0; }
.expression:hover .reading-hover { visibility: visible; }
"""
style_vocab = """
.card { font-family: "Noto Sans JP", sans-serif; text-align: center; background-color: #fdfdfd; padding: 20px; }
.level { display: inline-block; padding: 2px 10px; border-radius: 5px; background: #3498db; color: white; font-size: 16px; margin-top: 10px; }
.meaning { text-align: left; margin-top: 20px; font-size: 18px; border-top: 1px solid #ccc; padding-top: 10px; }
.sentence { margin-top: 20px; font-style: italic; background: #eee; padding: 10px; border-radius: 5px; font-size: 22px; }
.translation { font-size: 16px; color: #7f8c8d; margin-top: 5px; }
.footer { font-size: 12px; color: #bdc3c7; margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 5px; }
""" + hover_css

fields = [
    {'name': 'Expression'}, {'name': 'Reading'}, {'name': 'Meaning'},
    {'name': 'Level'}, {'name': 'Frequency'}, {'name': 'Sentence'},
    {'name': 'Translation'}, {'name': 'Shows'}
]

vocab_model = genanki.Model(
    MODEL_ID_VOCAB, 'Japanese Mega Vocab v1', fields=fields,
    templates=[{
        'name': 'Vocab Card',
        'qfmt': '<div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div><br><div class="level">{{Level}}</div>',
        'afmt': '{{FrontSide}}<hr id="answer"><div class="meaning">{{Meaning}}</div><div class="sentence">{{Sentence}}</div><div class="translation">{{Translation}}</div><div class="footer">Found in: {{Shows}} | Total Count: {{Frequency}}x</div>'
    }],
    css=style_vocab
)

mega_deck = genanki.Deck(DECK_ID_VOCAB, show_name)

# --- DATA AGGREGATION ---
word_data = {}  # Key: Expression, Value: All fields
total_counts = Counter()
word_shows = {}  # Key: Expression, Value: Set of show names

print("Scanning CSV folder for data...")
csv_folder = "csv"
for filename in os.listdir(csv_folder):
    if filename.endswith("_Vocabulary_Full.csv"):
        current_show = filename.replace("_Vocabulary_Full.csv", "")
        print(f"  > Processing: {current_show}")

        with open(os.path.join(csv_folder, filename), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                expr = row['Expression']
                freq = int(row['Frequency'])

                total_counts[expr] += freq

                if expr not in word_shows:
                    word_shows[expr] = set()
                word_shows[expr].add(current_show)

                # Keep the best example sentence (highest frequency from the original show)
                if expr not in word_data or freq > int(word_data[expr]['Frequency']):
                    word_data[expr] = row

# --- NOTE GENERATION ---
print(f"Generating Mega Deck with {len(total_counts)} unique words...")

# Sort by total frequency across all shows
for word, count in total_counts.most_common():
    # Filter out single-use words across the entire library if desired (Optional)
    # if count < 2: continue

    orig = word_data[word]
    show_list = ", ".join(sorted(list(word_shows[word])))

    fields_data = [
        word,
        orig['Reading'],
        orig['Meaning'],
        orig['Level'],
        str(count),
        orig['Sentence'],
        orig['Translation'],
        show_list
    ]

    note = genanki.Note(model=vocab_model, fields=fields_data)
    mega_deck.add_note(note)

# --- EXPORT ---
output_file = 'react-anime/public/anki/Anime_Mega_Deck.apkg'
if not os.path.exists('react-anime/public/anki'): os.makedirs('react-anime/public/anki')

print(f"Saving to {output_file}...")
genanki.Package(mega_deck).write_to_file(output_file)

print("Done! One Mega Deck to rule them all created.")