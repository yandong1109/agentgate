# Control Panel

The control panel is the Vue 3 Web interface for Dataset management, evaluation launch,
progress, reports, Badcases, Trace drill-down, and later analysis workflows.

```text
web/ -> server/ -> application/ -> core capabilities
```

The Web UI does not query storage directly and does not duplicate domain rules in
TypeScript. The inherited Chinese P1 UI remains the working baseline while the backend
architecture is refactored. Its setup and test instructions are preserved under
[P1 demo history](../history/p1-demo/).
