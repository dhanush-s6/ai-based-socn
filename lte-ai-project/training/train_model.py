import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

df = pd.read_csv("training_dataset.csv")

# Example feature selection
features = [
'Th_ENB1','Delay_ENB1','Loss_ENB1','UE_ENB1','RSRP_ENB1','SINR_ENB1','Load_ENB1'
]

X = df[features]

# Generate labels automatically
def label(row):

    if row['Load_ENB1'] > 0.8:
        return 3

    if row['SINR_ENB1'] < 5:
        return 1

    if row['Load_ENB1'] < 0.2:
        return 2

    return 0

y = df.apply(label, axis=1)

X_train,X_test,y_train,y_test = train_test_split(
    X,y,test_size=0.2
)

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=12
)

model.fit(X_train,y_train)

print("Accuracy:",model.score(X_test,y_test))

joblib.dump(model,"models/network_ai.pkl")

print("Model saved")
