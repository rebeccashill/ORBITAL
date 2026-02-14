# mission_framework/core/decision_variables.py
"""
Domain-agnostic decision variable system.

Designed for hackathon speed + systems clarity:
- Supports mixed variables: continuous, integer, binary, permutation.
- Provides sampling + mutation operators suitable for simulation-based planning
  (random-restart hillclimb / CEM / evolutionary search).
- Provides flatten/unflatten for numeric optimizers if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

ArrayLike = Union[float, int, List[float], List[int], np.ndarray]


class VarType(str, Enum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    BINARY = "binary"
    PERMUTATION = "permutation"


@dataclass(frozen=True)
class Bounds:
    """Numeric bounds for continuous/integer variables (broadcastable)."""
    low: Union[float, int, np.ndarray]
    high: Union[float, int, np.ndarray]

    def as_arrays(self, shape: Tuple[int, ...]) -> Tuple[np.ndarray, np.ndarray]:
        lo = np.broadcast_to(np.array(self.low, dtype=float), shape).copy()
        hi = np.broadcast_to(np.array(self.high, dtype=float), shape).copy()
        return lo, hi


@dataclass
class DecisionVar:
    """
    Base variable descriptor.

    Notes:
    - For PERMUTATION, use PermutationVar (items list; bounds unused).
    - For BINARY, bounds are implicitly [0,1].
    """
    name: str
    vtype: VarType
    shape: Tuple[int, ...] = (1,)
    bounds: Optional[Bounds] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def size(self) -> int:
        n = 1
        for s in self.shape:
            n *= s
        return n


@dataclass
class ContinuousVar(DecisionVar):
    def __init__(self, name: str, shape=(1,), bounds: Optional[Bounds] = None, metadata=None):
        super().__init__(name=name, vtype=VarType.CONTINUOUS, shape=tuple(shape),
                         bounds=bounds, metadata=metadata or {})


@dataclass
class IntegerVar(DecisionVar):
    def __init__(self, name: str, shape=(1,), bounds: Optional[Bounds] = None, metadata=None):
        super().__init__(name=name, vtype=VarType.INTEGER, shape=tuple(shape),
                         bounds=bounds, metadata=metadata or {})


@dataclass
class BinaryVar(DecisionVar):
    def __init__(self, name: str, shape=(1,), metadata=None):
        super().__init__(name=name, vtype=VarType.BINARY, shape=tuple(shape),
                         bounds=Bounds(0, 1), metadata=metadata or {})


@dataclass
class PermutationVar(DecisionVar):
    """
    A permutation of a fixed set of items (e.g., waypoint IDs, task IDs).

    Stored assignment value is a list of those items in some order.
    """
    items: Sequence[Any] = field(default_factory=list)

    def __init__(self, name: str, items: Sequence[Any], metadata=None):
        super().__init__(name=name, vtype=VarType.PERMUTATION, shape=(len(items),),
                         bounds=None, metadata=metadata or {})
        self.items = list(items)


@dataclass
class DecisionAssignment:
    """Concrete values for all decision variables."""
    values: Dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __setitem__(self, key: str, val: Any) -> None:
        self.values[key] = val

    def copy(self) -> "DecisionAssignment":
        return DecisionAssignment(values={k: _deepcopy_value(v) for k, v in self.values.items()})


def _deepcopy_value(v: Any) -> Any:
    if isinstance(v, np.ndarray):
        return v.copy()
    if isinstance(v, list):
        return list(v)
    return v


@dataclass
class MutationConfig:
    """
    Tuning knobs for mutation operators.

    - cont_sigma: stddev for continuous gaussian noise, as fraction of range if cont_sigma_is_frac.
    - int_step: max integer step for integer mutation.
    - p_flip: probability to flip each binary bit.
    - p_perm_swap: probability to apply a permutation swap.
    - perm_swaps: number of swap operations if permutation swap occurs.
    """
    cont_sigma: float = 0.10
    cont_sigma_is_frac: bool = True
    int_step: int = 1
    p_flip: float = 0.05
    p_perm_swap: float = 0.50
    perm_swaps: int = 2


@dataclass
class DecisionSpace:
    """
    Defines variables and provides:
    - validation
    - sampling (random feasible)
    - mutation (hillclimb / evolutionary)
    - crossover (optional)
    - flatten/unflatten for numeric-only optimizers
    """
    variables: List[DecisionVar]

    def names(self) -> List[str]:
        return [v.name for v in self.variables]

    def var(self, name: str) -> DecisionVar:
        for v in self.variables:
            if v.name == name:
                return v
        raise KeyError(f"Unknown decision variable: {name}")

    # -------------------------
    # Validation / coercion
    # -------------------------

    def validate(self, a: DecisionAssignment) -> None:
        for v in self.variables:
            if v.name not in a.values:
                raise ValueError(f"Missing value for variable '{v.name}'")

            val = a.values[v.name]

            if v.vtype == VarType.PERMUTATION:
                self._validate_permutation(v, val)
                continue

            arr = np.array(val, dtype=float).reshape(v.shape)

            if v.vtype == VarType.BINARY:
                if not np.all((arr == 0) | (arr == 1)):
                    raise ValueError(f"Binary var '{v.name}' contains non-binary values.")
            if v.vtype == VarType.INTEGER:
                if not np.all(np.isclose(arr, np.round(arr))):
                    raise ValueError(f"Integer var '{v.name}' contains non-integer values.")

            if v.bounds is not None:
                lo, hi = v.bounds.as_arrays(v.shape)
                if np.any(arr < lo - 1e-9) or np.any(arr > hi + 1e-9):
                    raise ValueError(f"Var '{v.name}' violates bounds.")

    def coerce(self, a: DecisionAssignment) -> DecisionAssignment:
        """
        Coerce an assignment to the closest valid representation:
        - clip numeric to bounds
        - round integers
        - threshold binaries
        - leave permutations untouched (assumed valid)
        """
        out = a.copy()
        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                continue

            arr = np.array(out[v.name], dtype=float).reshape(v.shape)

            if v.bounds is not None:
                lo, hi = v.bounds.as_arrays(v.shape)
                arr = np.minimum(np.maximum(arr, lo), hi)

            if v.vtype == VarType.BINARY:
                arr = (arr >= 0.5).astype(int)
            elif v.vtype == VarType.INTEGER:
                arr = np.round(arr).astype(int)

            out[v.name] = arr
        return out

    # -------------------------
    # Sampling
    # -------------------------

    def random_feasible(self, seed: Optional[int] = None) -> DecisionAssignment:
        rng = np.random.default_rng(seed)
        vals: Dict[str, Any] = {}

        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                items = list(getattr(v, "items"))
                rng.shuffle(items)
                vals[v.name] = items
                continue

            if v.bounds is None:
                raise ValueError(f"Cannot sample '{v.name}' without bounds.")

            lo, hi = v.bounds.as_arrays(v.shape)

            if v.vtype == VarType.BINARY:
                vals[v.name] = rng.integers(0, 2, size=v.shape, dtype=int)
            elif v.vtype == VarType.INTEGER:
                # integers() upper bound is exclusive; make it inclusive by +1
                lo_i = lo.astype(int)
                hi_i = hi.astype(int)
                vals[v.name] = rng.integers(lo_i, hi_i + 1, size=v.shape, dtype=int)
            else:
                vals[v.name] = rng.uniform(lo, hi, size=v.shape)

        a = DecisionAssignment(vals)
        self.validate(a)
        return a

    # -------------------------
    # Mutation / crossover (for hackathon-friendly planners)
    # -------------------------

    def mutate(
        self,
        a: DecisionAssignment,
        rng: np.random.Generator,
        cfg: MutationConfig = MutationConfig(),
        intensity: float = 1.0,
    ) -> DecisionAssignment:
        """
        Returns a mutated copy. Intended for hillclimb / evolutionary search.

        intensity scales mutation magnitude/probability (>=0).
        """
        out = a.copy()

        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                if rng.random() < (cfg.p_perm_swap * intensity):
                    out[v.name] = self._mutate_permutation(out[v.name], rng, swaps=max(1, cfg.perm_swaps))
                continue

            arr = np.array(out[v.name], dtype=float).reshape(v.shape)

            if v.vtype == VarType.BINARY:
                p = min(1.0, cfg.p_flip * intensity)
                flips = rng.random(size=v.shape) < p
                arr = np.where(flips, 1 - arr, arr)
                out[v.name] = arr.astype(int)
                continue

            if v.bounds is None:
                raise ValueError(f"Numeric var '{v.name}' missing bounds (needed for mutation).")

            lo, hi = v.bounds.as_arrays(v.shape)

            if v.vtype == VarType.INTEGER:
                step = max(1, int(round(cfg.int_step * intensity)))
                delta = rng.integers(-step, step + 1, size=v.shape)
                arr = np.round(arr).astype(int) + delta
                arr = np.minimum(np.maximum(arr, lo.astype(int)), hi.astype(int))
                out[v.name] = arr.astype(int)
                continue

            # CONTINUOUS
            if cfg.cont_sigma_is_frac:
                sigma = cfg.cont_sigma * (hi - lo)
            else:
                sigma = np.full(v.shape, cfg.cont_sigma, dtype=float)
            sigma = sigma * max(0.0, float(intensity))
            noise = rng.normal(0.0, 1.0, size=v.shape) * sigma
            arr = arr + noise
            arr = np.minimum(np.maximum(arr, lo), hi)
            out[v.name] = arr

        return self.coerce(out)

    def crossover(
        self,
        parent_a: DecisionAssignment,
        parent_b: DecisionAssignment,
        rng: np.random.Generator,
        p_swap: float = 0.50,
    ) -> DecisionAssignment:
        """
        Simple crossover:
        - Numeric vars: element-wise pick from A or B
        - Permutation vars: take A then apply small repair by swapping towards B (cheap heuristic)
