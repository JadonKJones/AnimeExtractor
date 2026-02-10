import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import re
from collections import Counter

plt.rcParams['font.family'] = 'MS Gothic'

csv_folder = "csv/"
core_folder = "core lists/"
if not os.path.exists("react-anime/src/stats"): os.makedirs("react-anime/src/stats")
if not os.path.exists("react-anime/public/graphs"): os.makedirs("react-anime/public/graphs")


core_sets = {}
if os.path.exists(core_folder):
    for filename in os.listdir(core_folder):
        if not filename.endswith(".json"):
            continue

        target_key = filename[:-5]
        try:
            with open(os.path.join(core_folder, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                words = [str(entry['word']).strip() for entry in data if 'word' in entry]
                core_sets[target_key] = set(words)
                print(f"Loaded {len(words)} words into core_sets['{target_key}']")
        except Exception as e:
            print(f"Error loading {filename}: {e}")


if not os.path.exists(csv_folder):
    print(f"Error: {csv_folder} folder not found!")
    exit()

for csv_filename in os.listdir(csv_folder):
    if not csv_filename.endswith(".csv"):
        continue

    show = re.sub(r'_Vocabulary_Full.*', '', csv_filename).replace('.csv', '')
    csv_path = os.path.join(csv_folder, csv_filename)

    print(f"\n--- Processing: {show} ---")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error loading {csv_filename}: {e}")
        continue


    def refine_level(row):
        meaning = str(row['Meaning'])
        if any(x in meaning for x in ["Grammar", "auxiliary", "particle", "Copula"]):
            return "Grammar"
        if "[Proper Noun]" in meaning:
            return "Proper Noun"
        return row['Level']


    df['Refined_Level'] = df.apply(refine_level, axis=1)

    total_words = df['Frequency'].sum()
    unique_words = len(df)
    used_once = len(df[df['Frequency'] == 1])
    used_once_pct = (used_once / unique_words) * 100
    all_text = "".join(df['Expression'].astype(str))
    kanji_list = re.findall(r'[\u4e00-\u9faf]', all_text)
    unique_kanji = set(kanji_list)
    kanji_freq = Counter(kanji_list)
    kanji_once = sum(1 for k in kanji_freq if kanji_freq[k] == 1)

    unique_readings = len(df.groupby(['Expression', 'Reading']).size())

    core_stats = {f"In_Core_{k}": 0 for k in core_sets.keys()}
    core_stats["Real_Life_Japanese"] = 0

    anime_vocab = df['Expression'].astype(str).str.strip().tolist()

    for word in anime_vocab:
        found = False
        for key in sorted(core_sets.keys()):
            if word in core_sets[key]:
                core_stats[f"In_Core_{key}"] += 1
                found = True
                break

        if not found:
            core_stats["Real_Life_Japanese"] += 1

    diff_weights = {'Grammar': 5, 'N5': 10, 'N4': 20, 'N3': 40, 'N2': 70, 'N1': 100, 'Proper Noun': 15,
                    'Real_Life_Japanese': 45}
    df['Score_Weight'] = df['Refined_Level'].map(diff_weights).fillna(45)
    avg_diff_unweighted = df['Score_Weight'].mean()
    avg_diff_weighted = (df['Score_Weight'] * df['Frequency']).sum() / total_words
    peak_diff = df['Score_Weight'].quantile(0.9)

    stats_dict = {
        "Anime": show,
        "Length_total_words": int(total_words),
        "Unique_words_dictionary_size": int(unique_words),
        "Unique_words_used_once": int(used_once),
        "Unique_words_used_once_%": f"{used_once_pct:.1f}%",
        "Unique_kanji": len(unique_kanji),
        "Unique_kanji_used_once": kanji_once,
        "Unique_kanji_readings": int(unique_readings),
        "Words_not_found_in_core_Lists": core_stats.get('Real_Life_Japanese', 0),
        "Average_Difficulty_Unweighted": int(avg_diff_unweighted),
        "Perceived_Difficulty_Weighted": int(avg_diff_weighted),
        "Peak_difficulty_90th_percentile": int(peak_diff)
    }

    for key, val in core_stats.items():
        stats_dict[key] = val

    with open(f"react-anime/src/stats/{show}.json", "w", encoding="utf-8") as f:
        json.dump(stats_dict, f, indent=4, ensure_ascii=False)

    level_counts = df['Refined_Level'].value_counts()

    plt.figure(figsize=(10, 6))
    sns.barplot(x=level_counts.index, y=level_counts.values, hue=level_counts.index, palette="viridis", legend=False)
    plt.title(f"JLPT Level Distribution (Unique Vocab): {show}")
    plt.savefig(f"graphs/{show}_level_dist_bar.png")
    plt.close()

    if 'Episodes' in df.columns:
        df['First_Ep'] = df['Episodes'].str.split(',').str[0]
        ep_vocab = df.groupby(['First_Ep', 'Refined_Level']).size().unstack().fillna(0)
        order = [l for l in ['N1', 'N2', 'N3', 'N4', 'N5', 'Grammar', 'Proper Noun', 'Real_Life_Japanese'] if
                 l in ep_vocab.columns]
        ep_vocab = ep_vocab[order]
        fig, ax = plt.subplots(figsize=(12, 7))
        ep_vocab.plot(kind='bar', stacked=True, ax=ax, colormap='viridis')
        plt.title(f"New Vocab Introduced per Episode: {show}")
        plt.tight_layout()
        plt.savefig(f"graphs/{show}_ep_difficulty.png")
        plt.close()

    plt.figure(figsize=(9, 9))
    labels_core = list(core_stats.keys())
    sizes_core = list(core_stats.values())
    colors_core = sns.color_palette("husl", len(labels_core))
    plt.pie(sizes_core, labels=labels_core, autopct='%1.1f%%', startangle=140, colors=colors_core,
            wedgeprops={'edgecolor': 'white'})
    plt.title(f"Core Deck Coverage vs Real_Life_Japanese: {show}")
    plt.savefig(f"graphs/{show}_core_coverage_pie.png")
    plt.close()

    print(f"Execution complete for {show}.")

print("\nAll files in folder processed successfully.")