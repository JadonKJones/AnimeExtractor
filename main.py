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
from sudachipy import tokenizer as sudachi_tokenizer
from sudachipy import dictionary as sudachi_dictionary
from jamdict import Jamdict
from deep_translator import GoogleTranslator
import genanki

try:
    import cgi
except ImportError:
    import legacy_cgi as cgi

    sys.modules['cgi'] = cgi

# --- SETUP START ---

excluded_words = set()
if os.path.exists('core lists/1.5K.json'):
    with open('core lists/1.5K.json', 'r', encoding='utf8') as f:
        file_data = json.load(f)
        for entry in file_data:
            if isinstance(entry, dict) and 'word' in entry:
                excluded_words.add(entry['word'])
            elif isinstance(entry, str):
                excluded_words.add(entry)
    print(f"Loaded exclusion list. Total excluded words: {len(excluded_words)}")
else:
    print("No exclusion list found at 'core lists/1.5K.json'. Proceeding without exclusions.")

NAME_FILE = 'names.json'
DEFAULT_NAMES = {
    "遊戯": "Yugi", "城之内": "Jonouchi", "海馬": "Kaiba", "本田": "Honda", "杏子": "Anzu",
    "モクバ": "Mokuba", "ペガサス": "Pegasus", "獏良": "Bakura", "マリク": "Marik",
    "サトシ": "Satoshi (Ash)", "カスミ": "Kasumi (Misty)", "タケシ": "Takeshi (Brock)",
    "ピカチュウ": "Pikachu", "ムサシ": "Musashi (Jessie)", "コジロウ": "Kojiro (James)", "ニャース": "Nyarth (Meowth)",
    "ナルト": "Naruto", "サスケ": "Sasuke", "サクラ": "Sakura", "カカシ": "Kakashi",
    "ヒナタ": "Hinata", "シカマル": "Shikamaru", "イノ": "Ino", "チョウジ": "Choji",
    "ゆっこ": "Yukko", "みお": "Mio", "麻衣": "Mai", "はかせ": "Hakase", "なの": "Nano", "阪本": "Sakamoto",
    "唯": "Yui", "澪": "Mio", "律": "Ritsu", "紬": "Tsumugi", "梓": "Azusa", "憂": "Ui", "和": "Nodoka",
    "こなた": "Konata", "かがみ": "Kagami", "つかさ": "Tsukasa", "みゆき": "Miyuki",
    "レゴシ": "Legoshi", "ハル": "Haru", "ルイ": "Louis", "ジュノ": "Juno", "ジャック": "Jack",
    "千代": "Chiyo", "大阪": "Osaka", "智": "Tomo", "暦": "Yomi", "榊": "Sakaki", "神楽": "Kagura",
    "ランガ": "Langa", "レキ": "Reki", "ジョー": "Joe", "チェリー": "Cherry", "愛抱夢": "Adam",
    "あず": "Azu (Azusa)"
}

if not os.path.exists(NAME_FILE):
    print(f"Creating default {NAME_FILE} with character names...")
    with open(NAME_FILE, 'w', encoding='utf8') as f:
        json.dump(DEFAULT_NAMES, f, ensure_ascii=False, indent=4)


def load_names():
    if os.path.exists(NAME_FILE):
        with open(NAME_FILE, 'r', encoding='utf8') as f:
            return json.load(f)
    return DEFAULT_NAMES


name_map = load_names()

# --- JAMDICT INITIALIZATION ---
print("Initializing dictionary...")
try:
    jam = Jamdict()
    test_lookup = jam.lookup('たべる')
    print("Dictionary loaded successfully.")
except Exception as e:
    print("\n[ERROR] Could not load the Jamdict dictionary.")
    print(f"Error Details: {e}")
    print("\nPLEASE RUN THIS COMMAND IN YOUR TERMINAL TO INSTALL THE DICTIONARY:")
    print("    python -m pip install jamdict-data")
    sys.exit(1)

# Initialize Translator
translator = GoogleTranslator(source='ja', target='en')
TRANSCRIPT_DIR = 'Transcripts'

