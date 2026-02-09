import json
import re
import os


def parse_kaishi_to_json_flexible(input_file, output_file):
    core_data = []

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip metadata and the welcome card
            if line.startswith('#') or not line or "Welcome" in line:
                continue

            # --- THE FLEXIBLE SPLIT ---
            # This regex splits the line whenever it sees a TAB (\t)
            # OR two or more spaces (\s{2,})
            parts = re.split(r'\t|\s{2,}', line)

            # Clean up empty strings from the list caused by multiple separators
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) >= 2:
                # In Kaishi, usually:
                # parts[0] = Kanji (Word)
                # parts[1] = Example Sentence
                # parts[2] = Furigana/Reading/Definition Block

                word = parts[0]
                definition = None

                # Look through the remaining parts for the first one containing English
                for p in parts[1:]:
                    # Remove any Anki/HTML tags first so we can check the text
                    clean_text = re.sub(r'<[^>]+>', '', p)

                    # If it has English letters and isn't just a "Note:" label
                    if re.search(r'[a-zA-Z]', clean_text) and not clean_text.startswith("Note:"):
                        definition = clean_text
                        break

                if word and definition:
                    core_data.append({
                        "word": word.split(' ')[0],
                        "definition": definition
                    })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(core_data, f, ensure_ascii=False, indent=4)

    print(f"Success! Processed {len(core_data)} words into {output_file}")


# Usage
parse_kaishi_to_json_flexible('kaishi_1.5k.txt', '1.5K.json')