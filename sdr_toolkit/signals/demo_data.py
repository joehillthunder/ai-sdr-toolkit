"""Bundled, fully-offline sample dataset.

This exists so the whole pipeline — signal collection, scoring, agents,
reporting, CLI — runs end to end with zero credentials and zero network
access. Swap this module out for real connectors (ATS job boards, a
funding-data API, BuiltWith, a website crawler) once you're plugging
this into an actual sales stack; every downstream piece only depends on
the `Company` / raw dict shapes below, not on this module.

All companies, people, and events here are fictional.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..models import Company, Contact

TODAY = date(2026, 8, 24)


def demo_companies() -> list[Company]:
    return [
        Company(
            id="nimbus-voice",
            name="Nimbus Voice Labs",
            domain="nimbusvoice.ai",
            industry="ai",
            employee_count=80,
            headquarters="San Francisco, CA",
            description="Nimbus builds real-time generative voice agents for customer support automation.",
        ),
        Company(
            id="pixel-forge",
            name="Pixel Forge Games",
            domain="pixelforgegames.com",
            industry="gaming",
            employee_count=150,
            headquarters="Austin, TX",
            description="Indie game studio experimenting with AI-driven NPC dialogue and dynamic quests.",
        ),
        Company(
            id="ledger-peak",
            name="Ledger Peak Finance",
            domain="ledgerpeak.com",
            industry="fintech",
            employee_count=400,
            headquarters="New York, NY",
            description="Ledger Peak provides SMB lending and treasury management software.",
        ),
        Company(
            id="skyline-robotics",
            name="Skyline Robotics",
            domain="skylinerobotics.com",
            industry="robotics",
            employee_count=90,
            headquarters="Boston, MA",
            description="Skyline builds warehouse automation hardware and fleet management software.",
        ),
        Company(
            id="chatterbox",
            name="Chatterbox AI",
            domain="chatterbox.ai",
            industry="ai",
            employee_count=45,
            headquarters="Seattle, WA",
            description="Chatterbox is a conversational AI assistant platform for consumer apps.",
        ),
        Company(
            id="vantage-dev",
            name="Vantage Dev Tools",
            domain="vantagedev.io",
            industry="developer tools",
            employee_count=220,
            headquarters="Denver, CO",
            description="Vantage ships an AI coding copilot and agent framework for enterprise engineering teams.",
        ),
        Company(
            id="greencart",
            name="GreenCart Retail",
            domain="greencart.com",
            industry="retail",
            employee_count=900,
            headquarters="Chicago, IL",
            description="GreenCart operates an e-commerce marketplace for sustainable home goods.",
        ),
        Company(
            id="aurora-games",
            name="Aurora Game Studios",
            domain="auroragames.com",
            industry="gaming",
            employee_count=1200,
            headquarters="Los Angeles, CA",
            description="Aurora is a AAA studio piloting generative AI for non-player character dialogue.",
        ),
    ]


# job title, days_ago posted
JOB_POSTINGS: dict[str, list[tuple[str, int]]] = {
    "nimbus-voice": [
        ("Senior Conversational AI Engineer", 3),
        ("Applied Scientist, Voice", 6),
        ("ML Infrastructure Engineer", 9),
        ("Voice UX Researcher", 14),
    ],
    "pixel-forge": [
        ("AI Gameplay Engineer (NPC Dialogue)", 5),
        ("Technical Artist", 20),
        ("Applied ML Engineer - Game AI", 8),
    ],
    "ledger-peak": [
        ("Compliance Analyst", 12),
        ("Backend Engineer, Payments", 18),
    ],
    "skyline-robotics": [
        ("Firmware Engineer", 15),
        ("Fleet Software Engineer", 22),
    ],
    "chatterbox": [
        ("ML Engineer, Conversational AI", 2),
        ("Applied AI Engineer", 4),
        ("Founding Voice Engineer", 7),
    ],
    "vantage-dev": [
        ("AI Agent Framework Engineer", 4),
        ("Developer Advocate, AI Copilot", 10),
        ("LLM Applications Engineer", 11),
    ],
    "greencart": [
        ("Fulfillment Operations Manager", 25),
    ],
    "aurora-games": [
        ("Generative AI Engineer - NPC Systems", 6),
        ("Narrative Designer, AI Dialogue", 9),
    ],
}

# round label, amount usd, days_ago announced
FUNDING_EVENTS: dict[str, list[tuple[str, int, int]]] = {
    "nimbus-voice": [("Series B", 42_000_000, 18)],
    "chatterbox": [("Series A", 14_000_000, 30)],
    "vantage-dev": [("Series B", 60_000_000, 55)],
    "skyline-robotics": [("Series A", 20_000_000, 90)],
}

# free-text snippets from blog posts / changelogs / social — used by the
# tech-adoption signal source.
TECH_MENTIONS: dict[str, list[tuple[str, int]]] = {
    "nimbus-voice": [
        ("We migrated our real-time inference stack to a new low-latency GPU cluster.", 10),
        ("Rolled out a retrieval-augmented generation (RAG) pipeline for support agents.", 25),
    ],
    "pixel-forge": [
        ("Shipped a vector database backed memory system for our NPCs.", 12),
    ],
    "vantage-dev": [
        ("Our agent framework now supports multi-step tool use out of the box.", 5),
        ("New: bring-your-own LLM inference endpoint for enterprise customers.", 40),
    ],
    "aurora-games": [
        ("Prototyping generative dialogue trees with an in-house LLM fine-tune.", 15),
    ],
    "ledger-peak": [
        ("Upgraded our fraud detection models to a new gradient boosting pipeline.", 60),
    ],
}

# simulated scraped homepage/about-page copy — used by the website-change
# signal source when live crawling is unavailable or disabled.
WEBSITE_SNIPPETS: dict[str, str] = {
    "nimbus-voice": "Nimbus Voice Labs — the generative voice agent platform for real-time, ai-powered customer support.",
    "pixel-forge": "Pixel Forge is building the next generation of games with dynamic, ai-driven NPC dialogue.",
    "ledger-peak": "Ledger Peak — lending and treasury tools built for modern finance teams.",
    "skyline-robotics": "Skyline Robotics — autonomous warehouse fleets and fulfillment automation.",
    "chatterbox": "Chatterbox AI — a conversational ai assistant and voice agent copilot for consumer apps.",
    "vantage-dev": "Vantage — an ai coding copilot and agent framework for enterprise engineering teams.",
    "greencart": "GreenCart — sustainable home goods, delivered fast.",
    "aurora-games": "Aurora Game Studios — award winning AAA titles, now exploring generative ai npc systems.",
}


def demo_contacts() -> list[Contact]:
    return [
        Contact("c1", "nimbus-voice", "Priya Anand", "VP Engineering", "vp", "priya@nimbusvoice.ai", "linkedin.com/in/priyaanand"),
        Contact("c2", "nimbus-voice", "Dev Malhotra", "Head of Product", "director", "dev@nimbusvoice.ai", "linkedin.com/in/devmalhotra"),
        Contact("c3", "pixel-forge", "Sam Ostrowski", "Studio Technical Director", "director", "sam@pixelforgegames.com", "linkedin.com/in/samostrowski"),
        Contact("c4", "ledger-peak", "Marcus Reyes", "VP Engineering", "vp", "marcus@ledgerpeak.com", "linkedin.com/in/marcusreyes"),
        Contact("c5", "skyline-robotics", "Elena Novak", "Director of Software", "director", "elena@skylinerobotics.com", "linkedin.com/in/elenanovak"),
        Contact("c6", "chatterbox", "Jordan Lee", "Co-Founder & CTO", "c_level", "jordan@chatterbox.ai", "linkedin.com/in/jordanlee"),
        Contact("c7", "vantage-dev", "Alicia Chen", "VP Product", "vp", "alicia@vantagedev.io", "linkedin.com/in/aliciachen"),
        Contact("c8", "greencart", "Tom Baker", "Director of Engineering", "director", "tom@greencart.com", "linkedin.com/in/tombaker"),
        Contact("c9", "aurora-games", "Nadia Kessler", "Head of AI R&D", "director", "nadia@auroragames.com", "linkedin.com/in/nadiakessler"),
    ]


def days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)
