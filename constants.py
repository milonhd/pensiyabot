```python
from typing import Dict, List

GROUP_IDS: List[int] = [
    -1002583988789, -1002529607781, -1002611068580, -1002607289832,
    -1002560662894, -1002645685285, -1002529375771, -1002262602915
]

TARIFF_DURATIONS: Dict[str, int] = {
    "self": 7,
    "basic": 30,
    "pro": 60,
    **{str(y): 7 for y in range(2025, 2032)}
}

REQUIRED_AMOUNTS: Dict[str, float] = {
    "self": 10000,
    "basic": 50000,
    "pro": 250000,
    **{str(y): 10000 for y in range(2025, 2032)}
}

TARIFF_CHAT_MAP: Dict[str, int] = {
    "basic": -1002583988789,
    "2025": -1002529607781,
    "2026": -1002611068580,
    "2027": -1002607289832,
    "2028": -1002560662894,
    "2029": -1002645685285,
    "2030": -1002529375771,
    "2031": -1002262602915
}
```
