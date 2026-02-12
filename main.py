import sys
import json
import os
import csv
import re
import requests
import cv2
import hashlib
import time
import asyncio  # <--- REQUIRED for Edge TTS
from collections import Counter

# --- IMPORTS ---
from sudachipy import tokenizer as sudachi_tokenizer
from sudachipy import dictionary as sudachi_dictionary
from jamdict import Jamdict
import genanki
from deep_translator import GoogleTranslator
import edge_tts  # <--- NEW LIBRARY

try:
    import cgi
except ImportError:
    import legacy_cgi as cgi

    sys.modules['cgi'] = cgi

# ==========================================
# GLOBAL SETUP & CONFIGURATION
# ==========================================

TRANSCRIPT_DIR = 'Transcripts'
MEDIA_DIR = 'react-anime/public/anki/media'

os.makedirs('cache', exist_ok=True)
os.makedirs('react-anime/public/anki', exist_ok=True)
os.makedirs('react-anime/public/csv', exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# 1. Load Exclusions
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
    print("No exclusion list found. Proceeding without exclusions.")

# 2. Load Names
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
    with open(NAME_FILE, 'w', encoding='utf8') as f:
        json.dump(DEFAULT_NAMES, f, ensure_ascii=False, indent=4)


def load_names():
    if os.path.exists(NAME_FILE):
        with open(NAME_FILE, 'r', encoding='utf8') as f:
            return json.load(f)
    return DEFAULT_NAMES


name_map = load_names()

# 3. Load JLPT Data
try:
    with open('JLPTWords.json', 'r', encoding='utf8') as file:
        jlpt_data = json.load(file)
except:
    jlpt_data = {}

# 4. Initialize Tools
print("Initializing dictionary...")
try:
    jam = Jamdict()
    _ = jam.lookup('たべる')
    print("Dictionary loaded successfully.")
except Exception as e:
    print(f"\n[ERROR] Could not load Jamdict: {e}")
    sys.exit(1)

# Initialize Translator
print("Initializing Google Translator (Optimized)...")
translator = GoogleTranslator(source='ja', target='en')

print("Initializing Sudachi tokenizer...")
sudachi_obj = sudachi_dictionary.Dictionary().create()
sudachi_mode = sudachi_tokenizer.Tokenizer.SplitMode.C


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def find_video_fuzzy(show_folder, episode_name):
    video_extensions = ['.mkv', '.mp4', '.avi', '.webm']
    for ext in video_extensions:
        exact_path = os.path.join(show_folder, episode_name + ext)
        if os.path.exists(exact_path):
            return exact_path

    if not os.path.exists(show_folder):
        return None

    files = os.listdir(show_folder)
    potential_matches = []
    for f in files:
        if any(f.endswith(ext) for ext in video_extensions):
            if episode_name in f:
                potential_matches.append(os.path.join(show_folder, f))

    if potential_matches:
        potential_matches.sort(key=lambda x: os.path.getsize(x), reverse=True)
        return potential_matches[0]
    return None


def extract_screenshot(video_path, timestamp_str, output_filename, show):
    # Sanitize the show name for the directory path to avoid encoding issues
    safe_show = re.sub(r'[^\x00-\x7f]', '', show).strip() or "Show"
    show_media_dir = os.path.join(MEDIA_DIR, safe_show)
    output_path = os.path.join(show_media_dir, output_filename)

    if os.path.exists(output_path):
        return True

    if not os.path.exists(show_media_dir):
        os.makedirs(show_media_dir, exist_ok=True)
    try:
        h, m, s = timestamp_str.replace(',', '.').split(':')
        milliseconds = (int(h) * 3600 + int(m) * 60 + float(s)) * 1000
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, milliseconds)
        success, image = cap.read()
        if success:
            image = cv2.resize(image, (854, 480))
            # Use imencode to handle potential non-ascii in output_path if it still exists
            is_success, buffer = cv2.imencode(".jpg", image)
            if is_success:
                with open(output_path, "wb") as f:
                    f.write(buffer)
                cap.release()
                return True
    except Exception as e:
        print(f"OpenCV Error: {e}")
    return False


