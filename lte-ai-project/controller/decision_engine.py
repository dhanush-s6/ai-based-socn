import joblib
import numpy as np

model = joblib.load("models/network_ai.pkl")

def predict_action(network_state):

    data = np.array(network_state).reshape(1,-1)

    action = model.predict(data)[0]

    return action
