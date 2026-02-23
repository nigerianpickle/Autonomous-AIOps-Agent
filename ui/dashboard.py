"""
ui/dashboard.py

Live terminal dashboard using the `rich` library.
Replaces plain print() calls with a real-time updating layout:

┌─────────────────────────────────────────────────────┐
│  AgentOps-Lite  |  Step 12/30  |  Provider: Claude  │
├──────────────────┬──────────────────────────────────┤
│  LIVE METRICS    │  AGENT STATUS                    │
│  CPU      ████   │  ✅ Nominal                      │
│  Memory   ██     │                                  │
│  Latency  ████   │  LAST INCIDENT                   │
│  Err Rate █      │  service_crash (high confidence) │
│  Traffic  ███    │  → restart_service               │
├──────────────────┴──────────────────────────────────┤
│  INCIDENT LOG                                        │
│  Step  Type           Confidence  Action            │
│   11   service_crash  high        restart_service   │
└─────────────────────────────────────────────────────┘
"""

import time
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box


console = Console()


# ------------------------------------------------------------------ #
#  Metric bar helpers                                                 #
# ------------------------------------------------------------------ #

def _metric_bar(value, max_val, width=20):
    """Return a colored progress-style bar string."""
    filled = int((value / max_val) * width)
    filled = max(0, min(width, filled))
    pct = value / max_val

    if pct > 0.85:
        color = "red"
    elif pct > 0.60:
        color = "yellow"
    else:
        color = "green"

    bar  = f"[{color}]{'█' * filled}[/{color}]"
    bar += f"[dim]{'░' * (width - filled)}[/dim]"
    return bar


def _metric_color(value, warn, crit):
    """Return rich color string based on thresholds."""
    if value >= crit:
        return "bold red"
    if value >= warn:
        return "yellow"
    return "green"


# ------------------------------------------------------------------ #
#  Panel builders                                                     #
# ------------------------------------------------------------------ #

def _build_metrics_panel(state):
    cpu  = state["cpu"]
    mem  = state["memory"]
    lat  = state["latency"]
    err  = state["error_rate"]
    traf = state["traffic"]
    fault = state.get("fault") or "None"

    fault_color = "red bold" if state.get("fault") else "dim"

    t = Table.grid(padding=(0, 1))
    t.add_column(style="bold white", width=12)
    t.add_column(width=22)
    t.add_column(width=10)

    t.add_row(
        "CPU",
        _metric_bar(cpu, 100),
        Text(f"{cpu:5.1f}%", style=_metric_color(cpu, 70, 90)),
    )
    t.add_row(
        "Memory",
        _metric_bar(mem, 100),
        Text(f"{mem:5.1f}%", style=_metric_color(mem, 75, 90)),
    )
    t.add_row(
        "Latency",
        _metric_bar(lat, 600, width=20),
        Text(f"{lat:5.0f}ms", style=_metric_color(lat, 200, 400)),
    )
    t.add_row(
        "Error Rate",
        _metric_bar(err, 0.5, width=20),
        Text(f"{err:.4f}", style=_metric_color(err, 0.05, 0.15)),
    )
    t.add_row(
        "Traffic",
        _metric_bar(traf, 2000, width=20),
        Text(f"{traf:6.0f}", style=_metric_color(traf, 800, 1400)),
    )
    t.add_row("", "", "")
    t.add_row(
        "Active Fault",
        Text(fault, style=fault_color),
        "",
    )

    return Panel(t, title="[bold cyan]📊 Live Metrics[/bold cyan]", border_style="cyan")