def generate_id(name, salt=0):
    hash_obj = hashlib.sha256((name + str(salt)).encode())
    return int(hash_obj.hexdigest(), 16) % 10 ** 10


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
    unique_sentences = [s.strip() for s in list(set(sentences)) if s.strip()]
    if not unique_sentences:
        return {}

    def process_batch(batch):
        results_map = {}
        combined_text = "\n".join(batch)
        try:
            translated_block = translator.translate(combined_text)
            translated_lines = translated_block.split("\n")
            if len(translated_lines) == len(batch):
                for orig, trans in zip(batch, translated_lines):
                    results_map[orig] = trans.strip()
                return results_map
            else:
                raise ValueError("Length mismatch")
        except Exception as e:
            if len(batch) > 1:
                mid = len(batch) // 2
                results_map.update(process_batch(batch[:mid]))
                results_map.update(process_batch(batch[mid:]))
            else:
                results_map[batch[0]] = "[Translation Failed]"
            return results_map

    print(f"  > Starting bulk translation of {len(unique_sentences)} sentences...")
    for i in range(0, len(unique_sentences), batch_size):
        current_batch = unique_sentences[i:i + batch_size]
        translated_dict.update(process_batch(current_batch))
        time.sleep(0.6)
    return translated_dict


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
    return "No definition found", word, "None"


def get_definition(word, normalized_word):
    local_result = check_local_dict(word)
    if local_result:
        return local_result

    search_term = normalized_word if normalized_word else word
    result = jam.lookup(search_term)

    if result.entries:
        best_entry = result.entries[0]
        reading = best_entry.kana_forms[0].text if best_entry.kana_forms else search_term
        meaning = "<br>".join(
            [f"{j + 1}. {', '.join([g.text for g in s.gloss])}" for j, s in enumerate(best_entry.senses)])
        return meaning, reading, "Jamdict"

    return get_online_definition(search_term)


def score_sentence(text):
    if len(text) < 5 or len(text) > 60: return 0
    stutter = text.count('…') + text.count('..')
    score = 20 - (stutter * 15)
    score += sum(1 for p in ['は', 'が', 'を', 'に', 'へ', 'と', 'も', 'で'] if p in text) * 3
    if text.endswith(('。', '!', '！')): score += 5
    if any(x in text for x in ['(', '（', '）', ')', '{\\', '-->', '♪']): return -100
    return score


# --- NEW: ASYNC WRAPPER FOR EDGE TTS ---
async def _generate_audio_edge(text, output_file, voice="ja-JP-NanamiNeural"):
    """
    Actually calls the Edge TTS API.
    Voices: ja-JP-NanamiNeural (Female), ja-JP-KeitaNeural (Male)
    """
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"    [EdgeTTS Error] {e}")
        return False


def generate_audio_file(text, filename_prefix, show_name):
    """
    Wrapper that runs the async Edge TTS in a sync way.
    """
    if not text:
        return None, ""

    # Clean filename
    safe_filename = re.sub(r'[\\/*?:"<>|]', "", filename_prefix)
    safe_filename = safe_filename[:100]  # Limit length
    filename = f"{safe_filename}.mp3"

    show_media_dir = os.path.join(MEDIA_DIR, show_name)
    if not os.path.exists(show_media_dir):
        os.makedirs(show_media_dir, exist_ok=True)

    full_path = os.path.join(show_media_dir, filename)

    # Check cache/existence
    if not os.path.exists(full_path):
        # Run async function in sync context
        try:
            asyncio.run(_generate_audio_edge(text, full_path))
        except Exception as e:
            print(f"  [Audio Gen Failed] {e}")
            return None, ""

    # Verify file was actually created
    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
        return full_path, f"[sound:{filename}]"

    return None, ""


