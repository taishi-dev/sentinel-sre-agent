# Sentinel

An autonomous SRE agent for the **DevOps × AI Agent Hackathon 2026** (Findy × Google Cloud Japan).

On a Cloud Monitoring alert, Sentinel investigates a service's telemetry, diagnoses the root cause, and either autonomously rolls back a bad Cloud Run revision or escalates to a human. Its value is the **diagnosis and safety judgment**, not the rollback: it knows when *not* to act on its own.

- **Stack:** Python · Gemini · ADK · Cloud Run · Cloud Logging/Monitoring · Pub/Sub
- **Design spec:** [`docs/superpowers/specs/2026-06-27-sentinel-design.md`](docs/superpowers/specs/2026-06-27-sentinel-design.md)

## Branching

Versioned Gitflow. The current product line is `V1-sentinel`:

```
V1-sentinel/main       production, tagged releases
V1-sentinel/develop    integration
V1-sentinel/feature/*  feature branches
V1-sentinel/release/*  release prep
exp-finetune/*         standalone fine-tuning experiment (never merges into V1)
```
