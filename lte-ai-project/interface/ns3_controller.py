from decision_engine import predict_action
import pandas as pd

data = pd.read_csv("latest_kpi.csv")

latest = data.iloc[-1]

state = [
latest['Th_ENB1'],
latest['Delay_ENB1'],
latest['Loss_ENB1'],
latest['UE_ENB1'],
latest['RSRP_ENB1'],
latest['SINR_ENB1'],
latest['Load_ENB1']
]

action = predict_action(state)

print("AI decided:",action)