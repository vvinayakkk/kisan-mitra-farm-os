"""Conservative, offline extraction of farmer-reported facts, never commands.

Messages remain the complete evidence trail. This small vocabulary deliberately
prefers missing a fact to turning a question, future wish, or document into truth.
"""

import re

_PATTERNS = (
    (
        "language_preference",
        r"(?:i prefer|please (?:reply|respond|speak) in|my preferred language is)\s+(?:english|hindi|telugu|tamil|marathi|bengali|kannada|malayalam|punjabi|gujarati|odia|urdu)\b[^?\n]*",
        0.95,
    ),
    ("soil", r"my (?:farm(?:'s)? |field(?:'s)? )?soil (?:is|has)\s+[^?\n]+", 0.9),
    (
        "water_source",
        r"my (?:farm(?:'s)? )?(?:water source|irrigation source|irrigation method) is\s+[^?\n]+",
        0.9,
    ),
    (
        "farm_location",
        r"(?:my (?:farm|field) is (?:in|near)|i farm in|i live in)\s+[^?\n]+",
        0.9,
    ),
    (
        "farm_area",
        r"(?:i (?:have|own|farm)|my farm (?:is|has))\s+(?:about |approximately )?\d+(?:\.\d+)?\s*(?:acres?|hectares?|ha|bighas?)\b[^?\n]*",
        0.9,
    ),
    (
        "reported_crop",
        r"i (?:currently )?(?:grow|cultivate|am growing)\s+[^?\n]+",
        0.85,
    ),
    (
        "irrigation",
        r"i (?:use|have)\s+(?:drip|sprinkler|flood|canal|borewell|well|rainfed)\b[^?\n]*",
        0.9,
    ),
    ("farm_area", r"मेरे पास\s+[\d०-९]+(?:\.[\d०-९]+)?\s*(?:एकड़|हेक्टेयर)\b[^?\n]*", 0.9),
    ("soil", r"मेरी मिट्टी\s+[^?\n]+\s+है", 0.9),
)
_UNTRUSTED = re.compile(
    r"\b(?:synthetic|integration test|pytest|fictional|hypothetical|pretend|example farmer|test fixture|system prompt|ignore (?:all |previous )?instructions)\b",
    re.IGNORECASE,
)
_FUTURE_OR_QUESTION = re.compile(
    r"\b(?:if|suppose|would|should|could|can i|will|planning to|plan to|want to|intend to|might|recommend|suggest|what|which|whether)\b|(?:क्या|अगर|चाहता|चाहती)",
    re.IGNORECASE,
)


def extract_facts(content):
    if (
        not isinstance(content, str)
        or len(content) > 12000
        or _UNTRUSTED.search(content)
    ):
        return []
    # Added attachment names, pasted quotations and code are untrusted context.
    content = content.split("\nSelected uploaded attachments", 1)[0]
    facts = {}
    for clause in re.split(
        r"[;!\n]|(?<!\d)\.(?!\d)|(?:,?\s+but\s+)|(?:,\s*(?=I\b|my\b))",
        content,
        flags=re.IGNORECASE,
    ):
        clause = clause.strip()
        if (
            not clause
            or "?" in clause
            or any(c in clause for c in ('"', "“", "”", "`", "<", ">"))
            or _FUTURE_OR_QUESTION.search(clause)
        ):
            continue
        for category, pattern, confidence in _PATTERNS:
            match = re.fullmatch(
                r"(?:actually,?\s*|correction:?\s*)?(" + pattern + r")",
                clause,
                re.IGNORECASE,
            )
            if match:
                facts[category] = {
                    "fact_key": "farmer_report:" + category,
                    "statement": match.group(1).strip()[:1000],
                    "confidence": confidence,
                    "kind": "explicit_farmer_report",
                    "not_authorization": True,
                    "independently_verified": False,
                }
                break
    return list(facts.values())
