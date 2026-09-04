# Evaluator

The Evaluator capability owns evaluation methods and execution:

```text
evaluator/
├── evaluator_protocol.py
├── executor.py
├── hybrid.py
├── rule/
└── judge/
```

Evaluator definition and version lifecycle orchestration belongs in
`application/evaluator_management.py`. External Judge model access belongs in
`integrations/model_providers/`.

The current [implementation plan](implementation-plan.md) retains useful JSON validation,
priority, and acceptance design, but its pre-refactor file map is not authoritative.
Implemented P1 refactor records are under [P1 history](../history/p1-demo/).
