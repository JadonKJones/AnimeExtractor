import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
from collections import Counter

# --- SETTINGS ---
csv_folder = "csv/"
core_folder = "core lists/"  # Ensure your .json files are here
output_folder = "graphs/"
plt.rcParams['font.family'] = 'MS Gothic'  # Support for Japanese characters

if not os.path.exists(output_folder):
    os.makedirs(output_folder)


# --- REFINED CATEGORIES FUNCTION ---
def refine_level(row):
    meaning = str(row['Meaning'])
    if any(x in meaning for x in ["Grammar", "auxiliary", "particle", "Copula"]):
        return "Grammar"
    if pd.isna(row['Level']) or row['Level'] == 'Unlabeled':
        return "Unlabeled"
    return row['Level']


# --- LOAD CORE LISTS FROM JSON ---
# Added 1.5K to the sets
core_sets = {"1.5K": set(), "2K": set(), "6K": set(), "10K": set()}

if os.path.exists(core_folder):
    for filename in os.listdir(core_folder):
        path = os.path.join(core_folder, filename)

        if not filename.endswith(".json"):
            continue

        target_key = None
        # Logic to identify the 1.5K file specifically
        if "1.5k" in filename.lower():
            target_key = "1.5K"
        elif "2k" in filename.lower():
            target_key = "2K"
        elif "6k" in filename.lower():
            target_key = "6K"
        elif "10k" in filename.lower():
            target_key = "10K"

        if target_key:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    words = [entry['word'] for entry in data if 'word' in entry]
                    core_sets[target_key].update(words)

                print(f"Loaded {len(core_sets[target_key])} words into {target_key} set from {filename}.")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
else:
    print(f"Warning: Folder '{core_folder}' not found. Core comparison will be skipped.")

# --- DATA AGGREGATION ---
all_shows_data = []
aggregate_counts = Counter()
all_unique_anime_words = set()

csv_files = [f for f in os.listdir(csv_folder) if f.endswith('.csv')]

if not csv_files:
    print(f"No CSV files found in {csv_folder}!")
else:
    for filename in csv_files:
        show_name = filename.replace("_Vocabulary_Full.csv", "").replace(".csv", "")
        file_path = os.path.join(csv_folder, filename)

        print(f"Processing: {show_name}...")

        df = pd.read_csv(file_path)
        df['Refined_Level'] = df.apply(refine_level, axis=1)
        all_unique_anime_words.update(df['Expression'].astype(str).str.strip().tolist())

        counts = df['Refined_Level'].value_counts(normalize=True) * 100
        counts_df = counts.to_frame().transpose()
        counts_df['Anime'] = show_name
        all_shows_data.append(counts_df)

        aggregate_counts.update(df['Refined_Level'].tolist())

    # --- 1. GENERATE MEGA COMPARISON BAR CHART ---
    if all_shows_data:
        mega_df = pd.concat(all_shows_data, axis=0).fillna(0)
        mega_df.set_index('Anime', inplace=True)

        order = [l for l in ['N5', 'N4', 'N3', 'N2', 'N1', 'Grammar', 'Unlabeled'] if l in mega_df.columns]
        mega_df = mega_df[order]

        plt.figure(figsize=(12, 8))
        mega_df.plot(kind='barh', stacked=True, colormap='viridis_r', edgecolor='white', ax=plt.gca())
        plt.title("Comparison of Vocabulary Difficulty Across All Anime", fontsize=15)
        plt.xlabel("Percentage of Total Vocabulary (%)")
        plt.legend(title="Level", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig(f"{output_folder}Mega_Comparison_Bar.png")

    # --- 2. GENERATE MEGA AGGREGATE PIE CHART ---
    if aggregate_counts:
        labels = []
        sizes = []
        for level in order:
            if level in aggregate_counts:
                labels.append(level)
                sizes.append(aggregate_counts[level])

        plt.figure(figsize=(10, 10))
        colors_pie = sns.color_palette("viridis_r", len(labels))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140,
                colors=colors_pie, wedgeprops={'edgecolor': 'white'})
        plt.title("Total Aggregate Vocabulary Composition\n(All Series Combined)", fontsize=16)
        plt.savefig(f"{output_folder}Mega_Aggregate_Pie.png")

    # --- 3. CORE DECK COMPARISON PIE CHART (WITH 1.5K) ---
    if all_unique_anime_words and any(core_sets.values()):
        core_comparison = {
            "In Core 1.5K": 0,
            "In Core 2K": 0,
            "In Core 10K (Extra)": 0,
            "Anime Only": 0
        }

        for word in all_unique_anime_words:
            # Hierarchy check: 1.5K -> 2K -> 10K
            if word in core_sets["1.5K"]:
                core_comparison["In Core 1.5K"] += 1
            elif word in core_sets["2K"]:
                core_comparison["In Core 2K"] += 1
            elif word in core_sets["10K"]:
                core_comparison["In Core 10K (Extra)"] += 1
            else:
                core_comparison["Anime Only"] += 1

        plt.figure(figsize=(10, 10))
        labels_core = list(core_comparison.keys())
        sizes_core = list(core_comparison.values())

        # Green for 1.5K, Lime for 2K, Blue for 10K, Red for Anime Only
        colors_core = ['#2ca02c', '#90ee90', '#1f77b4', '#d62728']

        plt.pie(sizes_core, labels=labels_core, autopct='%1.1f%%', startangle=140,
                colors=colors_core, wedgeprops={'edgecolor': 'white'},
                textprops={'fontsize': 12})

        plt.title("How Much Anime Vocab is covered by Core Decks?\n(Unique Words Across All Series)", fontsize=16)
        plt.savefig(f"{output_folder}Anime_vs_Core_Decks_Pie.png")
        print(f"Generated Core Deck comparison: {core_comparison}")

    print(f"\nSuccess! All graphs saved in {output_folder}")