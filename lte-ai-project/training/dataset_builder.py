import pandas as pd
import glob

files = glob.glob("dataset/*.csv")

dataframes = []

for file in files:
    df = pd.read_csv(file)
    dataframes.append(df)

dataset = pd.concat(dataframes, ignore_index=True)

dataset.to_csv("data/training_dataset.csv", index=False)

print("Dataset size:", dataset.shape)
