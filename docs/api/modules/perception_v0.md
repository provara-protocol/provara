# perception_v0

**Module:** `src/provara/perception_v0.py`

Sensor data hierarchy. Organizes observations into trust tiers (T0–T3) for structured sensor integration.

## Perception Tiers

| Tier | Trust | Latency | Example |
|------|-------|---------|---------|
| T0   | System | Instant | Internal state, heartbeat |
| T1   | Trusted | < 1s | Validated sensor input |
| T2   | Uncertain | < 60s | Network data, crowdsourced |
| T3   | Untrusted | Any | External claims, user input |

## Example

```python
from provara.perception_v0 import emit_perception_event

# T1: Trusted sensor (verified thermometer)
event = emit_perception_event(
    tier="T1",
    sensor_id="temp_sensor_01",
    value=22.5,
    unit="celsius"
)

# T3: Untrusted user input (social media claim)
event = emit_perception_event(
    tier="T3",
    source="twitter.com",
    claim="Alice is in Paris",
    confidence=0.3
)
```

## References

- [Provara: Perception Ontology](https://provara.dev/spec/)
