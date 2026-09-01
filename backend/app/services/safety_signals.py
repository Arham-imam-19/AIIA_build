"""Pure NPvCC-style PRR calculations for demonstration safety signals."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


MINIMUM_COUNT = 3
MINIMUM_PRR = 2.0
MINIMUM_CHI_SQUARE = 4.0
DISCLAIMER = "Demo decision support only - not validated pharmacovigilance signal detection."


@dataclass(frozen=True)
class SignalSite:
    id: int
    code: str
    name: str


@dataclass(frozen=True)
class SignalEvent:
    site_id: int
    term: str


def _chi_square(a: int, b: int, c: int, d: int) -> float | None:
    total = a + b + c + d
    denominator = (a + b) * (c + d) * (a + c) * (b + d)
    if total == 0 or denominator == 0:
        return None
    value = total * ((a * d - b * c) ** 2) / denominator
    return round(value, 6) if isfinite(value) else None


def calculate_safety_signals(
    trial_id: int,
    visible_sites: Iterable[SignalSite],
    trial_events: Iterable[SignalEvent],
) -> dict:
    """Calculate one PRR table for every visible-site/observed-term pair.

    The target sites are visibility-filtered by the caller. Events intentionally
    include the full trial: the other sites form the comparator for each visible
    target site. Terms are compared exactly as reported, without normalization.
    """
    sites = sorted(visible_sites, key=lambda site: (site.code, site.id, site.name))
    events = list(trial_events)
    terms = sorted({event.term for event in events})
    total_events = len(events)
    site_totals: dict[int, int] = {}
    pair_counts: dict[tuple[int, str], int] = {}
    term_totals: dict[str, int] = {}

    for event in events:
        site_totals[event.site_id] = site_totals.get(event.site_id, 0) + 1
        key = (event.site_id, event.term)
        pair_counts[key] = pair_counts.get(key, 0) + 1
        term_totals[event.term] = term_totals.get(event.term, 0) + 1

    items = []
    for site in sites:
        site_total = site_totals.get(site.id, 0)
        other_sites_total = total_events - site_total
        for term in terms:
            a = pair_counts.get((site.id, term), 0)
            b = site_total - a
            c = term_totals[term] - a
            d = other_sites_total - c
            chi_square = _chi_square(a, b, c, d)

            reasons = []
            prr = None
            if a + b == 0:
                reasons.append("target site has no adverse events")
            elif c + d == 0:
                reasons.append("no adverse events are available at other trial sites")
            elif c == 0:
                reasons.append("target term has no adverse events at other trial sites")
            else:
                value = (a / (a + b)) / (c / (c + d))
                if isfinite(value):
                    prr = round(value, 6)
                else:
                    reasons.append("PRR is not finite")

            if chi_square is None:
                reasons.append("chi-square is not estimable because a marginal total is zero")

            estimable = prr is not None and chi_square is not None
            signal = bool(
                estimable
                and a >= MINIMUM_COUNT
                and prr >= MINIMUM_PRR
                and chi_square >= MINIMUM_CHI_SQUARE
            )
            items.append(
                {
                    "trial_id": trial_id,
                    "term": term,
                    "site_id": site.id,
                    "site_code": site.code,
                    "site_name": site.name,
                    "a": a,
                    "b": b,
                    "c": c,
                    "d": d,
                    "prr": prr,
                    "chi_square": chi_square,
                    "signal": signal,
                    "calculation_status": "estimable" if estimable else "not_estimable",
                    "calculation_reason": (
                        "PRR and chi-square estimated" if estimable else "; ".join(reasons)
                    ),
                }
            )

    if not events:
        calculation_status = "no_data"
        calculation_reason = "trial has no adverse events"
    elif not sites:
        calculation_status = "no_visible_sites"
        calculation_reason = "caller has no visible sites in this trial"
    else:
        calculation_status = "calculated"
        calculation_reason = "all visible site and verbatim-term pairs calculated"

    return {
        "trial_id": trial_id,
        "calculation_status": calculation_status,
        "calculation_reason": calculation_reason,
        "thresholds": {
            "minimum_count": MINIMUM_COUNT,
            "minimum_prr": MINIMUM_PRR,
            "minimum_chi_square": MINIMUM_CHI_SQUARE,
        },
        "disclaimer": DISCLAIMER,
        "items": items,
    }
