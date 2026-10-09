"""SmartFabric — the reference implementation of the IAIso Fabric Protocol (IFP).

IFP is the wire protocol + node fingerprint that carries IAIso v5.0 containment
(pressure, the 7 layers, the 5 invariants, ConsentScope, atomic reset) across a
*fleet* of governed AI nodes — so heterogeneous agents/tools/models behave as
one governed data fabric, not a pile of independently-wrapped agents.

Public API:
    PressureEngine, PressureConfig, Zone, StepOutcome  — the core pressure model
    NodeSample, FleetPressure, fleet_pressure          — Layer-3 fleet aggregation
    CIRMessage, CIRHeader, CIRPolicy, InfluenceClass   — the CIR envelope
    fingerprint (module)                               — load/validate/parse
    conformance (module)                               — run FAB-* checks
"""
from ._version import __version__
from .models import (
    CIR_VERBS,
    CIRHeader,
    CIRMessage,
    CIRPolicy,
    EXPANDING_VERBS,
    InfluenceClass,
    is_known_verb,
)
from .pressure import (
    FleetPressure,
    NodeSample,
    PressureConfig,
    PressureEngine,
    StepOutcome,
    Zone,
    fleet_pressure,
)
from . import conformance, fingerprint, vectors, wire

__all__ = [
    "__version__",
    "PressureEngine",
    "PressureConfig",
    "Zone",
    "StepOutcome",
    "NodeSample",
    "FleetPressure",
    "fleet_pressure",
    "CIRMessage",
    "CIRHeader",
    "CIRPolicy",
    "InfluenceClass",
    "CIR_VERBS",
    "EXPANDING_VERBS",
    "is_known_verb",
    "fingerprint",
    "conformance",
    "vectors",
    "wire",
]
