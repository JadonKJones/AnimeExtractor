import sys
import time
import json
import os
import csv
import re
import random
import hashlib
import requests
from collections import Counter
from janome.tokenizer import Tokenizer
from jamdict import Jamdict
from googletrans import Translator
import genanki

# Polyfill for Python 3.13
try:
    import cgi
except ImportError:
    import legacy_cgi as cgi

    sys.modules['cgi'] = cgi

# --- SETUP ---
jam = Jamdict()

translator = Translator()
show = "WataMote"

for show in os.listdir('Transcripts'):
    t = Tokenizer()
    # Deterministic IDs based on show name
    def generate_id(name, salt=0):
        hash_obj = hashlib.sha256((name + str(salt)).encode())
        return int(hash_obj.hexdigest(), 16) % 10 ** 10


    MODEL_ID_VOCAB = generate_id(show, salt=1)
    DECK_ID_VOCAB = generate_id(show, salt=2)
    MODEL_ID_SENTENCE = generate_id(show, salt=3)
    DECK_ID_SENTENCE = generate_id(show, salt=4)

    CACHE_FILE = f"cache/{show}_cache.json"


    def load_cache():
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf8') as f:
                return json.load(f)
        return {}


    def save_cache(cache_data):
        with open(CACHE_FILE, 'w', encoding='utf8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)


    # --- ROMAJI CONVERTER ---
    def kana_to_romaji(text):
        consonants = {
            'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
            'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
            'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
            'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
            'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
            'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
            'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
            'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
            'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n',
            'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
            'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
            'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
            'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
            'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
            'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
            'ー': '', '・': ' '
        }
        res = ""
        i = 0
        while i < len(text):
            char = text[i]
            if char == 'ッ' and i + 1 < len(text):
                next_romaji = consonants.get(text[i + 1], '')
                if next_romaji:
                    res += next_romaji[0]
                    i += 1
                    continue
            if i + 1 < len(text) and text[i + 1] in ['ャ', 'ュ', 'ョ']:
                base = consonants.get(char, '')[:-1]
                small = {'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo'}
                res += base + small.get(text[i + 1], '')
                i += 2
                continue
            res += consonants.get(char, char)
            i += 1
        return res.capitalize()


    # --- UTILS ---
    def is_garbage_token(base_word):
        if re.match(r'^[a-zA-Z0-9]+$', base_word): return True
        if re.match(r'^[。、？！!?.…\s　～〜\-―♪★「」『』]+$', base_word): return True
        if len(base_word) == 1 and re.match(r'[\u3040-\u309f]', base_word): return True
        return False


    def bulk_translate(sentences, batch_size=50):
        translated_dict = {}
        sentences = list(sentences)
        total = len(sentences)
        for i in range(0, total, batch_size):
            batch = sentences[i:i + batch_size]
            print(f"  > Batch translating {i + 1}-{min(i + batch_size, total)} of {total}...")
            try:
                results = translator.translate(batch, src='ja', dest='en')
                if isinstance(results, list):
                    for original, res in zip(batch, results):
                        translated_dict[original] = res.text
                else:
                    translated_dict[batch[0]] = results.text
                time.sleep(1.5)
            except Exception as e:
                print(f"  > Batch failed: {e}. Retrying individually...")
                for s in batch:
                    translated_dict[s] = translate_with_retry(s)
        return translated_dict


    def translate_with_retry(text, retries=3):
        for i in range(retries):
            try:
                time.sleep(random.uniform(1.0, 2.0))
                result = translator.translate(text, src='ja', dest='en')
                if result and result.text: return result.text
            except:
                time.sleep((i + 1) * 2)
        return "[Unavailable]"


    def get_online_definition(word):
        print(f"  > Local dict failed for '{word}'. Trying Jisho API...")
        try:
            url = f"https://jisho.org/api/v1/search/words?keyword={word}"
            response = requests.get(url, timeout=10)
            data = response.json()
            if data['meta']['status'] == 200 and data['data']:
                entry = data['data'][0]
                senses = entry.get('senses', [])
                defs = [f"{i + 1}. {', '.join(s.get('english_definitions', []))}" for i, s in enumerate(senses[:3])]
                formatted_def = "<br>".join(defs)
                reading = word
                if 'japanese' in entry and entry['japanese']:
                    reading = entry['japanese'][0].get('reading', word)
                return formatted_def, reading, "Jisho"
        except:
            pass
        try:
            return f"1. {translate_with_retry(word)} (Auto-translated)", word, "GTranslate"
        except:
            return "No definition found", word, "None"


    def score_sentence(text):
        if len(text) < 5 or len(text) > 60: return 0
        stutter = text.count('…') + text.count('..')
        score = 20 - (stutter * 15)
        score += sum(1 for p in ['は', 'が', 'を', 'に', 'へ', 'と', 'も', 'で'] if p in text) * 3
        if text.endswith(('。', '!', '！')): score += 5
        if any(x in text for x in ['(', '（', '）', ')', '{\\', '-->', '♪']): return -100
        return score


    GRAMMAR_OVERRIDES = {
        'ない': 'Not / There is not (Negative auxiliary)',
        'いる': 'To be (animate) / -ing marker',
        'ある': 'To be (inanimate)',
        'なる': 'To become',
        'くる': 'To come',
        'やる': 'To do',
        'いい': 'Good',
        'よい': 'Good',
        'すごい': 'Amazing',
        'だ': 'Be (Copula)',
        'です': 'Be (Polite Copula)',
        'ます': 'Polite verb suffix',
        'た': 'Past tense marker',
        'て': 'Conjunctive particle (-te form)',
        'ん': 'Explanation / Emphasis marker',
        'の': 'Possessive / Nominalizer',
        'に': 'Target / Direction particle',
        'へ': 'Direction particle',
        'と': 'And / With / Quote marker',
        'も': 'Also / Too',
        'が': 'Subject marker',
        'は': 'Topic marker',
        'を': 'Object marker',
        'から': 'From / Because',
        'けど': 'But / Although',
        'しかし': 'However',
        'こと': 'Thing (intangible) / Nominalizer',
        'もの': 'Thing (tangible)',
        'わけ': 'Reason / Conclusion',
        'ほう': 'Direction / Side',
        'よう': 'Way / Like / As if',
        'くらい': 'About / Approximately',
        'ばかり': 'Just / Only',
        'だけ': 'Only',
        'ため': 'Sake / Purpose',
        'まま': 'As is / Condition',
        'ところ': 'Place / Moment',
        'うえ': 'Above / Upon',
        'うち': 'Inside / While',
        'あげる': 'To give',
        'くれる': 'To give (to me)',
        'もらう': 'To receive',
        'おく': 'To place / Do in advance',
        'しまう': 'To finish / Do completely',
        'みる': 'To try doing',
        'う': 'Volitional (Let\'s...)',
        'ね': 'Right? (Sentence ending)',
        'よ': 'Emphasis (Sentence ending)',
        'な': 'Don\'t / Right? (Sentence ending)',
        'たい': 'Want to...',
        'れる': 'Passive/Potential form',
        'られる': 'Passive/Potential form',
        'させる': 'Causative form',
        'ないで': 'Without doing...',
        'ながら': 'While doing...',
        'ば': 'If...',
        'たら': 'If/When...',
        'なら': 'If (contextual)...'
    }

    # --- ANKI TEMPLATES ---

    # Common style for hover effect
    hover_css = """
    .expression { font-size: 50px; cursor: pointer; position: relative; display: inline-block; font-weight: bold; }
    .expression .reading-hover { visibility: hidden; font-size: 20px; color: #7f8c8d; position: absolute; width: 100%; top: -25px; left: 0; }
    .expression:hover .reading-hover { visibility: visible; }
    """

    style_vocab = """
    .card { font-family: "Noto Sans JP", "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif; text-align: center; background-color: #fdfdfd; padding: 20px; }
    .level { display: inline-block; padding: 2px 10px; border-radius: 5px; background: #3498db; color: white; font-size: 16px; margin-top: 10px; }
    .meaning { text-align: left; margin-top: 20px; font-size: 18px; border-top: 1px solid #ccc; padding-top: 10px; }
    .sentence { margin-top: 20px; font-style: italic; background: #eee; padding: 10px; border-radius: 5px; font-size: 22px; }
    .translation { font-size: 16px; color: #7f8c8d; margin-top: 5px; }
    .footer { font-size: 12px; color: #bdc3c7; margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 5px; }
    """ + hover_css

    style_sentence = """
    .card { font-family: "Noto Sans JP", "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif; text-align: center; background-color: #fdfdfd; padding: 20px; }
    .sentence-front { font-size: 32px; font-weight: normal; margin-bottom: 20px; line-height: 1.5; }
    .sentence-front b { color: #e74c3c; font-weight: 900; } 
    .reading { font-size: 20px; color: #7f8c8d; margin-bottom: 15px; }
    .meaning { text-align: left; font-size: 18px; border-top: 1px solid #ccc; padding-top: 10px; }
    .translation { font-size: 16px; color: #7f8c8d; margin-top: 10px; font-style: italic; }
    .level { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #3498db; color: white; font-size: 12px; }
    """ + hover_css

    fields = [{'name': 'Expression'}, {'name': 'Reading'}, {'name': 'Meaning'}, {'name': 'Level'}, {'name': 'Frequency'},
              {'name': 'Sentence'}, {'name': 'Translation'}, {'name': 'Episodes'}]

    # VOCAB CARD: Standard Front/Back
    vocab_model = genanki.Model(
        MODEL_ID_VOCAB,
        'Japanese Anime Vocab v8 (+1 Sorting)',
        fields=fields,
        templates=[{
            'name': 'Vocab Card',
            'qfmt': '<div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div><br><div class="level">{{Level}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="meaning">{{Meaning}}</div><div class="sentence">{{Sentence}}</div><div class="translation">{{Translation}}</div><div class="footer">Found in: {{Episodes}} | Count: {{Frequency}}x</div>'
        }],
        css=style_vocab
    )

    # SENTENCE CARD: Front is Sentence, Back is Word (with Hover)
    sentence_model = genanki.Model(
        MODEL_ID_SENTENCE,
        'Japanese Anime Sentence v6 (+1 Sorting & Hover)',
        fields=fields,
        templates=[{
            'name': 'Sentence Card',
            'qfmt': '<div class="sentence-front">{{Sentence}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div><br><div class="level">{{Level}}</div><div class="meaning">{{Meaning}}</div><div class="translation">{{Translation}}</div>'
        }],
        css=style_sentence
    )

    vocab_deck = genanki.Deck(DECK_ID_VOCAB, f'Anime Vocabulary:: {show}')
    sentence_deck = genanki.Deck(DECK_ID_SENTENCE, f'Anime Sentences:: {show}')

    # --- DATA PROCESSING ---
    try:
        with open('JLPTWords.json', 'r', encoding='utf8') as file:
            jlpt_data = json.load(file)
    except:
        jlpt_data = {}

    translation_cache = load_cache()
    all_words = []
    word_stats = {}
    word_pos = {}
    word_reading_katakana = {}

    print(f"Scanning transcripts for: {show}")
    for path in os.scandir(f"transcripts/{show}"):
        if path.name.endswith('.srt'):
            ep_name = path.name.replace('.srt', '')
            try:
                with open(path, 'r', encoding='utf8') as file:
                    lines = file.read().split('\n')
            except:
                continue

            for text in lines:
                text = text.strip()
                if '♪' in text: continue
                clean_text = re.sub(r'\{.*?\}', '', text)
                clean_text = re.sub(r'[（\(].*?[）\)]', '', clean_text).strip()
                if not clean_text or "-->" in clean_text or clean_text.isdigit(): continue

                current_score = score_sentence(clean_text)
                if current_score <= 0: continue

                sentence_tokens = []
                for token in t.tokenize(clean_text):
                    base = token.base_form
                    if is_garbage_token(base): continue

                    sentence_tokens.append(base)
                    all_words.append(base)

                    if base not in word_pos:
                        word_pos[base] = token.part_of_speech
                        word_reading_katakana[base] = token.reading

                    if base not in word_stats:
                        word_stats[base] = {'raw': clean_text, 'bolded': '', 'score': -999, 'episodes': set(), 'tokens': []}

                    word_stats[base]['episodes'].add(ep_name)

                    if current_score > word_stats[base]['score']:
                        bolded = re.sub(f"({re.escape(token.surface)})", r"<b>\1</b>", clean_text, count=1)
                        word_stats[base].update({'raw': clean_text, 'bolded': bolded, 'score': current_score, 'tokens': []})

                # Store best sentence tokens for complexity calc
                for token_base in sentence_tokens:
                    if token_base in word_stats and word_stats[token_base]['raw'] == clean_text:
                        word_stats[token_base]['tokens'] = sentence_tokens

    counts = Counter(all_words)
    csv_data = []

    # --- BULK TRANSLATION ---
    print("Identifying sentences for bulk translation...")
    sentences_to_translate = []
    for word, info in word_stats.items():
        if info['raw'] and info['raw'] not in translation_cache:
            sentences_to_translate.append(info['raw'])
    sentences_to_translate = list(set(sentences_to_translate))

    if sentences_to_translate:
        print(f"Translating {len(sentences_to_translate)} new sentences...")
        new_trans = bulk_translate(sentences_to_translate)
        translation_cache.update(new_trans)
        save_cache(translation_cache)

    print("Generating Notes...")

    # --- DECK GENERATION LOGIC ---
    # We split the lists here to sort them differently
    sorted_vocab = [w for w, c in counts.most_common() if c >= 2]
    known_words = set()

    # Storage lists
    vocab_notes_list = []
    sentence_notes_list = []  # Stores tuple: (complexity_score, note_object)

    for word in sorted_vocab:
        # 1. Definition Logic
        pos = word_pos.get(word, "")
        is_proper_noun = '固有名詞' in pos

        if word in GRAMMAR_OVERRIDES:
            meaning = GRAMMAR_OVERRIDES[word]
            reading = word
            source = "Grammar"
        elif is_proper_noun:
            kana = word_reading_katakana.get(word, word)
            romaji = kana_to_romaji(kana)
            meaning = romaji if romaji else "[Proper Noun]"
            reading = word
            source = "ProperNoun"
        else:
            result = jam.lookup(word)
            if result.entries:
                entry = result.entries[0]
                reading = entry.kana_forms[0].text if entry.kana_forms else word
                meaning = "<br>".join(
                    [f"{j + 1}. {', '.join([g.text for g in s.gloss])}" for j, s in enumerate(entry.senses)])
                source = "Jamdict"
            else:
                meaning, reading, source = get_online_definition(word)

        level = jlpt_data.get(word, "Unlabeled")
        if word == "さん": level = "N5"

        info = word_stats.get(word)
        ep_list = ", ".join(sorted(list(info['episodes'])))
        trans = translation_cache.get(info['raw'], "[Unavailable]")

        # 2. Complexity Calculation (For Sentence Deck Sorting)
        sentence_tokens = info.get('tokens', [])
        unknown_count = 0
        for t in sentence_tokens:
            if t != word and t not in known_words:
                unknown_count += 1

        sentence_len = len(info['raw'])
        # Score: Prefer fewer unknowns, then shorter sentences
        # Heavily penalize unknowns (x100), lightly penalize length
        complexity_score = (unknown_count * 100) + sentence_len

        fields_data = [word, reading, meaning, str(level), str(counts[word]), info['bolded'], trans, ep_list]

        # Add to Vocab List (Preserves Frequency Order)
        vocab_notes_list.append(genanki.Note(model=vocab_model, fields=fields_data))

        # Add to Sentence List (Stored with score for sorting)
        sentence_notes_list.append((complexity_score, genanki.Note(model=sentence_model, fields=fields_data)))

        csv_data.append(fields_data)
        known_words.add(word)

    # --- FINAL DECK ADDITION ---

    # 1. Vocab Deck: Add in original Frequency Order
    print(f"Adding {len(vocab_notes_list)} notes to Vocab Deck (Frequency Sorted)...")
    for note in vocab_notes_list:
        vocab_deck.add_note(note)

    # 2. Sentence Deck: Sort by Simplicity, then Add
    print(f"Sorting and adding {len(sentence_notes_list)} notes to Sentence Deck (Simplicity Sorted)...")
    sentence_notes_list.sort(key=lambda x: x[0])  # Sort by score (lowest first)
    for score, note in sentence_notes_list:
        sentence_deck.add_note(note)

    print("Creating APKG package...")
    genanki.Package([vocab_deck, sentence_deck]).write_to_file(f'anki/{show}_Master.apkg')

    with open(f'csv/{show}_Vocabulary_Full.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Expression', 'Reading', 'Meaning', 'Level', 'Frequency', 'Sentence', 'Translation', 'Episodes'])
        writer.writerows(csv_data)

    print(f"Done! Created 'anki/{show}_Master.apkg'.")