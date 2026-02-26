import numpy as np
import json
from collections import deque


class AIOpsAgent:
    """
    Autonomous AIOps Agent combining:
    - Statistical anomaly detection (z-score / rolling baseline)  [ML layer]
    - LLM-powered diagnosis & action reasoning                    [AI layer]

    The LLM provider is injected at construction time, so the agent
    works with Anthropic, OpenAI, Ollama, or any future provider.
    """

    METRICS = ["cpu", "latency", "error_rate", "traffic", "memory"]

    def __init__(self, llm_provider, warmup_steps=10, window_size=30, z_threshold=2.0):
        """
        Initializes the AIOps agent.

        Parameters:
            llm_provider  : The LLM backend to use for diagnosis (Anthropic, OpenAI, or Ollama).
            warmup_steps  : Number of steps the agent observes before making any decisions.
                            During this phase it collects data to build an initial baseline.
                            Default is 10.
            window_size   : How many recent steps to include when computing the rolling baseline.
                            Older observations beyond this window are discarded automatically.
                            Default is 30.
            z_threshold   : How many standard deviations above the baseline mean a metric must
                            reach before it is flagged as anomalous. Based on the statistical
                            property that 95% of normal values fall within 2 standard deviations.
                            Default is 2.0.
        """
        self.llm           = llm_provider
        self.warmup_steps  = warmup_steps
        self.window_size   = window_size
        self.z_threshold   = z_threshold

        #Create a queue for each metric
        self.windows        = {m: deque(maxlen=window_size) for m in self.METRICS}
        self.step_count     = 0
        self.baseline_ready = False
        self.mean           = {}
        self.std            = {}

        self.recent_states  = deque(maxlen=5)
        self.incident_log   = []


    def _update_baseline(self):
        """
        Recomputes the rolling mean and standard deviation for each metric
        using the current observation window.

        Called every step after warmup. Because the window has a fixed max size,
        older observations automatically drop off as new ones come in, keeping
        the baseline representative of recent system behaviour rather than
        the entire run history.

        A small epsilon (1e-6) is added to std to prevent division by zero
        in cases where a metric is temporarily perfectly flat.
        """


        #Update mean and std for each metric
        for metric in self.METRICS:
            if len(self.windows[metric]) >= 2:
                values = list(self.windows[metric])
                self.mean[metric] = np.mean(values)
                self.std[metric]  = np.std(values) + 1e-6 #suggested by ai
        self.baseline_ready = True

    # ------------------------------------------------------------------ #
    #  Anomaly Detection                                                   #
    # ------------------------------------------------------------------ #

    def _detect_anomalies(self, state):
        anomalies = {}
        for metric in self.METRICS:
            if metric in self.mean:
                z = (state[metric] - self.mean[metric]) / self.std[metric]
                if z > self.z_threshold:
                    anomalies[metric] = round(float(z), 2)
        return anomalies

    # ------------------------------------------------------------------ #
    #  LLM Diagnosis                                                       #
    # ------------------------------------------------------------------ #

    def _build_prompt(self, state, anomalies):
        history_lines = [
            f"  t-{len(self.recent_states)-i}: cpu={s['cpu']}% | "
            f"latency={s['latency']}ms | error_rate={s['error_rate']} | "
            f"traffic={s['traffic']} | fault={s.get('fault')}"
            for i, s in enumerate(self.recent_states)
        ]
        baseline_summary = {
            m: {"mean": round(self.mean[m], 2), "std": round(self.std[m], 2)}
            for m in self.mean
        }
        return f"""You are an AIOps agent monitoring a cloud application.
Your job is to diagnose the current incident and recommend a remediation action.

## Current System State
- CPU:        {state['cpu']}%
- Memory:     {state['memory']}%
- Latency:    {state['latency']}ms
- Error Rate: {state['error_rate']}
- Traffic:    {state['traffic']} req/s
- Active Fault Label: {state.get('fault', 'unknown')}

## Anomalous Metrics (z-scores above threshold)
{json.dumps(anomalies, indent=2)}

## Learned Baseline (normal behavior)
{json.dumps(baseline_summary, indent=2)}

## Recent History
{chr(10).join(history_lines) if history_lines else "  No history yet."}

## Available Actions
- "restart_service" : Best for high error rates, crashes.
- "scale_up"        : Best for CPU overload, traffic spikes, high latency.
- "do_nothing"      : Best for transient blips or self-healing in progress.

Respond ONLY with valid JSON in this exact format:
{{
  "incident_type": "<traffic_spike | service_crash | cpu_overload | memory_pressure | latency_spike | cascading_failure | unknown>",
  "confidence": "<high | medium | low>",
  "reasoning": "<2-3 sentences referencing specific metric values>",
  "action": "<restart_service | scale_up | do_nothing>",
  "action_reasoning": "<one sentence explaining the action choice>"
}}"""

    def _diagnose_with_llm(self, state, anomalies):
        prompt = self._build_prompt(state, anomalies)
        raw    = self.llm.diagnose(prompt)

        # Strip markdown fences if the model wraps output in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return json.loads(raw.strip())

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    def get_action(self, state):
        self.step_count += 1

        for metric in self.METRICS:
            if metric in state:
                self.windows[metric].append(state[metric])

        self.recent_states.append(state)

        if self.step_count >= self.warmup_steps:
            self._update_baseline()

        if not self.baseline_ready:
            return "do_nothing", {
                "phase": "warmup",
                "step": self.step_count,
                "warmup_remaining": self.warmup_steps - self.step_count,
            }

        anomalies = self._detect_anomalies(state)

        if not anomalies:
            return "do_nothing", {
                "phase": "operational",
                "status": "nominal",
                "anomalies": {},
            }

        print(f"  🤖 Anomaly detected — consulting {self.llm.name} for diagnosis...")
        try:
            diagnosis = self._diagnose_with_llm(state, anomalies)
        except Exception as e:
            print(f"  ⚠️  LLM call failed ({e}), using fallback rule.")
            action = "restart_service" if "error_rate" in anomalies else "scale_up"
            diagnosis = {
                "incident_type":    "unknown",
                "confidence":       "low",
                "reasoning":        "LLM unavailable — fallback rule applied.",
                "action":           action,
                "action_reasoning": "Fallback heuristic.",
            }

        action = diagnosis.get("action", "do_nothing")
        report = {
            "phase":    "operational",
            "status":   "anomaly_detected",
            "anomalies": anomalies,
            **diagnosis,
        }

        self.incident_log.append({
            "step": self.step_count,
            **diagnosis,
            "raw_anomalies": anomalies,
        })

        return action, report