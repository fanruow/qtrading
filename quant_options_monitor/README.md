# quant_options_monitor

This is the canonical Python package project for the options monitor work.

The sibling `quant-options-monitor/` directory contains the earlier prototype CLI
that imports `src.*`. New implementation work should target this directory and
the import package:

```python
import quant_options_monitor
```

## Test

```bash
cd /Users/fanruowang/GitHub/qtrading/quant_options_monitor
python3 -m pytest
```

## Current Modules

- `quant_options_monitor.data`
- `quant_options_monitor.features`
- `quant_options_monitor.options`
- `quant_options_monitor.risk`
- `quant_options_monitor.strategies`
