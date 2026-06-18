import pandas as pd
from datasets import load_dataset

print("Downloading fka/awesome-chatgpt-prompts dataset...")
ds = load_dataset("fka/awesome-chatgpt-prompts")

data = []
for row in ds['train']:
    prompt_text = row['prompt']
    
    # Classify as heavy if it's explicitly for devs, or if the prompt is very long/complex
    # Otherwise classify as light
    is_heavy = row.get('for_devs', False) or len(prompt_text) > 300
    label = "heavy" if is_heavy else "light"
    
    data.append({"text": prompt_text, "label": label})

df = pd.DataFrame(data)

# Let's shuffle it to ensure good training mix
df = df.sample(frac=1).reset_index(drop=True)

df.to_csv("data/prompts.csv", index=False)
print(f"Saved {len(df)} new prompts to data/prompts.csv")
print("Label distribution:")
print(df['label'].value_counts())
