import joblib
import numpy as np

# load trained model
model = joblib.load("models/network_ai.pkl")

# Example network state
# (Throughput, Delay, Loss, UE count, RSRP, SINR, Load)

state = [
    35,    # throughput Mbps
    10,    # delay ms
    0.2,   # packet loss %
    25,    # UE count
    -85,   # RSRP
    12,    # SINR
    0.5    # load
]

X = np.array(state).reshape(1,-1)

prediction = model.predict(X)[0]

print("Network state:", state)
print("AI predicted action:", prediction)
