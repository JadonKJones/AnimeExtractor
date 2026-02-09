import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import re
from collections import Counter

# --- THE FIX FOR JAPANESE CHARACTERS ---
plt.rcParams['font.family'] = 'MS Gothic'

show = "Baku Tech! Bakugan"
csv_file = f"csv/{show}_Vocabulary_Full.csv"

if not os.path.exists(csv_file):
    print(f"Error: {csv_file} not found!")
    exit()

# --- LOAD DATA ---
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

# --- THE "USEFUL" DIFFICULTY LOGIC ---
# Using an exponential scale to reflect the actual difficulty gap in JLPT levels
# N5/N4 are basic, N2/N1 are vastly more complex.
diff_weights = {
    'Grammar': 5,
    'N5': 10,
    'N4': 20,
    'N3': 40,
    'N2': 70,
    'N1': 100,
    'Proper Noun': 15,
    'Unlabeled': 45
}

df['Score_Weight'] = df['Refined_Level'].map(diff_weights).fillna(45)

# 1. Unweighted (Dictionary Difficulty) - Average difficulty of the word list
avg_diff_unweighted = df['Score_Weight'].mean()

# 2. Weighted (Perceived Difficulty) - Difficulty based on how often words are spoken
avg_diff_weighted = (df['Score_Weight'] * df['Frequency']).sum() / total_words

peak_diff = df['Score_Weight'].quantile(0.9)

# --- JSON FILE OUTPUT (EVERYTHING INCLUDED) ---
stats_dict = {
    "Anime": show,
    "Length (total words)": int(total_words),
    "Unique words (dictionary size)": int(unique_words),
    "Unique words (used once)": int(used_once),
    "Unique words (used once %)": f"{used_once_pct:.1f}%",
    "Unique kanji": len(unique_kanji),
    "Unique kanji (used once)": kanji_once,
    "Unique kanji readings": int(unique_readings),
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
plt.xlabel("Level")
plt.ylabel("Word Count")
plt.savefig(f"graphs/{show}_level_dist_bar.png")

# 2. Episode Difficulty (Stacked Bar)
if 'Episodes' in df.columns:
    df['First_Ep'] = df['Episodes'].str.split(',').str[0]
    ep_vocab = df.groupby(['First_Ep', 'Refined_Level']).size().unstack().fillna(0)
    order = [l for l in ['N1', 'N2', 'N3', 'N4', 'N5', 'Grammar', 'Proper Noun', 'Unlabeled'] if l in ep_vocab.columns]
    ep_vocab = ep_vocab[order]

    fig, ax = plt.subplots(figsize=(12, 7))
    ep_vocab.plot(kind='bar', stacked=True, ax=ax, colormap='viridis')
    plt.title(f"New Vocab Introduced per Episode: {show}")
    plt.ylabel("Unique Word Count")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(f"graphs/{show}_ep_difficulty.png")

# 3. Level Composition (Pie - Unweighted)
plt.figure(figsize=(9, 9))
plt.pie(level_counts.values, labels=level_counts.index, autopct='%1.1f%%',
        startangle=140, colors=sns.color_palette("viridis", len(level_counts)))
plt.title(f"Vocabulary Composition (Dictionary): {show}")
plt.savefig(f"graphs/{show}_level_pie.png")

print(f"\nExecution complete for {show}.")
print(f"Unweighted Difficulty: {avg_diff_unweighted:.1f}")
print(f"Weighted Difficulty: {avg_diff_weighted:.1f}")