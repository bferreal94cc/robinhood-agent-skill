"""Version-bound strategy readiness gates; no strategy rules are approved here."""
from dataclasses import dataclass
from datetime import datetime
import re

from .market_data import source_rejection_reasons


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class StrategyVersion:
    version: str
    definition_hash: str
    approved_hash: str | None
    requirements: tuple
    enabled: bool = False


@dataclass(frozen=True)
class Evaluation:
    status: str
    reasons: tuple[str, ...]
    strategy_version: str
    definition_hash: str


def evaluate_readiness(strategy, symbol, observations, now, calendar):
    reasons = []
    if not _SHA256.fullmatch(strategy.definition_hash):
        reasons.append("invalid_strategy_definition_hash")
    if strategy.approved_hash != strategy.definition_hash:
        reasons.append("strategy_version_not_approved")
    if not strategy.enabled:
        reasons.append("strategy_disabled")
    if not calendar.is_open(now):
        reasons.append("market_closed")
    reasons.extend(source_rejection_reasons(strategy.requirements, observations, symbol, now))
    if not reasons:
        reasons.append("strategy_rules_not_configured")
    return Evaluation("blocked", tuple(reasons), strategy.version, strategy.definition_hash)