# ==========================================
# DICTIONARY CONSTANTS
# ==========================================

# --- NEW TABLE: FREQUENT MISTRANSLATIONS ---
MISTRANSLATION_FIXES = {
    # --- 共通・代名詞・応答 ---
    '私': {'reading': 'わたし', 'meaning': 'I / Me'},
    '僕': {'reading': 'ぼく', 'meaning': 'I / Me (Male pronoun)'},
    '俺': {'reading': 'おれ', 'meaning': 'I / Me (Masculine)'},
    'あんた': {'reading': 'あんた', 'meaning': 'You (informal/blunt)'},
    '奴': {'reading': 'やつ', 'meaning': 'Guy / Person / Fellow / That thing'},
    '人': {'reading': 'ひと', 'meaning': 'Person / People'},
    '様': {'reading': 'さま', 'meaning': 'Sama (Honorific suffix)'},
    'この': {'reading': 'この', 'meaning': 'This (Demonstrative)'},
    '今': {'reading': 'いま', 'meaning': 'Now'},
    '何': {'reading': 'なに', 'meaning': 'What'},
    'うん': {'reading': 'うん', 'meaning': 'Yeah / Yes (casual)'},
    'ううん': {'reading': 'ううん', 'meaning': 'No (casual)'},
    'いえ': {'reading': 'いえ', 'meaning': 'No / Not at all (Polite interjection)'},
    'ダメ': {'reading': 'だめ', 'meaning': 'No / Bad / Forbidden / Useless'},

    # --- 助詞・感嘆詞・フィラー ---
    'ねえ': {'reading': 'ねえ', 'meaning': 'Hey! / Look! / (seeking agreement) / No / Not (Slang negative)'},
    'なあ': {'reading': 'なあ', 'meaning': 'Hey / I wonder (sentence ending particle)'},
    'ちょっと': {'reading': 'ちょっと', 'meaning': 'A little / A moment'},
    'えっと': {'reading': 'えっと', 'meaning': 'Umm... / Let me see... (Filler word)'},
    'って': {'reading': 'って', 'meaning': 'Quotation particle / "They say..." / Topic marker'},
    'コラ': {'reading': 'こら', 'meaning': 'Hey! / Listen! / Watch out! (Interjection)'},
    'ッ': {'reading': 'ッ', 'meaning': '(Glottal stop / Emphasis marker / Clipped sound)'},
    'リ': {'reading': 'り', 'meaning': '(Stuttering sound / Part of a name)'},
    'くらい': {'reading': 'くらい', 'meaning': 'Around / Approximately (Time/Amount)'},

    # --- 文法・活用形 ---
    'てる': {'reading': 'てる', 'meaning': 'is... -ing (Contraction of te-iru)'},
    'ます': {'reading': 'ます', 'meaning': 'Polite verb ending'},
    'たい': {'reading': 'たい', 'meaning': 'Want to... (Verb suffix)'},
    'そう': {'reading': 'そう', 'meaning': 'So / That way / Seeming'},
    'やがる': {'reading': 'やがる', 'meaning': 'Pejorative auxiliary verb (indicates contempt)'},
    'がん': {'reading': 'がん', 'meaning': 'Rough version of "yagaru" (not cancer)'},
    'やん': {'reading': 'やん', 'meaning': 'Part of contraction (yaru -> yannakya) / Emphasis'},
    '前': {'reading': 'まえ', 'meaning': 'Before / Front / Previous'},

    # --- 関西弁 (Kansai-ben) ---
    'なあかん': {'reading': 'なあかん', 'meaning': 'Must do / Have to (Kansai-ben)'},
    'へん': {'reading': 'へん', 'meaning': 'Negative verb ending (Kansai-ben "nai")'},

    # --- 専門用語・固有名詞 (作品別) ---
    # Lucky Star / K-ON! / School Context
    '占う': {'reading': 'うらなう', 'meaning': 'To tell fortunes / To predict'},
    '外れる': {'reading': 'はずれる', 'meaning': 'To miss / To lose (lottery) / To fail'},
    'プレイ': {'reading': 'プレイ', 'meaning': 'Play (game/sport) / Video Game Play'},
    '部長': {'reading': 'ぶちょう', 'meaning': 'Club President (School Context)'},
    'お茶': {'reading': 'おちゃ', 'meaning': 'Tea / (ready to drink)'},
    '入る': {'reading': 'はいる', 'meaning': 'To enter / To be poured (tea) / To be ready'},
    '王道': {'reading': 'おうどう', 'meaning': 'The classic way / Royal road / Standard path'},
    '唯': {'reading': 'ゆい', 'meaning': 'Yui (Character Name)'},
    'ロンドン': {'reading': 'ろんどん', 'meaning': 'London'},
    'ネス湖': {'reading': 'ねすこ', 'meaning': 'Loch Ness'},
    '皆勤賞': {'reading': 'かいきんしょう', 'meaning': 'Perfect Attendance Award'},
    '教えの庭': {'reading': 'おしえのにわ', 'meaning': 'Garden of learning / School campus'},

    # Gaming / Battle (Bakugan / Yu-Gi-Oh! / SK8)
    '決闘': {'reading': 'けっとう', 'meaning': 'Duel'},
    '召喚': {'reading': 'しょうかん', 'meaning': 'Summon / Summoning (Monster)'},
    '融合': {'reading': 'ゆうごう', 'meaning': 'Fusion / Polymerization'},
    '術': {'reading': 'じゅつ', 'meaning': 'Jutsu / Technique / Art'},
    '腕': {'reading': 'うで', 'meaning': 'Skill / Ability (in games/sports)'},
    '読み': {'reading': 'よみ', 'meaning': 'Predicting the opponent / Reading the game'},
    '爆': {'reading': 'ばく', 'meaning': 'Baku (Explosive/Bakugan prefix)'},
    '向く': {'reading': 'むく', 'meaning': 'To face / To point toward'},
    '仲間': {'reading': 'なかま', 'meaning': 'Friend / Comrade / Teammate'},
    '愛抱夢': {'reading': 'あだむ', 'meaning': 'Adam (Antagonist Name)'},
    'あぶねえ': {'reading': 'あぶねえ', 'meaning': 'Dangerous! / Watch out!'},

    # Beastars / Shirokuma Cafe
    '食殺': {'reading': 'しょくさつ', 'meaning': 'Predation / Meat-eating murder'},
    '隕石祭': {'reading': 'いんせきさい', 'meaning': 'Meteor Festival'},
    'テム': {'reading': 'てむ', 'meaning': 'Tem (Character Name)'},
    '笹子': {'reading': 'ささこ', 'meaning': 'Sasako (Waitress)'},
    'ゾウガメ': {'reading': 'ぞうがめ', 'meaning': 'Giant Tortoise'},
    'パンダママ': {'reading': 'ぱんだまま', 'meaning': 'Panda-mama'},
    '常勤パンダ': {'reading': 'じょうきんぱんだ', 'meaning': 'Full-time Panda'},

    # WataMote / Saiki K / Others
    'ヘヘ': {'reading': 'へへ', 'meaning': 'Heh-heh (Awkward laughter)'},
    'おっふ': {'reading': 'おっふ', 'meaning': 'Offu! (Awestruck sound)'},
    'くだらない': {'reading': 'くだらない', 'meaning': 'Stupid / Worthless / Trivial'},
    '喪女': {'reading': 'もじょ', 'meaning': 'Mojo (Unpopular woman / Femcel slang)'},
    'もこっち': {'reading': 'もこっち', 'meaning': 'Mokocchi (Nickname)'},
    '独り言': {'reading': 'ひとりごと', 'meaning': 'Speaking to oneself / Monologue'},

    # その他修正
    'さいふ': {'reading': 'さいふ', 'meaning': 'Wallet / Purse'},
    'チュー': {'reading': 'ちゅう', 'meaning': 'Kiss (onomatopoeia)'},
    '分': {'reading': 'ぶん', 'meaning': 'Part / Portion / Amount / Share'},
    'ド': {'reading': 'ド', 'meaning': 'D (as in Dreadnought) / Super-'},
    '目': {'reading': 'め', 'meaning': 'Eye / (part of idiom "teach a lesson")'},
    '気を取り直す': {'reading': 'きをとりなおす', 'meaning': 'To pull oneself together / To refresh ones mood'},
    '預かる': {'reading': 'あずかる', 'meaning': 'To look after / To take care of (luggage, etc.)'},
    '預かっとく': {'reading': 'あずかっとく', 'meaning': "I'll look after it (for you)"},
    'モー': {'reading': 'モー', 'meaning': 'Mo- (part of "Moment")'},
    'メン': {'reading': 'メン', 'meaning': '-men (part of "Moment")'},
    'プリー': {'reading': 'プリー', 'meaning': 'Plea- (part of "Please")'},

    # Pronoun & Particle Fixes
    'が': {'reading': 'が', 'meaning': 'Subject Marker (Particle)'},
    'は': {'reading': 'は', 'meaning': 'Topic Marker (Particle)'},
    'を': {'reading': 'を', 'meaning': 'Object Marker (Particle)'},

    # Character Name Fixes (Literal Noun Traps)
    '紬': {'reading': 'つむぎ', 'meaning': 'Tsumugi (Character Name)'},
    # Emphatic & Slang Fixes
    'てめえ': {'reading': 'てめえ', 'meaning': 'You (Very rude/aggressive)'},

    # --- Structural Fixes (Stutters/Parsing) ---
    'メ': {'reading': 'め', 'meaning': 'Part of "Dame" (No) or part of a word'},
    '・': {'reading': '・', 'meaning': '(Punctuation / Name separator)'},
    'ヶ': {'reading': 'ヶ', 'meaning': '(Counter / Place name marker)'},

    # --- Context-Specific Terminology ---
    '玉': {'reading': 'たま', 'meaning': 'Ball / Coin / Sphere / Attack orb'},
    '弾': {'reading': 'たま', 'meaning': 'Bullet / Blast / Projectile'},
}

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

