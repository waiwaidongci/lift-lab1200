"""Pre-registered pre-revenue strata: validation, labels and membership.

Bounds are the cut points fixed when the experiment is registered. Values are
assigned to ``[-inf, b0), [b0, b1), ..., [bn, +inf)``; an empty/None value
means the experiment keeps the legacy unstratified method.
"""
from bisect import bisect_right
import math

MAX_BOUNDS = 10


def validate_bounds(bounds):
    if bounds is None:
        return None
    if not isinstance(bounds, (list, tuple)):
        raise ValueError("分层边界必须是数值列表")
    if not 1 <= len(bounds) <= MAX_BOUNDS:
        raise ValueError(f"分层边界需 1 至 {MAX_BOUNDS} 个切点")
    values = []
    for item in bounds:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("分层边界必须是有限数值")
        value = float(item)
        if not math.isfinite(value):
            raise ValueError("分层边界必须是有限数值")
        if values and value <= values[-1]:
            raise ValueError("分层边界必须严格递增且不可重复")
        values.append(value)
    return values


def _edge(value):
    return f"{value:g}"


def labels(bounds):
    labels = []
    for index, bound in enumerate(bounds):
        if index == 0:
            labels.append(f"< {_edge(bound)}")
        else:
            labels.append(f"[{_edge(bounds[index - 1])}, {_edge(bound)})")
    labels.append(f"≥ {_edge(bounds[-1])}")
    return labels


def index_of(value, bounds):
    """Stratum index for a single pre-revenue value (0 .. len(bounds))."""
    return bisect_right(bounds, value)


def describe(bounds):
    """Compact human-readable description used in summaries and exports."""
    if not bounds:
        return "不分层（原方法）"
    return " / ".join(labels(bounds)) + " 元"
