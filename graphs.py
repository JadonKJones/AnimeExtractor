import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import re
from collections import Counter

# --- THE FIX FOR JAPANESE CHARACTERS ---
plt.rcParams['font.family'] = 'MS Gothic'

show = "K-ON! Movie"
csv_file = f"react-anime/public/csv/{show}_Vocabulary_Full.csv"
core_folder = "core lists/"  # Path to your .json files

if not os.path.exists(csv_file):
    print(f"Error: {csv_file} not found!")
    exit()

# --- LOAD CORE LISTS FROM JSON ---
core_sets = {"1.5K": set(),"2K": set(), "10K": set()}
if os.path.exists(core_folder):
    for filename in os.listdir(core_folder):
        if not filename.endswith(".json"): continue

        target_key = filename[:-5]

        if target_key:
            try:
                with open(os.path.join(core_folder, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    words = [entry['word'] for entry in data if 'word' in entry]
                    core_sets[target_key].update(words)
            except Exception as e:
                print(f"Error loading {filename}: {e}")

# --- LOAD ANIME DATA ---
df = pd.read_csv(csv_file)


# --- REFINED CATEGORIES ---
def refine_level(row):
    meaning = str(row['Meaning'])
    if any(x in meaning for x in ["Grammar", "auxiliary", "particle", "Copula"]):
        return "Grammar"
    if "[Proper Noun]" in meaning:
        return "Proper Noun"
    return row['Level']


df['Refined_Level'] = df.apply(refine_level, axis=1)

# --- METRIC CALCULATIONS ---
total_words = df['Frequency'].sum()
unique_words = len(df)
used_once = len(df[df['Frequency'] == 1])
used_once_pct = (used_once / unique_words) * 100

# Kanji Analysis
all_text = "".join(df['Expression'].astype(str))
kanji_list = re.findall(r'[\u4e00-\u9faf]', all_text)
unique_kanji = set(kanji_list)
kanji_freq = Counter(kanji_list)
kanji_once = sum(1 for k in kanji_freq if kanji_freq[k] == 1)

# Reading Analysis
unique_readings = len(df.groupby(['Expression', 'Reading']).size())

# --- CORE DECK COMPARISON CALCULATION ---
core_stats = {"In Core 1.5K": 0,"In Core 2K": 0, "In Core 10K (Extra)": 0, "Anime Only": 0}
anime_vocab = df['Expression'].astype(str).str.strip().tolist()

for word in anime_vocab:
    if word in core_sets["1.5K"]:
        core_stats["In Core 1.5K"] += 1
    elif word in core_sets["2K"]:
        core_stats["In Core 2K"] += 1
    elif word in core_sets["10K"]:
        core_stats["In Core 10K (Extra)"] += 1
    else:
        core_stats["Anime Only"] += 1

# --- THE "USEFUL" DIFFICULTY LOGIC ---
diff_weights = {'Grammar': 5, 'N5': 10, 'N4': 20, 'N3': 40, 'N2': 70, 'N1': 100, 'Proper Noun': 15, 'Unlabeled': 45}
df['Score_Weight'] = df['Refined_Level'].map(diff_weights).fillna(45)
avg_diff_unweighted = df['Score_Weight'].mean()
avg_diff_weighted = (df['Score_Weight'] * df['Frequency']).sum() / total_words
peak_diff = df['Score_Weight'].quantile(0.9)

# --- JSON FILE OUTPUT ---
stats_dict = {
    "Anime": show,
    "Length (total words)": int(total_words),
    "Unique words (dictionary size)": int(unique_words),
    "Unique words (used once)": int(used_once),
    "Unique words (used once %)": f"{used_once_pct:.1f}%",
    "Unique kanji": len(unique_kanji),
    "Unique kanji (used once)": kanji_once,
    "Unique kanji readings": int(unique_readings),
    "Words not found in core Lists":core_stats['Anime Only'],
    "Average Difficulty (Unweighted)": f"{avg_diff_unweighted:.1f}/100",
    "Perceived Difficulty (Weighted)": f"{avg_diff_weighted:.1f}/100",
    "Peak difficulty (90th percentile)": f"{peak_diff:.0f}/100"
}

if not os.path.exists("stats"): os.makedirs("stats")
with open(f"stats/{show}.json", "w", encoding="utf-8") as f:
    json.dump(stats_dict, f, indent=4, ensure_ascii=False)

# --- VISUALIZATION ---
if not os.path.exists("graphs"): os.makedirs("graphs")
level_counts = df['Refined_Level'].value_counts()

# 1. JLPT Level Distribution (Bar)
plt.figure(figsize=(10, 6))
sns.barplot(x=level_counts.index, y=level_counts.values, hue=level_counts.index, palette="viridis", legend=False)
plt.title(f"JLPT Level Distribution (Unique Vocab): {show}")
plt.savefig(f"react-anime/public/graphs/{show}_level_dist_bar.png")

# 2. Episode Difficulty (Stacked Bar)
if 'Episodes' in df.columns:
    df['First_Ep'] = df['Episodes'].str.split(',').str[0]
    ep_vocab = df.groupby(['First_Ep', 'Refined_Level']).size().unstack().fillna(0)
    order = [l for l in ['N1', 'N2', 'N3', 'N4', 'N5', 'Grammar', 'Proper Noun', 'Unlabeled'] if l in ep_vocab.columns]
    ep_vocab = ep_vocab[order]
    fig, ax = plt.subplots(figsize=(12, 7))
    ep_vocab.plot(kind='bar', stacked=True, ax=ax, colormap='viridis')
    plt.title(f"New Vocab Introduced per Episode: {show}")
    plt.tight_layout()
    plt.savefig(f"react-anime/public/graphs/{show}_ep_difficulty.png")

# 3. Core Deck Coverage (Pie)
plt.figure(figsize=(9, 9))
labels_core = list(core_stats.keys())
sizes_core = list(core_stats.values())
colors_core = ['#2ca02c', '#bcbd22', '#1f77b4', '#d62728']  # Green, Yellow, Blue, Red
plt.pie(sizes_core, labels=labels_core, autopct='%1.1f%%', startangle=140, colors=colors_core,
        wedgeprops={'edgecolor': 'white'})
plt.title(f"Core Deck Coverage vs Anime Only: {show}")
plt.savefig(f"react-anime/public/graphs/{show}_core_coverage_pie.png")

print(f"\nExecution complete for {show}.")
print(f"Anime Only words found: {core_stats['Anime Only']}")