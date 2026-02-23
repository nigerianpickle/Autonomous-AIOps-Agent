from agent.llm_provider import select_provider
from agent.agent import AIOpsAgent
from environment.simulator import ApplicationSimulator
from orchestrator.orchestrator import Orchestrator
from ui import server as ui_server

if __name__ == "__main__":
    # 1. Provider setup
    provider = select_provider()

    # 2. Start web dashboard (opens browser automatically)
    port = ui_server.start(port=5000, open_browser=True)
    print(f"\n  ✅ Dashboard running at http://localhost:{port}")

    # 3. Wire simulation
    env          = ApplicationSimulator()
    agent        = AIOpsAgent(llm_provider=provider, warmup_steps=10, z_threshold=2.0)
    orchestrator = Orchestrator(env, agent, total_steps=50, step_delay=1.5)

    # 4. Run — streams events live to browser
    orchestrator.run()