def _build_status_panel(report, last_incident):
    phase  = report.get("phase", "")
    status = report.get("status", "")

    lines = []

    # Current status
    if phase == "warmup":
        remaining = report.get("warmup_remaining", "?")
        lines.append(Text(f"⏳ Warmup — {remaining} steps left", style="yellow"))
        lines.append(Text("Building baseline...", style="dim"))

    elif status == "nominal":
        lines.append(Text("✅  NOMINAL", style="bold green"))
        lines.append(Text("No anomalies detected", style="dim green"))

    elif status == "anomaly_detected":
        inc_type   = report.get("incident_type", "unknown").upper()
        confidence = report.get("confidence", "?")
        action     = report.get("action", "?")
        reasoning  = report.get("reasoning", "")

        conf_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(confidence, "white")

        lines.append(Text("🚨  INCIDENT DETECTED", style="bold red"))
        lines.append(Text(""))
        lines.append(Text(f"Type:       {inc_type}", style="bold red"))
        lines.append(Text(f"Confidence: ", style="white") + Text(confidence.upper(), style=f"bold {conf_color}"))
        lines.append(Text(f"Action:     {action}", style="bold yellow"))
        lines.append(Text(""))
        lines.append(Text("Reasoning:", style="bold white"))

        # Word-wrap reasoning to ~40 chars
        words = reasoning.split()
        line, col = "", 0
        for w in words:
            if col + len(w) > 42:
                lines.append(Text(f"  {line}", style="dim"))
                line, col = w + " ", len(w) + 1
            else:
                line += w + " "
                col  += len(w) + 1
        if line:
            lines.append(Text(f"  {line}", style="dim"))

    # Last incident summary
    if last_incident and status != "anomaly_detected":
        lines.append(Text(""))
        lines.append(Text("─" * 38, style="dim"))
        lines.append(Text("Last Incident:", style="bold white"))
        lines.append(Text(f"  {last_incident.get('incident_type','?')}  →  {last_incident.get('action','?')}", style="yellow"))
        lines.append(Text(f"  Step {last_incident.get('step','?')}  |  {last_incident.get('confidence','?')} confidence", style="dim"))

    content = "\n".join(str(l) for l in lines)

    # Build renderable using a table so we can join Text objects properly
    grid = Table.grid()
    grid.add_column()
    for l in lines:
        grid.add_row(l)

    return Panel(grid, title="[bold magenta]🤖 Agent Status[/bold magenta]", border_style="magenta")


def _build_incident_table(incident_log):
    t = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold white",
        expand=True,
    )
    t.add_column("Step",       style="dim",        width=6)
    t.add_column("Incident",   style="bold",        width=20)
    t.add_column("Confidence", width=12)
    t.add_column("Action",     style="yellow",      width=18)
    t.add_column("Anomalies",  style="dim",         width=30)

    conf_style = {"high": "bold red", "medium": "yellow", "low": "dim"}

    # Show most recent first, max 8 rows
    for inc in reversed(incident_log[-8:]):
        anomaly_str = ", ".join(
            f"{k}={v}σ" for k, v in inc.get("raw_anomalies", {}).items()
        )
        t.add_row(
            str(inc["step"]),
            inc.get("incident_type", "?"),
            Text(inc.get("confidence", "?"), style=conf_style.get(inc.get("confidence"), "white")),
            inc.get("action", "?"),
            anomaly_str,
        )

    return Panel(t, title="[bold white]📋 Incident Log[/bold white]", border_style="white")


def _build_header(step, total_steps, provider_name, log_path):
    pct   = int((step / total_steps) * 30)
    bar   = "█" * pct + "░" * (30 - pct)
    ts    = datetime.now().strftime("%H:%M:%S")

    t = Table.grid(padding=(0, 2))
    t.add_column(ratio=2)
    t.add_column(ratio=3)
    t.add_column(ratio=2)

    t.add_row(
        Text(f"AgentOps-Lite", style="bold cyan"),
        Text(f"[{bar}] Step {step}/{total_steps}", style="green"),
        Text(f"🕐 {ts}  |  {provider_name}", style="dim"),
    )
    t.add_row(
        Text(""),
        Text(""),
        Text(f"Log: {log_path}", style="dim"),
    )

    return Panel(t, border_style="cyan")


# ------------------------------------------------------------------ #
#  Dashboard class                                                    #
# ------------------------------------------------------------------ #

class Dashboard:
    """
    Wraps a Rich Live context and exposes an `update()` method
    the orchestrator calls every step.
    """

    def __init__(self, total_steps, provider_name, log_path):
        self.total_steps   = total_steps
        self.provider_name = provider_name
        self.log_path      = log_path
        self.last_incident = None
        self._live         = None

    def __enter__(self):
        self._live = Live(
            self._render(0, {}, {}),
            refresh_per_second=4,
            screen=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._live.__exit__(*args)

    def update(self, step, state, report, incident_log):
        if report.get("status") == "anomaly_detected" and incident_log:
            self.last_incident = incident_log[-1]
        self._live.update(self._render(step, state, report, incident_log))
        time.sleep(0.3)   # small pause so human eye can follow

    def _render(self, step, state, report, incident_log=None):
        incident_log = incident_log or []

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="body"),
            Layout(name="footer", size=14),
        )
        layout["body"].split_row(
            Layout(name="metrics"),
            Layout(name="status"),
        )

        layout["header"].update(
            _build_header(step, self.total_steps, self.provider_name, self.log_path)
        )

        if state:
            layout["metrics"].update(_build_metrics_panel(state))
            layout["status"].update(_build_status_panel(report, self.last_incident))
        else:
            layout["metrics"].update(Panel("Starting...", border_style="cyan"))
            layout["status"].update(Panel("Starting...", border_style="magenta"))

        layout["footer"].update(_build_incident_table(incident_log))

        return layout