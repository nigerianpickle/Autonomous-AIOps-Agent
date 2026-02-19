import random

class ApplicationSimulator:
    def __init__(self):
        self.cpu = 40
        self.memory = 50
        self.latency = 100
        self.error_rate = 0.01
        self.traffic = 300
        self.active_fault = None

    def step(self):
        # Normal fluctuations
        self.cpu += random.uniform(-2, 2)
        self.memory += random.uniform(-2, 2)
        self.latency += random.uniform(-5, 5)
        self.traffic += random.uniform(-20, 20)

        # Keep values realistic
        self.cpu = max(0, min(100, self.cpu))
        self.memory = max(0, min(100, self.memory))
        self.latency = max(50, self.latency)
        self.error_rate = max(0, self.error_rate)

    def get_state(self):
        return {
            "cpu": round(self.cpu, 2),
            "memory": round(self.memory, 2),
            "latency": round(self.latency, 2),
            "error_rate": round(self.error_rate, 4),
            "traffic": round(self.traffic, 2),
            "fault": self.active_fault
        }

    def apply_action(self, action):
        if action == "restart_service":
            self.error_rate *= 0.3
            self.latency *= 0.8
            self.active_fault = None

        elif action == "scale_up":
            self.cpu *= 0.8
            self.latency *= 0.85
            self.active_fault = None
