# AgentOps-Lite

### Autonomous AI-Driven AIOps Agent

**Observe · Detect · Diagnose · Remediate**

Built for FCT Summer Student Program -- AI Technical Challenge (2026)

------------------------------------------------------------------------

# 1. Overview

**AgentOps-Lite** is a lightweight autonomous AIOps system that
demonstrates the full incident lifecycle:

> **Observe → Detect → Diagnose → Remediate**

It combines:

-   Statistical anomaly detection (unsupervised ML)
-   LLM-powered reasoning and root-cause analysis
-   Automated remediation actions
-   A closed-loop autonomous agent architecture
-   Real-time web dashboard and terminal interface

The system simulates a cloud application environment, injects
operational faults, detects abnormal behavior, reasons about root cause
using a large language model, and automatically applies remediation ---
all without human intervention.

------------------------------------------------------------------------

# 2. Problem Statement

Traditional monitoring systems rely on static thresholds:

-   Alert if CPU \> 80%
-   Alert if latency \> 500ms
-   Alert if error rate \> 5%

This approach is:

-   Hardcoded and brittle
-   Context-blind across applications
-   Noisy (high false positives)
-   Unable to detect gradual degradation

Modern cloud systems are dynamic. "Normal" behavior changes over time.

**AgentOps-Lite addresses this by learning what normal looks like,
detecting deviations statistically, and reasoning about incidents
autonomously.**

------------------------------------------------------------------------

# 3. System Architecture

AgentOps-Lite is designed as a closed-loop autonomous agent system.

## Core Components

**Environment** - Simulated cloud app - CPU, Memory, Latency, Error
Rate, Traffic - Realistic metric correlation (memory pressure increases
latency) - Probabilistic fault injection

**AIOpsAgent** - Layer 1: Statistical anomaly detection - Layer 2:
LLM-based diagnosis - Graceful fallback if LLM fails

**Orchestrator** - Runs 50-step simulation loop - Controls
agent-environment interaction - Streams events to UI - Writes `.jsonl`
logs

**UI Layer** - Flask + Server-Sent Events (SSE) - Live metric
dashboard - LLM reasoning feed - Incident timeline - Simultaneous rich
terminal UI


------------------------------------------------------------------------

# 4. AI Techniques & Intelligent Logic

## Layer 1:Unsupervised Anomaly Detection

Each metric maintains a rolling window:

-   `window_size = 30`
-   `warmup_steps = 10`
-   Rolling mean + standard deviation

Anomalies detected via **z-score**:

    z = (value - rolling_mean) / rolling_std

If:

    z > 2.0

→ Statistically significant deviation (\~top 2.5%)

### Why This Matters

-   No hardcoded thresholds
-   Adaptive to system behavior
-   Online learning (baseline evolves every step)
-   Works for any metric without tuning


------------------------------------------------------------------------

## Layer 2: LLM-Powered Diagnosis

The LLM is only invoked when Layer 1 confirms an anomaly.

This reduces: - Cost - Latency - Unnecessary inference

### Prompt Context Includes:

-   Current metric values
-   Anomalous metrics + z-scores
-   Learned baseline (mean + std)
-   Last 5-step trajectory history
-   Constrained JSON output schema

### Structured Output

The model must return:

    {
      incident_type,
      confidence,
      reasoning,
      action,
      action_reasoning
    }

This ensures machine-parseable output and deterministic execution.

------------------------------------------------------------------------

## Autonomous Decision Loop

Each step:

1.  Observe telemetry
2.  Detect statistical anomaly
3.  Diagnose with LLM
4.  Select remediation
5.  Apply action to environment
6.  Repeat

The system runs fully autonomously.

------------------------------------------------------------------------

# 5. Simulation Design

Metrics: - CPU - Memory - Latency - Error Rate - Traffic

Fault Injection (12% probability per step):

-   traffic_spike
-   service_crash
-   memory_leak(Future addition)

Remediation actions:

-   `restart_service`
-   `scale_up`
-   `do_nothing`

------------------------------------------------------------------------

# 6. How to Run

## 1. Install dependencies

    pip install -r requirements.txt

## 2. Run the system

    python main.py

The browser opens automatically at:

    http://localhost:5000

-   Simulation runs for 50 steps
-   Dashboard updates in real time
-   Logs written to `logs/session_<timestamp>.jsonl`

------------------------------------------------------------------------

# 7. Assumptions

-   Single-node application simulation
-   Limited fault types
-   No historical baseline seeding
-   No cross-session memory
-   Prototype focused on AI-driven logic

------------------------------------------------------------------------

# 8. Known Limitations & Future Improvements

-   Baseline contamination during warmup
-   Single-step remediation only
-   Simplified simulation realism

Future improvements may include:

-   Reinforcement learning policy layer
-   More faults
-   Multi-agent coordination
-   Kubernetes integration
-   Persistent baseline storage
-   Advanced correlation modeling


------------------------------------------------------------------------

# 9. Video Walkthrough

The repository includes a 5--10 minute video walkthrough explaining:

-   Architecture design decisions
-   AI concepts incorporated
-   How the agent makes decisions
-   Live demonstration
-   Challenges encountered and lessons learned

------------------------------------------------------------------------

> AgentOps-Lite is a lightweight autonomous AIOps system that
> demonstrates the full incident lifecycle --- observe, detect,
> diagnose, remediate --- using a two-layer AI architecture where
> statistical machine learning identifies anomalies and a large language
> model reasons about their root cause and selects the appropriate
> remediation action.