This is optional; you can ignore crossover and just mutate.
        """
        child = parent_a.copy()

        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                # keep A's order, optionally nudge towards B by swapping some positions
                if rng.random() < p_swap:
                    child[v.name] = self._perm_nudge_towards(child[v.name], parent_b[v.name], rng)
                continue

            a_arr = np.array(parent_a[v.name], dtype=float).reshape(v.shape)
            b_arr = np.array(parent_b[v.name], dtype=float).reshape(v.shape)
            mask = rng.random(size=v.shape) < p_swap
            out = np.where(mask, b_arr, a_arr)

            if v.vtype == VarType.BINARY:
                child[v.name] = (out >= 0.5).astype(int)
            elif v.vtype == VarType.INTEGER:
                child[v.name] = np.round(out).astype(int)
            else:
                child[v.name] = out

        return self.coerce(child)

    # -------------------------
    # Flatten / unflatten for numeric-only optimizers
    # -------------------------

    def flat_size(self) -> int:
        """Size of flattened numeric vector (excludes permutations)."""
        total = 0
        for v in self.variables:
            if v.vtype != VarType.PERMUTATION:
                total += v.size()
        return total

    def to_flat(self, a: DecisionAssignment) -> np.ndarray:
        """Flatten numeric vars (continuous/integer/binary). Permutations excluded."""
        chunks: List[np.ndarray] = []
        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                continue
            arr = np.array(a[v.name], dtype=float).reshape(-1)
            chunks.append(arr)
        return np.concatenate(chunks) if chunks else np.array([], dtype=float)

    def from_flat(self, x: np.ndarray, template: Optional[DecisionAssignment] = None) -> DecisionAssignment:
        """
        Build an assignment from a flat numeric vector.
        - If template provided, permutations are copied from it.
        - Otherwise, permutations are sampled randomly.
        """
        rng = np.random.default_rng(0)
        vals: Dict[str, Any] = {}

        if template is None:
            # Create a minimal template with random permutations, if any.
            template = self.random_feasible(seed=0)

        i = 0
        for v in self.variables:
            if v.vtype == VarType.PERMUTATION:
                vals[v.name] = _deepcopy_value(template[v.name])
                continue
            n = v.size()
            vals[v.name] = np.array(x[i:i + n], dtype=float).reshape(v.shape)
            i += n

        a = DecisionAssignment(vals)
        return self.coerce(a)

    # -------------------------
    # Internal helpers
    # -------------------------

    def _validate_permutation(self, v: DecisionVar, val: Any) -> None:
        items = list(getattr(v, "items"))
        if not isinstance(val, (list, tuple)):
            raise ValueError(f"Permutation var '{v.name}' must be list/tuple.")
        if len(val) != len(items):
            raise ValueError(f"Permutation var '{v.name}' wrong length.")
        if set(val) != set(items):
            raise ValueError(f"Permutation var '{v.name}' must be a permutation of items.")

    @staticmethod
    def _mutate_permutation(order: Sequence[Any], rng: np.random.Generator, swaps: int = 2) -> List[Any]:
        arr = list(order)
        n = len(arr)
        if n < 2:
            return arr
        for _ in range(swaps):
            i, j = rng.integers(0, n), rng.integers(0, n)
            if i != j:
                arr[i], arr[j] = arr[j], arr[i]
        return arr

    @staticmethod
    def _perm_nudge_towards(order_a: Sequence[Any], order_b: Sequence[Any], rng: np.random.Generator) -> List[Any]:
        """
        Very lightweight nudge:
        - Pick a random item and move it in A closer to its index in B.
        """
        a = list(order_a)
        b = list(order_b)
        n = len(a)
        if n < 2:
            return a
        item = a[rng.integers(0, n)]
        ia = a.index(item)
        ib = b.index(item)
        if ia == ib:
            return a
        # Swap item step-by-step toward target index with one swap
        j = ia + 1 if ib > ia else ia - 1
        a[ia], a[j] = a[j], a[ia]
        return a
