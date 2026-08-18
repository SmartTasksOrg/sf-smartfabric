"""Pressure model — the mechanical heart of IAIso, carried across the fabric.

This is a *faithful* re-implementation of the single-node IAIso v5.0 pressure
model (SmartTasksOrg/IAISO · IAIso-v5.0/core/spec/pressure), plus the fabric's
own addition: fleet-level aggregation (``P_fleet``) so Layer-3 ecosystem
coupling works across many nodes.

Binding note (why the field names look like this): the fabric does **not**
invent a pressure model — it carries the core's. So ``PressureConfig`` uses the
exact field names and defaults from the core's normative spec
(``escalation_threshold``, ``release_threshold``, ``dissipation_per_step``,
``token_coefficient`` per 1000 tokens, ``tool_coefficient``, ``depth_coefficient``,
``post_release_lock``). Determinism tolerance is 1e-9, as in the core.

Nothing here is empirically calibrated — the defaults reproduce the core's
reference behaviour; production deployments MUST calibrate against real traces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

TOLERANCE = 1e-9


class Zone(str, Enum):
    """Pressure zones on the wire. ``nominal``/``warning`` are fabric telemetry
    bands; ``escalation``/``release`` are the core's two normative thresholds."""

    NOMINAL = "nominal"
    WARNING = "warning"
    ESCALATION = "escalation"
    RELEASE = "release"


@dataclass(frozen=True)
class PressureConfig:
    """Mirror of IAIso core ``PressureConfig`` (+ one fabric-only field).

    All defaults trace to IAIso-v5.0/core/spec/pressure/README.md §2. The single
    fabric addition is ``warning_band`` — an early-warning telemetry threshold
    the fabric surfaces *before* the core's escalation threshold. It has no
    enforcement meaning in the core; it only raises sampling/observability.
    """

    escalation_threshold: float = 0.85
    release_threshold: float = 0.95
    dissipation_per_step: float = 0.02
    dissipation_per_second: float = 0.0
    token_coefficient: float = 0.015  # per 1000 tokens
    tool_coefficient: float = 0.08    # per tool call
    depth_coefficient: float = 0.05   # per planning-depth level
    post_release_lock: bool = True
    # fabric-only early-warning band (not a core threshold):
    warning_band: float = 0.70

    def validate(self) -> None:
        """Reject configs the core would reject (spec §2 Validation)."""
        for name in ("escalation_threshold", "release_threshold"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{name}={v} outside [0, 1]")
        if self.release_threshold <= self.escalation_threshold:
            raise ValueError("release_threshold must be > escalation_threshold")
        for name in (
            "dissipation_per_step",
            "dissipation_per_second",
            "token_coefficient",
            "tool_coefficient",
            "depth_coefficient",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if not (0.0 <= self.warning_band <= self.escalation_threshold):
            raise ValueError("warning_band must be in [0, escalation_threshold]")


@dataclass
class StepOutcome:
    """Result of one clocked evaluation (invariant 3: clocked evaluation only)."""

    pressure: float
    zone: Zone
    released: bool
    locked: bool


class PressureEngine:
    """Deterministic single-node pressure accumulator.

    ``dp/dt = I(t) - D(p,t) - R(p,t)`` realised as a discrete step:
    accumulate input, dissipate, then release (atomic reset) if at/over the
    release threshold. Given identical config + input sequence, two engines
    produce identical trajectories (within TOLERANCE) — that is what lets the
    fabric compare and aggregate pressure across heterogeneous nodes.
    """

    def __init__(self, config: PressureConfig | None = None) -> None:
        self.config = config or PressureConfig()
        self.config.validate()
        self._p: float = 0.0
        self._locked: bool = False

    @property
    def pressure(self) -> float:
        return self._p

    @property
    def locked(self) -> bool:
        return self._locked

    def zone(self, p: float | None = None) -> Zone:
        p = self._p if p is None else p
        c = self.config
        if p >= c.release_threshold:
            return Zone.RELEASE
        if p >= c.escalation_threshold:
            return Zone.ESCALATION
        if p >= c.warning_band:
            return Zone.WARNING
        return Zone.NOMINAL

    def step(
        self,
        *,
        tokens: int = 0,
        tool_calls: int = 0,
        depth: int = 0,
        seconds: float = 0.0,
    ) -> StepOutcome:
        """One clocked evaluation. Returns the post-step outcome.

        If ``post_release_lock`` is set and the node has released, further input
        is refused (``ExecutionLocked`` semantics) until :meth:`reset` is called.
        """
        c = self.config
        if self._locked and c.post_release_lock:
            return StepOutcome(self._p, self.zone(), released=False, locked=True)

        intake = (
            (tokens / 1000.0) * c.token_coefficient
            + tool_calls * c.tool_coefficient
            + depth * c.depth_coefficient
        )
        dissipation = c.dissipation_per_step + c.dissipation_per_second * seconds
        p = self._p + intake - dissipation
        p = _clamp(p)

        released = False
        if p >= c.release_threshold - TOLERANCE:
            # Atomic reset (release). Lossy by contract (invariant 2).
            released = True
            self._p = 0.0
            self._locked = c.post_release_lock
            return StepOutcome(0.0, Zone.RELEASE, released=True, locked=self._locked)

        self._p = p
        return StepOutcome(self._p, self.zone(), released=released, locked=False)

    def reset(self) -> None:
        """Explicit atomic reset — lossy wipe; clears the post-release lock.

        Any state expected to survive a reset MUST be gated by a Layer-5
        ConsentScope elsewhere; the engine itself keeps nothing (invariant 2).
        """
        self._p = 0.0
        self._locked = False


def _clamp(p: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, p))


# --------------------------------------------------------------------------- #
# Fabric addition: fleet pressure (Layer-3 ecosystem coupling across nodes)    #
# --------------------------------------------------------------------------- #

@dataclass
class NodeSample:
    """One node's contribution to fleet pressure."""

    node_id: str
    pressure: float
    centrality: float = 1.0  # substrate S10 topology weight; hubs weigh more


@dataclass
class FleetPressure:
    value: float
    peak_node: str | None
    peak_pressure: float
    hot_nodes: list[str] = field(default_factory=list)


def fleet_pressure(
    samples: Iterable[NodeSample],
    *,
    escalation_threshold: float = 0.85,
) -> FleetPressure:
    """Topology-weighted fleet pressure.

    A scale-free fleet is heavy-tailed: a few high-centrality hubs dominate
    load (docs/05). We therefore weight each node's pressure by its centrality
    so a hub approaching release moves ``P_fleet`` more than a leaf does. Also
    surfaces which nodes are in/above the escalation band ("hot").
    """
    samples = list(samples)
    if not samples:
        return FleetPressure(value=0.0, peak_node=None, peak_pressure=0.0, hot_nodes=[])

    total_w = sum(max(s.centrality, 0.0) for s in samples) or float(len(samples))
    weighted = sum(s.pressure * max(s.centrality, 0.0) for s in samples) / total_w

    peak = max(samples, key=lambda s: s.pressure)
    hot = sorted(
        (s.node_id for s in samples if s.pressure >= escalation_threshold - TOLERANCE)
    )
    return FleetPressure(
        value=_clamp(weighted),
        peak_node=peak.node_id,
        peak_pressure=peak.pressure,
        hot_nodes=hot,
    )
