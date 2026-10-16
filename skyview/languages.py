"""Canonical farmer language codes; provider coverage is reported separately."""

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "ne": "Nepali",
    "sa": "Sanskrit",
    "ks": "Kashmiri",
    "kok": "Konkani",
    "mai": "Maithili",
    "doi": "Dogri",
    "mni": "Manipuri",
    "sat": "Santali",
    "sd": "Sindhi",
    "bo": "Tibetan",
    "brx": "Bodo",
}


def normalize_language(value):
    code = str(value).strip().lower().replace("_", "-").split("-")[0]
    code = "or" if code == "od" else code
    if code not in LANGUAGE_NAMES:
        raise ValueError("Choose a supported language code")
    return code


def preferred_language(value):
    try:
        return normalize_language(value)
    except ValueError:
        return "en"


def speech_language(value):
    code = normalize_language(value)
    return ("od" if code == "or" else code) + "-IN"
