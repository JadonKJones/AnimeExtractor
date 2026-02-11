import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import re
from collections import Counter

# --- CONFIGURATION ---
plt.rcParams['font.family'] = 'MS Gothic'
csv_folder = "react-anime/public/csv/"
core_folder = "core lists/"
output_stats_folder = "stats"
output_graphs_folder = "react-anime/public/graphs"

# Ensure output directories exist
for folder in [output_stats_folder, output_graphs_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- LOAD CORE LISTS ONCE ---
core_sets = {"1.5K": set(), "2K": set(), "10K": set()}
if os.path.exists(core_folder):
    for filename in os.listdir(core_folder):
        if not filename.endswith(".json"): continue
        target_key = filename[:-5]
        if target_key in core_sets:
            try:
                with open(os.path.join(core_folder, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    words = [entry['word'] for entry in data if 'word' in entry]
                    core_sets[target_key].update(words)
            except Exception as e:
                print(f"Error loading {filename}: {e}")


def refine_level(row):
    meaning = str(row['Meaning'])
    if any(x in meaning for x in ["Grammar", "auxiliary", "particle", "Copula"]):
        return "Grammar"
    if "[Proper Noun]" in meaning:
        return "Proper Noun"
    return row['Level']


# --- MAIN LOOP: PROCESS EACH CSV ---
for csv_filename in os.listdir(csv_folder):
    if not csv_filename.endswith("_Vocabulary_Full.csv"):
        continue

    # Extract Anime Name from filename
    show = csv_filename.replace("_Vocabulary_Full.csv", "")
    csv_path = os.path.join(csv_folder, csv_filename)

    print(f"Processing: {show}...")

    try:
        df = pd.read_csv(csv_path)
        df['Refined_Level'] = df.apply(refine_level, axis=1)

        # --- METRIC CALCULATIONS ---
        total_words = df['Frequency'].sum()
        unique_words = len(df)
        used_once = len(df[df['Frequency'] == 1])
        used_once_pct = (used_once / unique_words) * 100 if unique_words > 0 else 0

        # Kanji Analysis
        all_text = "".join(df['Expression'].astype(str))
        kanji_list = re.findall(r'[\u4e00-\u9faf]', all_text)
        unique_kanji = set(kanji_list)
        kanji_freq = Counter(kanji_list)
        kanji_once = sum(1 for k in kanji_freq if kanji_freq[k] == 1)

        # Reading Analysis
        unique_readings = len(df.groupby(['Expression', 'Reading']).size())

        # Core Deck Comparison
        core_stats = {"In_Core_1.5K": 0, "In_Core_2K": 0, "In_Core_10K": 0, "Real_Life_Japanese": 0}
        anime_vocab = df['Expression'].astype(str).str.strip().tolist()

        for word in anime_vocab:
            if word in core_sets["1.5K"]:
                core_stats["In_Core_1.5K"] += 1
            elif word in core_sets["2K"]:
                core_stats["In_Core_2K"] += 1
            elif word in core_sets["10K"]:
                core_stats["In_Core_10K"] += 1
            else:
                core_stats["Real_Life_Japanese"] += 1

        # Difficulty Logic
        diff_weights = {'Grammar': 5, 'N5': 10, 'N4': 20, 'N3': 40, 'N2': 70, 'N1': 100, 'Proper Noun': 15,
                        'Unlabeled': 45}
        df['Score_Weight'] = df['Refined_Level'].map(diff_weights).fillna(45)
        avg_diff_unweighted = df['Score_Weight'].mean()
        avg_diff_weighted = (df['Score_Weight'] * df['Frequency']).sum() / total_words if total_words > 0 else 0
        peak_diff = df['Score_Weight'].quantile(0.9)

        # --- GENERATE JSON ---
        stats_dict = {
            "Anime": show,
            "Length_total_words": int(total_words),
            "Unique_words_dictionary_size": int(unique_words),
            "Unique_words_used_once": int(used_once),
            "Unique_words_used_once_%": f"{used_once_pct:.1f}%",
            "Unique_kanji": len(unique_kanji),
            "Unique_kanji_used_once": kanji_once,
            "Unique_kanji_readings": int(unique_readings),
            "Words_not_found_in_core_Lists": core_stats['Real_Life_Japanese'],
            "Average_Difficulty_Unweighted": int(round(avg_diff_unweighted)),
            "Perceived_Difficulty_Weighted": int(round(avg_diff_weighted)),
            "Peak_difficulty_90th_percentile": int(round(peak_diff)),
            "In_Core_1.5K": core_stats["In_Core_1.5K"],
            "In_Core_10K": core_stats["In_Core_10K"],
            "In_Core_2K": core_stats["In_Core_2K"],
            "Real_Life_Japanese": core_stats["Real_Life_Japanese"]
        }

        with open(os.path.join(output_stats_folder, f"{show}.json"), "w", encoding="utf-8") as f:
            json.dump(stats_dict, f, indent=4, ensure_ascii=False)

        # --- VISUALIZATION ---
        level_counts = df['Refined_Level'].value_counts()

        # 1. JLPT Level Distribution
        plt.figure(figsize=(10, 6))
        sns.barplot(x=level_counts.index, y=level_counts.values, hue=level_counts.index, palette="viridis",
                    legend=False)
        plt.title(f"JLPT Level Distribution: {show}")
        plt.savefig(os.path.join(output_graphs_folder, f"{show}_level_dist_bar.png"))
        plt.close()  # Close figure to free memory during loop

        # 2. Episode Difficulty
        if 'Episodes' in df.columns:
            df['First_Ep'] = df['Episodes'].str.split(',').str[0]
            ep_vocab = df.groupby(['First_Ep', 'Refined_Level']).size().unstack().fillna(0)
            order = [l for l in ['N1', 'N2', 'N3', 'N4', 'N5', 'Grammar', 'Proper Noun', 'Unlabeled'] if
                     l in ep_vocab.columns]
            ep_vocab = ep_vocab[order]
            fig, ax = plt.subplots(figsize=(12, 7))
            ep_vocab.plot(kind='bar', stacked=True, ax=ax, colormap='viridis')
            plt.title(f"New Vocab Introduced per Episode: {show}")
            plt.tight_layout()
            plt.savefig(os.path.join(output_graphs_folder, f"{show}_ep_difficulty.png"))
            plt.close()

        # 3. Core Deck Coverage
        plt.figure(figsize=(9, 9))
        plt.pie(core_stats.values(), labels=core_stats.keys(), autopct='%1.1f%%', startangle=140,
                colors=['#2ca02c', '#bcbd22', '#1f77b4', '#d62728'], wedgeprops={'edgecolor': 'white'})
        plt.title(f"Core Deck Coverage: {show}")
        plt.savefig(os.path.join(output_graphs_folder, f"{show}_core_coverage_pie.png"))
        plt.close()

    except Exception as e:
        print(f"Failed to process {show}: {e}")

print("\nAll files processed.")