HOVER_CSS = """
.expression { font-size: 50px; cursor: pointer; position: relative; display: inline-block; font-weight: bold; }
.expression .reading-hover { visibility: hidden; font-size: 20px; color: #7f8c8d; position: absolute; width: 100%; top: -25px; left: 0; }
.expression:hover .reading-hover { visibility: visible; }
"""

STYLE_VOCAB = """
.card { font-family: "Noto Sans JP", "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif; text-align: center; background-color: #fdfdfd; padding: 20px; }
.level { display: inline-block; padding: 2px 10px; border-radius: 5px; background: #3498db; color: white; font-size: 16px; margin-top: 10px; }
.meaning { text-align: left; margin-top: 20px; font-size: 18px; border-top: 1px solid #ccc; padding-top: 10px; }
.sentence { margin-top: 20px; font-style: italic; background: #eee; padding: 10px; border-radius: 5px; font-size: 22px; }
.translation { font-size: 16px; color: #7f8c8d; margin-top: 5px; }
.screenshot { margin-top: 15px; }
.screenshot img { max-width: 100%; height: auto; border-radius: 5px; }
.footer { font-size: 12px; color: #bdc3c7; margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 5px; }
""" + HOVER_CSS


# ==========================================
# CORE FUNCTION: PROCESS SINGLE SHOW
# ==========================================

