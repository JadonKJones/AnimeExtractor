import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
from collections import Counter

# --- SETTINGS ---
# Adjust 'csv_folder' if your files are in a different directory
csv_folder = "csv/"
output_folder = "graphs/"
plt.rcParams['font.family'] = 'MS Gothic'  # Support for Japanese characters

if not os.path.exists(output_folder):
    os.makedirs(output_folder)


# --- REFINED CATEGORIES FUNCTION ---
def refine_level(row):
    meaning = str(row['Meaning'])
    if any(x in meaning for x in ["Grammar", "auxiliary", "particle", "Copula"]):
        return "Grammar"
    # Keep Unlabeled as Unlabeled
    if pd.isna(row['Level']) or row['Level'] == 'Unlabeled':
        return "Unlabeled"
    return row['Level']


# --- DATA AGGREGATION ---
all_shows_data = []
aggregate_counts = Counter()

# Loop through every CSV in the folder
csv_files = [f for f in os.listdir(csv_folder) if f.endswith('.csv')]

if not csv_files:
    print(f"No CSV files found in {csv_folder}!")
else:
    for filename in csv_files:
        # Clean up show name from filename
        show_name = filename.replace("_Vocabulary_Full.csv", "").replace(".csv", "")
        file_path = os.path.join(csv_folder, filename)

        print(f"Processing: {show_name}...")

        df = pd.read_csv(file_path)
        df['Refined_Level'] = df.apply(refine_level, axis=1)

        # 1. Get stats for the Comparison Bar Chart (Percentages)
        counts = df['Refined_Level'].value_counts(normalize=True) * 100
        counts_df = counts.to_frame().transpose()
        counts_df['Anime'] = show_name
        all_shows_data.append(counts_df)

        # 2. Add to total counts for the Mega Pie Chart (Raw counts)
        aggregate_counts.update(df['Refined_Level'].tolist())

    # --- 1. GENERATE MEGA COMPARISON BAR CHART ---
    mega_df = pd.concat(all_shows_data, axis=0).fillna(0)
    mega_df.set_index('Anime', inplace=True)

    # Logical order for JLPT levels
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
    # Prepare data from the Counter
    labels = []
    sizes = []
    for level in order:
        if level in aggregate_counts:
            labels.append(level)
            sizes.append(aggregate_counts[level])

    plt.figure(figsize=(10, 10))
    # Using the same viridis palette to match your other graphs
    colors = sns.color_palette("viridis_r", len(labels))

    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140,
            colors=colors, wedgeprops={'edgecolor': 'white'})

    plt.title("Total Aggregate Vocabulary Composition\n(All Series Combined)", fontsize=16)
    plt.savefig(f"{output_folder}Mega_Aggregate_Pie.png")

    print(f"\nSuccess! Mega-graphs saved in {output_folder}")