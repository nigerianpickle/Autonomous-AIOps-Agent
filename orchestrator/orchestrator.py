import json
import os
from datetime import datetime
from environment.faults import inject_fault
from ui.dashboard import Dashboard


class Orchestrator:
    """
    Controls the closed-loop simulation and drives the live dashboard.
    inject faults → step environment → agent observes → agent acts → update UI → repeat
    """

    def __init__(self, env, agent):
        self.env   = env
        self.agent = agent
        self.log   = []

        os.makedirs("logs", exist_ok=True)
        timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = f"logs/session_{timestamp}.jsonl"

    def run(self, steps=50):
        provider_name = self.agent.llm.name

        with Dashboard(steps, provider_name, self.log_path) as dash:
            for step in range(steps):

                # 1. Inject random fault
                inject_fault(self.env)

                # 2. Advance environment
                self.env.step()

                # 3. Observe
                state = self.env.get_state()

                # 4. Agent decides
                action, report = self.agent.get_action(state)

                # 5. Apply action
                self.env.apply_action(action)

                # 6. Update dashboard
                dash.update(step + 1, state, report, self.agent.incident_log)

                # 7. Log to file
                entry = {"step": step + 1, "state": state, "action": action, "report": report}
                self.log.append(entry)
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")

        # Final summary after dashboard closes
        self._print_summary(steps)

    def _print_summary(self, steps):
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        incidents = self.agent.incident_log

        action_counts   = {}
        incident_types  = {}
        for inc in incidents:
            a = inc.get("action", "unknown")
            t = inc.get("incident_type", "unknown")
            action_counts[a]  = action_counts.get(a, 0) + 1
            incident_types[t] = incident_types.get(t, 0) + 1

        console.print()
        console.rule("[bold cyan]Run Complete — Final Summary[/bold cyan]")

        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column(style="bold white", width=28)
        t.add_column(style="cyan")
        t.add_row("Total steps",        str(steps))
        t.add_row("Incidents detected", str(len(incidents)))
        t.add_row("Incident types",     str(incident_types))
        t.add_row("Actions taken",      str(action_counts))
        t.add_row("Session log",        self.log_path)
        console.print(t)
        console.rule()