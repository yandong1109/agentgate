# Result

The Result capability owns derived evaluation conclusions:

```text
result/
├── metrics.py
├── gate.py
├── report.py
└── comparison.py
```

Domain Result models belong in `domain/`. Read-only retrieval and assembly for Web, CLI,
and APIs belongs in `application/result_reader.py`. Persistence belongs in `storage/`,
and optional external delivery belongs in `integrations/result_outputs/`.

Result does not execute Evaluators, invoke Agents, collect Traces, or render Web charts.
