"""ICP (Ideal Customer Profile) configuration.

The whole pipeline is driven by a single YAML file so a sales leader can
redefine targeting without touching code. See examples/icp.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ICPConfig:
    name: str
    target_industries: list[str]
    min_employees: int
    max_employees: int
    description_keywords: list[str]
    signal_keywords: dict[str, list[str]]
    signal_type_weights: dict[str, float]
    icp_weight: float = 0.5
    signal_weight: float = 0.5
    qualification_threshold: float = 0.55
    nurture_threshold: float = 0.35

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ICPConfig":
        raw = yaml.safe_load(Path(path).read_text())
        return cls(
            name=raw["name"],
            target_industries=raw.get("target_industries", []),
            min_employees=raw.get("min_employees", 0),
            max_employees=raw.get("max_employees", 10_000_000),
            description_keywords=raw.get("description_keywords", []),
            signal_keywords=raw.get("signal_keywords", {}),
            signal_type_weights=raw.get(
                "signal_type_weights",
                {
                    "hiring_surge": 1.0,
                    "funding": 0.8,
                    "tech_adoption": 0.7,
                    "website_change": 0.6,
                },
            ),
            icp_weight=raw.get("icp_weight", 0.5),
            signal_weight=raw.get("signal_weight", 0.5),
            qualification_threshold=raw.get("qualification_threshold", 0.55),
            nurture_threshold=raw.get("nurture_threshold", 0.35),
        )

    @classmethod
    def default(cls) -> "ICPConfig":
        return cls(
            name="Default AI/Voice ICP",
            target_industries=["ai", "gaming", "consumer apps", "developer tools"],
            min_employees=20,
            max_employees=2000,
            description_keywords=["ai", "generative", "agents", "voice", "llm", "assistant"],
            signal_keywords={
                "hiring_surge": ["ml engineer", "ai engineer", "applied scientist", "voice", "conversational ai"],
                "tech_adoption": ["llm", "vector database", "rag", "inference", "gpu"],
                "website_change": ["ai-powered", "generative ai", "voice agent", "copilot"],
            },
            signal_type_weights={
                "hiring_surge": 1.0,
                "funding": 0.8,
                "tech_adoption": 0.7,
                "website_change": 0.6,
            },
        )
