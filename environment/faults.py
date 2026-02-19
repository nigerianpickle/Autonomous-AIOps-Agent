import random

def inject_fault(env):
    if random.random() < 0.1:  # 10% chance per step
        fault_type = random.choice(["traffic_spike", "service_crash"])
        env.active_fault = fault_type

        if fault_type == "traffic_spike":
            env.traffic += 500
            env.cpu += 30
            env.latency += 100

        elif fault_type == "service_crash":
            env.error_rate += 0.2
            env.latency += 200
