import json
import os
import time
from datetime import datetime
from environment.faults import inject_fault
from ui import server as ui_server

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich import box

console = Console()


def _metric_bar(value, max_val, width=18):
    filled = max(0, min(width, int((value / max_val) * width)))
    pct = value / max_val
    color = "red" if pct > 0.85 else "yellow" if pct > 0.60 else "green"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (width - filled)}[/dim]"


def _metric_color(value, warn, crit):
    if value >= crit:  return "bold red"
    if value >= warn:  return "yellow"
    return "bright_green"


class Orchestrator:
    """
    Runs the simulation loop and outputs to BOTH:
      - Rich scrolling terminal (full detail every step)
      - Web dashboard  (browser updates live)
    """

    def __init__(self, env, agent, total_steps=50, step_delay=1.5):
        self.env         = env
        self.agent       = agent
        self.total_steps = total_steps
        self.step_delay  = step_delay
        self.log         = []

        os.makedirs("logs", exist_ok=True)
        ts            = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = f"logs/session_{ts}.jsonl"

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        ui_server.push_event("meta", {
            "total_steps": self.total_steps,
            "provider":    self.agent.llm.name,
            "log_path":    self.log_path,
        })

        self._print_header()

        for step in range(1, self.total_steps + 1):

            # 1. Inject fault
            injected = inject_fault(self.env)
            if injected:
                ui_server.push_event("fault", {"fault_type": injected, "step": step})

            # 2. Advance environment
            self.env.step()

            # 3. Observe
            state = self.env.get_state()

            # 4. Agent decides
            action, report = self.agent.get_action(state)

            # 5. Apply action
            self.env.apply_action(action)

            # 6. Push to web dashboard
            ui_server.push_event("step", {
                "step":   step,
                "state":  state,
                "action": action,
                "report": report,
            })

            # 7. Print to terminal (rich, scrolling)
            self._print_step(step, state, report, action, injected)

            # 8. Log to file
            entry = {"step": step, "state": state, "action": action, "report": report}
            self.log.append(entry)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

            time.sleep(self.step_delay)

        self._print_summary()

    # ------------------------------------------------------------------ #
    #  Terminal rendering                                                  #
    # ------------------------------------------------------------------ #

    def _print_header(self):
        console.print()
        console.rule(f"[bold cyan]AgentOps-Lite[/bold cyan]  ·  [dim]{self.agent.llm.name}[/dim]  ·  [dim]{self.total_steps} steps[/dim]")
        console.print(f"  [dim]Dashboard →[/dim] [cyan underline]http://localhost:5000[/cyan underline]")
        console.print(f"  [dim]Log       →[/dim] [dim]{self.log_path}[/dim]")
        console.rule()
        console.print()

    def _print_step(self, step, state, report, action, injected):
        phase  = report.get("phase", "")
        status = report.get("status", "")

        # ── Step divider ──
        progress_pct = step / self.total_steps
        filled = int(progress_pct * 30)
        bar = f"[cyan]{'█' * filled}[/cyan][dim]{'░' * (30 - filled)}[/dim]"
        console.print(f"\n  [bold white]STEP {step:02d}[/bold white]  {bar}  [dim]{step}/{self.total_steps}[/dim]")

        # ── Fault banner ──
        if injected:
            console.print(f"  [bold red on dark_red]  ⚡ FAULT INJECTED: {injected.upper().replace('_',' ')}  [/bold red on dark_red]")

        # ── Metrics table ──
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim", width=12)
        t.add_column(width=20)
        t.add_column(width=10)

        metrics = [
            ("CPU",        state["cpu"],        100,  70,  90,  "%"),
            ("Memory",     state["memory"],      100,  75,  90,  "%"),
            ("Latency",    state["latency"],      600, 200, 400, "ms"),
            ("Error Rate", state["error_rate"],   0.5, 0.05,0.15,""),
            ("Traffic",    state["traffic"],     2000, 800,1400, "req/s"),
        ]
        anomalies = report.get("anomalies", {})

        for name, val, mx, warn, crit, unit in metrics:
            key = name.lower().replace(" ", "_")
            is_anomaly = key in anomalies
            color = _metric_color(val, warn, crit)
            val_str = (
                f"{val:.4f}" if key == "error_rate" else
                f"{val:.0f}"  if key == "latency"   else
                f"{val:.1f}"
            )
            flag = " [bold red]◄ ANOMALY[/bold red]" if is_anomaly else ""
            t.add_row(
                name,
                _metric_bar(val, mx),
                Text(f"{val_str}{unit}", style=color) if not is_anomaly
                else Text(f"{val_str}{unit}", style="bold red"),
            )
            if is_anomaly:
                # Add z-score inline after the row
                t.add_row("", f"[dim]  z-score: {anomalies[key]}σ[/dim]", "")

        console.print(t)

        # ── Active fault tag ──
        if state.get("fault"):
            console.print(f"  [dim]Active fault:[/dim] [red]{state['fault']}[/red]")

        # ── Agent decision ──
        if phase == "warmup":
            remaining = report.get("warmup_remaining", "?")
            console.print(f"  [yellow]⏳ Warmup — {remaining} steps until baseline ready[/yellow]")

        elif status == "nominal":
            console.print(f"  [bright_green]✅  Nominal — no anomalies detected[/bright_green]")

        elif status == "anomaly_detected":
            inc_type   = report.get("incident_type", "unknown")
            confidence = report.get("confidence", "?")
            reasoning  = report.get("reasoning", "")
            action_r   = report.get("action_reasoning", "")

            conf_color = {"high": "bold red", "medium": "yellow", "low": "dim"}.get(confidence, "white")

            console.print(f"  [bold red]🚨 INCIDENT:[/bold red] [bold white]{inc_type.upper().replace('_',' ')}[/bold white]  [dim]confidence:[/dim] [{conf_color}]{confidence.upper()}[/{conf_color}]")
            console.print(f"  [bold yellow]🛠  Action:[/bold yellow]  [yellow]{action}[/yellow]")
            console.print()
            console.print(f"  [dim]Reasoning:[/dim]")
            # Word-wrap reasoning at 72 chars
            words = reasoning.split()
            line = "    "
            for w in words:
                if len(line) + len(w) > 74:
                    console.print(f"[dim]{line}[/dim]")
                    line = "    " + w + " "
                else:
                    line += w + " "
            if line.strip():
                console.print(f"[dim]{line}[/dim]")

            console.print(f"  [dim]→ {action_r}[/dim]")

    def _print_summary(self):
        incidents = self.agent.incident_log
        types   = {}
        actions = {}
        for inc in incidents:
            t = inc.get("incident_type", "?")
            a = inc.get("action", "?")
            types[t]   = types.get(t, 0) + 1
            actions[a] = actions.get(a, 0) + 1

        console.print()
        console.rule("[bold cyan]Run Complete[/bold cyan]")

        summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        summary.add_column(style="bold white", width=26)
        summary.add_column(style="cyan")
        summary.add_row("Total steps",        str(self.total_steps))
        summary.add_row("Incidents detected", str(len(incidents)))
        summary.add_row("Incident types",     str(types))
        summary.add_row("Actions taken",      str(actions))
        summary.add_row("Session log",        self.log_path)
        summary.add_row("Dashboard",          "http://localhost:5000")
        console.print(summary)
        console.rule()