os.makedirs('cache', exist_ok=True)
os.makedirs('react-anime/public/anki', exist_ok=True)
os.makedirs('react-anime/public/csv', exist_ok=True)

if not os.path.exists(TRANSCRIPT_DIR):
    print(f"Error: '{TRANSCRIPT_DIR}' directory not found.")
    sys.exit(1)

# Initialize Sudachi Tokenizer
print("Initializing Sudachi tokenizer...")
sudachi_obj = sudachi_dictionary.Dictionary().create()
sudachi_mode = sudachi_tokenizer.Tokenizer.SplitMode.C

for show in os.listdir(TRANSCRIPT_DIR):
    show_path = os.path.join(TRANSCRIPT_DIR, show)

    if not os.path.isdir(show_path):
        continue

    print(f"\nProcessing Show: {show}")


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


    def is_garbage_token(base_word):
        if not re.match(r'^[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\u3005\u30fc]+$', base_word):
            return True
        if len(base_word) == 1 and re.match(r'[\u3040-\u309f]', base_word):
            return True
        return False


    def bulk_translate(sentences, batch_size=50):
        translated_dict = {}
        sentences = list(sentences)
        total = len(sentences)
        for i in range(0, total, batch_size):
            batch = sentences[i:i + batch_size]
            print(f"  > Batch translating {i + 1}-{min(i + batch_size, total)} of {total}...")
            try:
                results = translator.translate_batch(batch)
                if isinstance(results, list):
                    for original, res in zip(batch, results):
                        translated_dict[original] = res
                else:
                    translated_dict[batch[0]] = results
                time.sleep(1.0)
            except Exception as e:
                print(f"  > Batch failed: {e}. Retrying individually...")
                for s in batch:
                    translated_dict[s] = translate_with_retry(s)
        return translated_dict


    def translate_with_retry(text, retries=3):
        for i in range(retries):
            try:
                time.sleep(random.uniform(1.0, 2.0))
                result = translator.translate(text)
                if result: return result
            except:
                time.sleep((i + 1) * 2)
        return "[Unavailable]"


    def get_definition(word, normalized_word):
        # 1. Try Local Dict
        local_result = check_local_dict(word)
        if local_result:
            return local_result

        # 2. Try Jamdict with Normalized Form
        search_term = normalized_word if normalized_word else word
        result = jam.lookup(search_term)

        if result.entries:
            # Simple fallback: just grab the first valid entry
            best_entry = result.entries[0]
            reading = best_entry.kana_forms[0].text if best_entry.kana_forms else search_term
            meaning = "<br>".join(
                [f"{j + 1}. {', '.join([g.text for g in s.gloss])}" for j, s in enumerate(best_entry.senses)])
            return meaning, reading, "Jamdict"

        # 3. Fallback to Jisho API
        return get_online_definition(search_term)


    def check_local_dict(word, filename='dict.csv'):
        if not os.path.exists(filename):
            return None
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip() == word:
                    return row[1].strip(), row[2].strip(), row[3].strip()
        return None


    def get_online_definition(word):
        print(f"  > Dictionary failed for '{word}'. Trying Jisho API...")
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


    # --- THE GRAMMAR DICTIONARY ---
    # This list intercepts the dictionary lookup for common structure words.
    GRAMMAR_DICT = {
        'ない': 'Not (Negative / Nonexistent)',
        'する': 'To do / To make',
        'てる': 'is... -ing (Contraction of te-iru)',
        'で': 'At / By / With (Particle)',
        'に': 'To / At (Target Particle)',
        'を': 'Object Marker',
        'は': 'Topic Marker (As for...)',
        'が': 'Subject Marker',
        'の': 'Possessive / Nominalizer (of / \'s)',
        'と': 'And / With / Quotation',
        'も': 'Also / Too',
        'へ': 'To (Direction Particle)',
        'から': 'From / Because',
        'けど': 'But / Although',
        'し': 'And / Besides',
        'です': 'To be (Polite Copula)',
        'ます': 'Polite Sentence Ending (Verb Suffix)',
        'だ': 'To be (Plain Copula)',
        'って': 'Topic Marker / Quotation ("You said..")',
        'て': 'Conjunctive Particle (And then...)',
        'た': 'Past Tense Marker',
        'ね': 'Right? (Sentence Ending)',
        'よ': 'Emphasis (Sentence Ending)',
        'な': 'Don\'t / Right? (Sentence Ending)',
        'ん': 'Explanation / Emphasis',
        'う': 'Volitional (Let\'s...)',
        'よう': 'Seem / Like / Way',
        'こと': 'Thing (Intangible) / Nominalizer',
        'もの': 'Thing (Tangible)',
        'この': 'This (Near Speaker)',
        'その': 'That (Near Listener)',
        'あの': 'That (Distant)',
        'どの': 'Which?',
        'これ': 'This one',
        'それ': 'That one',
        'あれ': 'That one over there',
        'どれ': 'Which one?',
        'ここ': 'Here',
        'そこ': 'There',
        'あそこ': 'Over there',
        'どこ': 'Where?',
        'ちゃん': 'Suffix for familiar names (Cute/Female)',
        'くん': 'Suffix for familiar names (Male)',
        'さん': 'Suffix for names (Mr./Ms.)',
        'ちゃう': 'To do completely / Regret (te-shimau)',
        'なきゃ': 'Must do (nakereba)',
        'じゃ': 'Well then / To be (de-wa)',
        'たい': 'Want to...',
        'れる': 'Passive / Potential Form',
        'られる': 'Passive / Potential Form',
        'させる': 'Causative Form',
        'っ': 'Small Tsu (Glottal Stop)',
        'ー': 'Long Vowel Mark'
    }

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

    fields = [{'name': 'Expression'}, {'name': 'Reading'}, {'name': 'Meaning'}, {'name': 'Level'},
              {'name': 'Frequency'},
              {'name': 'Sentence'}, {'name': 'Translation'}, {'name': 'Episodes'}]

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
    word_normalized = {}

    print(f"Scanning transcripts for: {show}")

    for path in os.scandir(show_path):
        is_srt = path.name.endswith('.srt')
        is_ass = path.name.endswith('.ass')

        if is_srt or is_ass:
            ep_name = path.name.replace('.srt', '').replace('.ass', '')
            try:
                with open(path, 'r', encoding='utf8') as file:
                    lines = file.read().split('\n')
            except:
                continue

            parsed_lines = []

            if is_srt:
                for text in lines:
                    text = text.strip()
                    if '♪' in text: continue
                    clean_text = re.sub(r'\{.*?\}', '', text)
                    clean_text = re.sub(r'[（\(].*?[）\)]', '', clean_text).strip()
                    if not clean_text or "-->" in clean_text or clean_text.isdigit(): continue
                    parsed_lines.append(clean_text)

            elif is_ass:
                for text in lines:
                    if text.startswith('Dialogue:'):
                        parts = text.split(',', 9)
                        if len(parts) > 9:
                            content = parts[9].strip()
                            if '♪' in content: continue
                            clean_text = re.sub(r'\{.*?\}', '', content)
                            clean_text = clean_text.replace(r'\N', ' ').replace(r'\n', ' ').replace(r'\h', ' ')
                            clean_text = re.sub(r'[（\(].*?[）\)]', '', clean_text).strip()
                            if clean_text:
                                parsed_lines.append(clean_text)

            for clean_text in parsed_lines:
                current_score = score_sentence(clean_text)
                if current_score <= 0: continue

                sentence_tokens = []
                for token in sudachi_obj.tokenize(clean_text, sudachi_mode):
                    base = token.dictionary_form()
                    norm = token.normalized_form()

                    if is_garbage_token(base): continue

                    sentence_tokens.append(base)
                    all_words.append(base)

                    pos_str = ",".join(token.part_of_speech())
                    reading_str = token.reading_form()

                    if base not in word_pos:
                        word_pos[base] = pos_str
                        word_reading_katakana[base] = reading_str
                        word_normalized[base] = norm

                    if base not in word_stats:
                        word_stats[base] = {'raw': clean_text, 'bolded': '', 'score': -999, 'episodes': set(),
                                            'tokens': []}

                    word_stats[base]['episodes'].add(ep_name)

                    if current_score > word_stats[base]['score']:
                        bolded = re.sub(f"({re.escape(token.surface())})", r"<b>\1</b>", clean_text, count=1)
                        word_stats[base].update(
                            {'raw': clean_text, 'bolded': bolded, 'score': current_score, 'tokens': []})

                for token_base in sentence_tokens:
                    if token_base in word_stats and word_stats[token_base]['raw'] == clean_text:
                        word_stats[token_base]['tokens'] = sentence_tokens

    counts = Counter(all_words)
    csv_data = []

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

    sorted_vocab = [w for w, c in counts.most_common() if c >= 2]
    known_words = set()

    vocab_notes_list = []
    sentence_notes_list = []

    for word in sorted_vocab:
        pos = word_pos.get(word, "")
        norm = word_normalized.get(word, word)
        is_proper_noun = '固有名詞' in pos

        if word in GRAMMAR_DICT:
            meaning = GRAMMAR_DICT[word]
            reading = word
            source = "GrammarDict"
            # Ensure reading is correct even if overridden
            if word in word_reading_katakana:
                reading = word_reading_katakana[word]

        elif word in name_map:
            meaning = name_map[word]
            reading = word
            source = "NameMap"
            if word in word_reading_katakana:
                reading = word_reading_katakana[word]

        else:
            if is_proper_noun:
                kana = word_reading_katakana.get(word, word)
                romaji = kana_to_romaji(kana)
                meaning = romaji if romaji else "[Proper Noun]"
                reading = word
                source = "ProperNoun"
            else:
                meaning, reading, source = get_definition(word, norm)
                with open('dict.csv', 'a', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([word, meaning, reading, source])

        level = jlpt_data.get(word, "Unlabeled")
        if word == "さん": level = "N5"

        info = word_stats.get(word)
        ep_list = ", ".join(sorted(list(info['episodes'])))
        trans = translation_cache.get(info['raw'], "[Unavailable]")

        sentence_tokens = info.get('tokens', [])
        unknown_count = 0
        for t in sentence_tokens:
            if t != word and t not in known_words:
                unknown_count += 1

        sentence_len = len(info['raw'])
        complexity_score = (unknown_count * 100) + sentence_len

        fields_data = [word, reading, meaning, str(level), str(counts[word]), info['bolded'], trans, ep_list]
        csv_data.append(fields_data)

        if word not in excluded_words:
            vocab_notes_list.append(genanki.Note(model=vocab_model, fields=fields_data))
            sentence_notes_list.append((complexity_score, genanki.Note(model=sentence_model, fields=fields_data)))

        known_words.add(word)

    print(f"Adding {len(vocab_notes_list)} notes to Vocab Deck (Frequency Sorted)...")
    for note in vocab_notes_list:
        vocab_deck.add_note(note)

    print(f"Sorting and adding {len(sentence_notes_list)} notes to Sentence Deck (Simplicity Sorted)...")
    sentence_notes_list.sort(key=lambda x: x[0])
    for score, note in sentence_notes_list:
        sentence_deck.add_note(note)

    print("Creating APKG package...")
    genanki.Package([vocab_deck, sentence_deck]).write_to_file(f'react-anime/public/anki/{show}_Master.apkg')

    with open(f'react-anime/public/csv/{show}_Vocabulary_Full.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(
            ['Expression', 'Reading', 'Meaning', 'Level', 'Frequency', 'Sentence', 'Translation', 'Episodes'])
        writer.writerows(csv_data)

    print(f"Done! Created 'anki/{show}_Master.apkg' and 'csv/{show}_Vocabulary_Full.csv' (CSV contains full list).")