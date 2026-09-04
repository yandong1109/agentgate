# Static Agent and Skill Analysis

`analysis/` is a top-level capability that examines externally owned Agent and Skill
definitions without executing them. It covers description quality, conflict, confusion,
Prompt-to-Skill alignment, coverage, and reviewable findings.

It remains separate from `optimizer/`:

```text
analysis/    Definition-time static analysis
optimizer/   Post-run analysis of Results and Traces
```

The [Skill static analysis plan](skill-static-analysis-plan.md) retains useful behavior
and acceptance criteria, but its pre-refactor ownership and file map are not
authoritative.
