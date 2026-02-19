import numpy as np

class AIOpsAgent:

    def __init__(self):
        self.history = []
        self.baseline_ready = False
        self.mean = {}
        self.std = {}

    def is_anomaly(self, state, metric, k=2):
        #k stands for standard deviations 
        return state[metric] > self.mean[metric] + k * self.std[metric]


    def update_baseline(self):

        metrics = ["cpu", "latency", "traffic", "error_rate"]

        for metric in metrics:
            values = [h[metric] for h in self.history]

            self.mean[metric] = np.mean(values)
            self.std[metric] = np.std(values) + 1e-6  # avoid divide by zero

        self.baseline_ready = True

        print("✅ Baseline learned:", self.mean)


    def get_action(self, state):

        self.history.append(state)

        # Wait first 10 steps to learn baseline
        if len(self.history) < 10:
            return "do_nothing"

        if not self.baseline_ready:
            self.update_baseline()

        # Automatic anomaly detection
        for metric in ["cpu", "latency", "error_rate"]:
            if state[metric] > self.mean[metric] + 2*self.std[metric]:
                if metric == "error_rate":
                    return "restart_service"
                if metric in ["cpu", "latency"]:
                    return "scale_up"

        return "do_nothing"