def process_single_show(show):
    show_path = os.path.join(TRANSCRIPT_DIR, show)
    if not os.path.isdir(show_path):
        return

    print(f"\n===============================")
    print(f"PROCESSING SHOW: {show}")
    print(f"===============================")

    MODEL_ID_VOCAB = generate_id(show, salt=1)
    DECK_ID_VOCAB = generate_id(show, salt=2)
    MODEL_ID_SENTENCE = generate_id(show, salt=3)
    DECK_ID_SENTENCE = generate_id(show, salt=4)
    CACHE_FILE = f"cache/{show}_cache.json"

    def load_cache_local():
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf8') as f:
                return json.load(f)
        return {}

    def save_cache_local(cache_data):
        with open(CACHE_FILE, 'w', encoding='utf8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)

    # --- UPDATED FIELDS: Added WordAudio and SentenceAudio ---
    fields = [{'name': 'Expression'}, {'name': 'Reading'}, {'name': 'Meaning'}, {'name': 'Level'},
              {'name': 'Frequency'}, {'name': 'Sentence'}, {'name': 'Translation'},
              {'name': 'Episodes'}, {'name': 'Image'}, {'name': 'WordAudio'}, {'name': 'SentenceAudio'}]

    vocab_model = genanki.Model(
        MODEL_ID_VOCAB, 'Japanese Anime Vocab v10 (Screenshots + Audio)', fields=fields,
        templates=[{
            'name': 'Vocab Card',
            # Added {{WordAudio}} to Front
            'qfmt': '<div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div><br>{{WordAudio}}<br><div class="level">{{Level}}</div>',
            # Added {{SentenceAudio}} to Back
            'afmt': '{{FrontSide}}<hr id="answer"><div class="meaning">{{Meaning}}</div><div class="sentence">{{Sentence}}<br>{{SentenceAudio}}</div><div class="translation">{{Translation}}</div><div class="screenshot">{{Image}}</div><div class="footer">Found in: {{Episodes}} | Count: {{Frequency}}x</div>'
        }], css=STYLE_VOCAB
    )

    sentence_model = genanki.Model(
        MODEL_ID_SENTENCE, 'Japanese Anime Sentence v8 (Screenshots + Audio)', fields=fields,
        templates=[{
            'name': 'Sentence Card',
            # Added {{SentenceAudio}} to Front
            'qfmt': '<div class="sentence-front">{{Sentence}}<br>{{SentenceAudio}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="expression"><span class="reading-hover">{{Reading}}</span>{{Expression}}</div><br>{{WordAudio}}<div class="level">{{Level}}</div><div class="meaning">{{Meaning}}</div><div class="translation">{{Translation}}</div><div class="screenshot">{{Image}}</div>'
        }], css=STYLE_VOCAB
    )

    vocab_deck = genanki.Deck(DECK_ID_VOCAB, f'Anime Vocabulary:: {show}')
    sentence_deck = genanki.Deck(DECK_ID_SENTENCE, f'Anime Sentences:: {show}')

    translation_cache = load_cache_local()
    all_words = []
    word_stats = {}
    word_pos = {}
    word_reading_katakana = {}
    word_normalized = {}
    media_files_to_package = []
    video_search_path = os.path.join(f'shows/{show}/')

    print(f"Scanning transcripts in: {show_path}")

    for path in os.scandir(show_path):
        is_srt = path.name.endswith('.srt')
        is_ass = path.name.endswith('.ass')
        if is_srt or is_ass:
            ep_name = path.name.replace('.srt', '').replace('.ass', '')
            video_file = find_video_fuzzy(video_search_path, ep_name)
            if video_file:
                print(f"  [Info] Video Found: {os.path.basename(video_file)}")
            else:
                pass

            try:
                with open(path, 'r', encoding='utf8') as file:
                    lines = file.read().split('\n')
            except:
                continue

            parsed_lines = []
            if is_srt:
                for i, line in enumerate(lines):
                    if "-->" in line:
                        start_time = line.split("-->")[0].strip()
                        text_lines = []
                        j = i + 1
                        while j < len(lines) and lines[j].strip() != "" and not lines[j].strip().isdigit():
                            t = lines[j].strip()
                            clean_t = re.sub(r'\{.*?\}', '', t)
                            clean_t = re.sub(r'[（\(].*?[）\)]', '', clean_t).strip()
                            if clean_t and "-->" not in clean_t:
                                text_lines.append(clean_t)
                            j += 1
                        full_text = " ".join(text_lines)
                        if full_text and "♪" not in full_text:
                            parsed_lines.append((full_text, start_time))
            elif is_ass:
                for text in lines:
                    if text.startswith('Dialogue:'):
                        parts = text.split(',', 9)
                        if len(parts) > 9:
                            start_time = parts[1].strip()
                            content = parts[9].strip()
                            if '♪' in content: continue
                            clean_text = re.sub(r'\{.*?\}', '', content)
                            clean_text = clean_text.replace(r'\N', ' ').replace(r'\n', ' ').replace(r'\h', ' ')
                            clean_text = re.sub(r'[（\(].*?[）\)]', '', clean_text).strip()
                            if clean_text:
                                parsed_lines.append((clean_text, start_time))

            for clean_text, timestamp in parsed_lines:
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
                                            'tokens': [], 'video': None, 'timestamp': None}
                    word_stats[base]['episodes'].add(ep_name)
                    if current_score > word_stats[base]['score']:
                        bolded = re.sub(f"({re.escape(token.surface())})", r"<b>\1</b>", clean_text, count=1)
                        word_stats[base].update(
                            {'raw': clean_text, 'bolded': bolded, 'score': current_score, 'tokens': [],
                             'video': video_file, 'timestamp': timestamp})
                for token_base in sentence_tokens:
                    if token_base in word_stats and word_stats[token_base]['raw'] == clean_text:
                        word_stats[token_base]['tokens'] = sentence_tokens

    counts = Counter(all_words)
    csv_data = []
    print("Identifying sentences for bulk translation...")
    sentences_to_translate = []
    for word, info in word_stats.items():
        clean_sentence = info['raw'].strip() if info['raw'] else None
        if clean_sentence and clean_sentence not in translation_cache:
            sentences_to_translate.append(clean_sentence)
    sentences_to_translate = list(set(sentences_to_translate))

    if sentences_to_translate:
        print(f"Found {len(sentences_to_translate)} new sentences. Translating...")
        batch_size = 20
        for i in range(0, len(sentences_to_translate), batch_size):
            batch = sentences_to_translate[i:i + batch_size]
            new_results = bulk_translate(batch)
            translation_cache.update(new_results)
            save_cache_local(translation_cache)
            print(
                f"    Progress: {min(i + batch_size, len(sentences_to_translate))}/{len(sentences_to_translate)} sentences cached.")

    print("Generating Notes, Screenshots, and Audio...")
    sorted_vocab = [w for w, c in counts.most_common() if c >= 2]
    known_words = set()
    vocab_notes_list = []
    sentence_notes_list = []

    for i, word in enumerate(sorted_vocab):
        pos = word_pos.get(word, "")
        norm = word_normalized.get(word, word)
        is_proper_noun = '固有名詞' in pos

        # --- PRIORITY CHECK: Mistranslations & Grammar ---
        if word in MISTRANSLATION_FIXES:
            meaning = MISTRANSLATION_FIXES[word]['meaning']
            reading = MISTRANSLATION_FIXES[word]['reading']
            source = "ManualFix"
        elif word in GRAMMAR_DICT:
            meaning = GRAMMAR_DICT[word]
            reading = word
            source = "GrammarDict"
            if word in word_reading_katakana: reading = word_reading_katakana[word]
        elif word in name_map:
            meaning = name_map[word]
            reading = word
            source = "NameMap"
            if word in word_reading_katakana: reading = word_reading_katakana[word]
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

        # --- FIXED SCREENSHOT LOGIC ---
        image_field = ""
        if info.get('video') and info.get('timestamp'):
            clean_ts = info['timestamp'].replace(':', '_').replace(',', '_').replace('.', '_')
            clean_ep = os.path.basename(info['video']).split('.')[0]
            img_filename = f"{clean_ep}_{clean_ts}.jpg"
            full_local_path = os.path.join(MEDIA_DIR, show, img_filename)

            if extract_screenshot(info['video'], info['timestamp'], img_filename, show):
                image_field = f'<img src="{img_filename}">'
                media_files_to_package.append(full_local_path)

        # --- AUDIO GENERATION LOGIC ---
        # 1. Generate Word Audio
        word_hash = hashlib.sha256(word.encode()).hexdigest()[:8]
        word_audio_path, word_audio_field = generate_audio_file(word, f"{show}_word_{word_hash}", show)
        if word_audio_path: media_files_to_package.append(word_audio_path)

        # 2. Generate Sentence Audio
        sent_audio_field = ""
        clean_sentence_text = info['raw']
        if clean_sentence_text:
            sent_hash = hashlib.sha256(clean_sentence_text.encode()).hexdigest()[:8]
            sent_audio_path, sent_audio_field = generate_audio_file(clean_sentence_text, f"{show}_sent_{sent_hash}",
                                                                    show)
            if sent_audio_path: media_files_to_package.append(sent_audio_path)

        sentence_tokens_list = info.get('tokens', [])
        unknown_count = 0
        for t in sentence_tokens_list:
            if t != word and t not in known_words:
                unknown_count += 1
        sentence_len = len(info['raw'])
        complexity_score = (unknown_count * 100) + sentence_len

        # Updated Fields List
        fields_data = [word, reading, meaning, str(level), str(counts[word]), info['bolded'], trans, ep_list,
                       image_field, word_audio_field, sent_audio_field]
        csv_data.append(fields_data)

        if word not in excluded_words:
            vocab_notes_list.append(genanki.Note(model=vocab_model, fields=fields_data))
            sentence_notes_list.append((complexity_score, genanki.Note(model=sentence_model, fields=fields_data)))
        known_words.add(word)
        if i % 20 == 0:  # Reduced print freq slightly
            print(f"  > Processed {i}/{len(sorted_vocab)} words...")

    print(f"Adding {len(vocab_notes_list)} notes to Vocab Deck...")
    for note in vocab_notes_list:
        vocab_deck.add_note(note)
    print(f"Adding {len(sentence_notes_list)} notes to Sentence Deck...")
    sentence_notes_list.sort(key=lambda x: x[0])
    for score, note in sentence_notes_list:
        sentence_deck.add_note(note)
    print("Creating APKG package...")
    media_files_to_package = list(set(media_files_to_package))
    genanki.Package([vocab_deck, sentence_deck], media_files=media_files_to_package).write_to_file(
        f'react-anime/public/anki/{show}_Master.apkg')

    # Update CSV Header for new fields
    with open(f'react-anime/public/csv/{show}_Vocabulary_Full.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(
            ['Expression', 'Reading', 'Meaning', 'Level', 'Frequency', 'Sentence', 'Translation', 'Episodes', 'Image',
             'WordAudio', 'SentenceAudio'])
        writer.writerows(csv_data)
    print(f"Done! Created '{show}_Master.apkg' with screenshots and audio.")


if __name__ == "__main__":
    if not os.path.exists(TRANSCRIPT_DIR):
        print(f"Error: '{TRANSCRIPT_DIR}' directory not found.")
        sys.exit(1)
    shows = os.listdir(TRANSCRIPT_DIR)
    print(f"Found {len(shows)} folders in {TRANSCRIPT_DIR}.")
    for show in shows:
        process_single_show(show)