from environment.faults import inject_fault

class Orchestrator:

    def __init__(self, env, agent):
        self.env = env
        self.agent = agent

    def run(self, steps=50):

        for step in range(steps):
            print(f"\n--- Step {step+1} ---")

            # Inject random fault
            inject_fault(self.env)

            # Update system state
            self.env.step()

            # Observe
            state = self.env.get_state()
            print("State:", state)

            # Agent decides
            action = self.agent.get_action(state)
            print("Action:", action)

            # Apply action
            self.env.apply_action(action)
