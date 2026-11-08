"""Explicit source-quality checks; raw provider events are not strategy evidence."""
from datetime import timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool


class SourceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=80)
    symbol: Literal["SPY", "QQQ"]
    event_at: AwareDatetime
    first_seen_at: AwareDatetime
    mode: Literal["live", "delayed", "replay", "paper", "mock"]
    entitlement: str = Field(min_length=1, max_length=80)
    entitlement_verified: StrictBool
    complete: StrictBool


class SourceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=80)
    max_age_seconds: int = Field(gt=0, le=86_400)
    entitlement: str = Field(min_length=1, max_length=80)


def source_rejection_reasons(requirements, observations, symbol, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Source freshness checks require a timezone-aware timestamp")
    now = now.astimezone(timezone.utc)
    reasons = []
    for requirement in requirements:
        observation = observations.get(requirement.source)
        if observation is None:
            reasons.append(f"missing_source_{requirement.source}")
            continue
        if observation.source != requirement.source:
            reasons.append(f"wrong_source_{requirement.source}")
        if observation.symbol != symbol:
            reasons.append(f"wrong_symbol_{requirement.source}")
        if observation.mode != "live":
            reasons.append(f"non_live_source_{requirement.source}")
        if not observation.complete:
            reasons.append(f"incomplete_source_{requirement.source}")
        if not observation.entitlement_verified or observation.entitlement != requirement.entitlement:
            reasons.append(f"unverified_entitlement_{requirement.source}")
        age = (now - observation.event_at.astimezone(timezone.utc)).total_seconds()
        first_seen_age = (now - observation.first_seen_at.astimezone(timezone.utc)).total_seconds()
        if age > requirement.max_age_seconds:
            reasons.append(f"stale_source_{requirement.source}")
        if age < -5 or first_seen_age < -5:
            reasons.append(f"future_source_{requirement.source}")
        delta = (observation.event_at - observation.first_seen_at).total_seconds()
        if delta > 5:
            reasons.append(f"event_after_first_seen_{requirement.source}")
    return reasons
