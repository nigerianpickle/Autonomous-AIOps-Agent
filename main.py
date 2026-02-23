from agent.llm_provider import select_provider
from agent.agent import AIOpsAgent
from environment.simulator import ApplicationSimulator
from orchestrator.orchestrator import Orchestrator

if __name__ == "__main__":
    # 1. User picks their LLM provider + API key
    provider = select_provider()

    # 2. Wire everything together
    env          = ApplicationSimulator()
    agent        = AIOpsAgent(llm_provider=provider, warmup_steps=10, z_threshold=2.0)
    orchestrator = Orchestrator(env, agent)

    # 3. Run
    orchestrator.run(steps=30)