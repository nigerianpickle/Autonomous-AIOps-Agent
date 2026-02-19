from environment.simulator import ApplicationSimulator
from agent.agent import AIOpsAgent
from orchestrator.orchestrator import Orchestrator

if __name__ == "__main__":
    env = ApplicationSimulator()
    agent = AIOpsAgent()
    orchestrator = Orchestrator(env, agent)

    orchestrator.run(steps=30)
