"""Conservative workflow hints and execution receipts for explicit user requests.

Hints expose relevant tools; they never supply arguments, authorize writes, or
interpret uploaded/source text. Receipts prevent a prose-only answer from passing
as execution of an explicitly requested deliverable.
"""

import re
from decimal import Decimal, InvalidOperation

FORMATS = {
    "xlsx": r"\b(?:xlsx|excel|spreadsheet|workbook|sheet)\b",
    "docx": r"\b(?:docx|word|word document|word file)\b",
    "pdf": r"\b(?:pdf|printable report|printable copy)\b",
    "csv": r"\bcsv\b",
    "pptx": r"\b(?:pptx|powerpoint|slide deck)\b",
}


def infer(text):
    text = text.lower().split("selected uploaded attachments")[0]
    skills, reads = [], []

    def add(skill, tool=None):
        if skill not in skills:
            skills.append(skill)
        if tool and tool not in reads:
            reads.append(tool)

    # Capability questions mention many features without requesting each one.
    capabilities = bool(
        re.search(r"what can you|what do you do|kya (?:kar|karta)|capabilit", text)
    )
    if capabilities:
        reads.append("assistant_capabilities")
    creation = r"create|generate|export|downloadable|make|prepare|put|turn|give|bana\w*|banao|convert|revise|update|draft"
    operations = list(
        re.finditer(
            r"\b(?:" + creation + r"|read|open|attached|uploaded|from|using)\b", text
        )
    )
    formats = []
    for fmt, pattern in FORMATS.items():
        for mention in re.finditer(pattern, text):
            before = [
                operation
                for operation in operations
                if operation.end() <= mention.start()
            ]
            operation = before[-1] if before else None
            creates = bool(operation and re.fullmatch(creation, operation.group()))
            # Hindi commonly places the verb after the object: "PDF bana do".
            creates = creates or bool(
                re.match(r"\s+(?:bana\w*|banao)\b", text[mention.end() :])
            )
            prefix = (
                text[max(0, operation.start() - 12) : operation.start()]
                if operation
                else ""
            )
            negated = bool(re.search(r"(?:do not|don't|never)\s*$", prefix))
            if (
                creates
                and not negated
                and not re.match(r"\s+mat bana", text[mention.end() :])
            ):
                formats.append(fmt)
                break
    if formats:
        add(
            "spreadsheets"
            if any(f in formats for f in ("xlsx", "csv"))
            else "documents"
        )
        if any(f in formats for f in ("pdf", "docx")):
            add("documents")
        if "pptx" in formats:
            add("presentations")
    if not capabilities:
        if re.search(r"budget|cost breakdown|kharcha|kharch|lagat|hisab", text):
            add(
                "farm-budget",
                "calculate_budget"
                if re.search(r"\d", text)
                and re.search(r"unit|each|bags? at|per bag|cost chart|total", text)
                else None,
            )
        if re.search(r"net proceeds|net sale|take.home|commission", text):
            add("sale-planning", "net_sale")
        if re.search(
            r"\b(?:mandi|market|markets|price trend|prices|bhav|daam)\b", text
        ):
            trend = bool(re.search(r"\btrend|history|historical", text))
            add("market-prices", "market_trend" if trend else "market_prices")
            if trend and re.search(
                r"\bcompare\b[^.!?;]{0,60}\b(?:markets?|prices?|mandis?|quotes?)\b",
                text,
            ):
                add("market-prices", "market_prices")
        if re.search(
            r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|season|rabi|kharif|winter|summer|monsoon|next crop)\b",
            text,
        ) and re.search(r"grow|sow|crop|chana|wheat|fasal|ugau|bona|plan", text):
            add("crop-calendar", "seasonal_planning_context")
        if re.search(r"\b(?:exchange|sprayer|barter|labour offers)\b", text):
            add("farmer-exchange", "exchange_listings")
        if re.search(
            r"\b(?:diagnos\w*|disease|yellow spots|leaf curl|patte|pest|spots on leaves|leaves? (?:are )?(?:turning |looking |look )?yellow)\b",
            text,
        ):
            add("crop-scouting")
    # Match the action's object, not a task word elsewhere in a file request.
    # "Create Excel ... do not save any task" must never imply a calendar write.
    create_task = re.search(
        r"\b(?:create|save|add|schedule)\s+(?:(?:one|a|an|the|new|two|any|\d+)\s+)?(?:calendar\s+)?(?:task|tasks|reminder)\b",
        text,
    )
    if create_task and not capabilities:
        prefix = text[max(0, create_task.start() - 12) : create_task.start()]
        if not re.search(r"(?:do not|don't|never)\s*$", prefix) and not re.search(
            r"\bsave mat\b", text
        ):
            add("farm-records", "save_task")
    edit_task = re.search(r"\b(?:move|reschedule|update|edit|delete|remove)\b", text)
    if edit_task and not capabilities:
        suffix = text[edit_task.end() :]
        prefix = text[max(0, edit_task.start() - 12) : edit_task.start()]
        targets_calendar = re.search(r"\b(?:calendar task|task|tasks)\b", suffix) or (
            edit_task.group() in ("move", "reschedule")
            and re.search(r"\d{4}-\d{2}-\d{2}", suffix)
        )
        if targets_calendar and not re.search(r"(?:do not|don't|never)\s*$", prefix):
            add("farm-records", "list_tasks")
            add(
                "farm-records",
                "delete_task"
                if edit_task.group() in ("delete", "remove")
                else "update_task",
            )
    if re.search(
        r"(?:check|read|show|list|review|dekho|what|kaunse).*\b(?:saved|my|mere)\b.*\b(?:tasks|work|kaam)\b|\b(?:my|mere)\b.*\b(?:pending|due|kaunse)\b.*\b(?:tasks|work|kaam)\b|\b(?:my|mere)\b.*\b(?:tasks|work|kaam)\b.*\b(?:dekh|check|review)\w*",
        text,
    ):
        add("farm-records", "list_tasks")
    if re.search(
        r"(?:check|read|show|list|review|dekho|what|kitna).*\b(?:saved|my|mere|ab tak)\b.*\b(?:expenses|spent|kharcha)\b|\b(?:ab tak|my|mere)\b.*\b(?:kitna|how much)\b.*\b(?:spent|expenses|kharcha)\b|\b(?:my|mere)\b.*\b(?:kharcha|expenses)\b.*\b(?:dekh|check|review)\w*",
        text,
    ):
        add("farm-records", "list_expenses")
    return {"skills": skills, "reads": reads, "formats": formats}


def remaining(contract, messages):
    """Receipts from this request only, including its approval/question resumes."""
    results = {}
    calls = {}
    formats = set()
    for message in messages[contract.get("start", 0) :]:
        for call in message.get("tool_calls", []):
            calls[call["id"]] = call["function"]["name"]
        if message["role"] != "tool":
            continue
        import json

        try:
            result = json.loads(message.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        if (
            not isinstance(result, dict)
            or result.get("skipped")
            or result.get("interrupted")
        ):
            continue
        name = calls.get(message.get("tool_call_id"))
        results[name] = result
        artifact = result.get("artifact")
        if isinstance(artifact, dict) and artifact.get("file_id"):
            formats.add(artifact.get("format"))
    missing_reads = [name for name in contract["reads"] if name not in results]
    missing_formats = [fmt for fmt in contract["formats"] if fmt not in formats]
    return missing_reads, missing_formats


def language_instruction(messages, start=0, ui_language="en"):
    """Use the farmer's words for this request; fall back to the UI locale."""
    from skyview.languages import LANGUAGE_NAMES, preferred_language

    user_messages = [
        message.get("content", "").split("Selected uploaded attachments")[0]
        for message in messages[start:]
        if message.get("role") == "user"
    ]
    for content in reversed(user_messages):
        text = content.lower()
        if re.search(
            r"(?:reply|answer|respond|speak) in english|in english\s*:", text
        ):
            return "Reply in English, including questions and document prose, as explicitly requested."
        if re.search(
            r"hinglish|roman (?:hindi|letters|script)|hindi.*english letters", text
        ):
            return "Reply in natural Hinglish (Hindi mixed with English), written in Latin/Roman letters, including questions, choices, headings and document prose. Do not answer entirely in English or Devanagari. This explicit user preference overrides the UI language."
    script_languages = (
        (r"[\u0980-\u09ff]", "Bengali"),
        (r"[\u0a00-\u0a7f]", "Punjabi"),
        (r"[\u0a80-\u0aff]", "Gujarati"),
        (r"[\u0b00-\u0b7f]", "Odia"),
        (r"[\u0b80-\u0bff]", "Tamil"),
        (r"[\u0c00-\u0c7f]", "Telugu"),
        (r"[\u0c80-\u0cff]", "Kannada"),
        (r"[\u0d00-\u0d7f]", "Malayalam"),
        (r"[\u0600-\u06ff]", "Urdu"),
    )
    for content in reversed(user_messages):
        for script, name in script_languages:
            if re.search(script, content):
                return f"Reply in {name} using the same script as the farmer's message, including questions, choices, headings and final answer."
        if re.search(r"[\u0900-\u097f]", content):
            locale = preferred_language(ui_language)
            name = LANGUAGE_NAMES[locale] if locale in {"hi", "mr", "ne", "sa", "kok", "mai", "doi"} else "Hindi"
            return f"Reply in {name} using Devanagari, including questions, choices, headings and final answer."
        words = re.findall(r"[a-z]+", content.lower())
        roman_hindi = {"mujhe", "mere", "meri", "mera", "batao", "bata", "kya", "kaise", "karo", "karna", "chahiye", "nahi", "hain", "hai", "fasal", "khet", "bhav", "daam", "kitna", "kitne", "lagao", "banao", "dikhao", "dekh", "wala"}
        if len(set(words) & roman_hindi) >= 2:
            return "Reply in natural Hinglish using Latin/Roman letters, matching the farmer's wording. Write questions, choices, headings and the final answer in Hinglish, including after tool calls."
        english_words = {"what", "which", "when", "where", "how", "can", "could", "should", "please", "tell", "show", "explain", "compare", "make", "create", "give", "help", "about", "with", "for", "the", "my", "me", "prices", "weather"}
        if len(words) >= 3 and len(set(words) & english_words) >= 2:
            return "Reply in English, matching the farmer's current English question. Write questions, choices, headings and the final answer in English even if the interface is set to another language."
    return ""


def public_text(text, messages):
    """File downloads use authenticated UI cards, never model-invented URLs."""
    import json

    identifiers = set()
    names = set()
    for message in messages:
        if message["role"] != "tool":
            continue
        try:
            data = json.loads(message.get("content", "{}"))
        except (TypeError, ValueError):
            continue
        artifact = data.get("artifact") if isinstance(data, dict) else None
        if isinstance(artifact, dict):
            identifiers.update(
                str(artifact[k]) for k in ("id", "file_id") if artifact.get(k)
            )
            names.update(
                str(artifact[k]).lower()
                for k in ("title", "filename")
                if artifact.get(k)
            )

    def link(match):
        label, url = match.group(1), match.group(2)
        if label.lower() in names or any(
            identifier in url for identifier in identifiers
        ):
            return label
        return match.group(0)

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)

    def chart(match):
        try:
            data = json.loads(match.group(1))
        except ValueError:
            return match.group(0)
        return (
            ""
            if isinstance(data, dict) and "points" in data and "title" in data
            else match.group(0)
        )

    text = re.sub(r"```(?:json)?\s*([\s\S]*?)```", chart, text)
    for tool, label in (
        ("list_tasks", "saved tasks"),
        ("list_expenses", "expense ledger"),
        ("market_prices", "market lookup"),
        ("seasonal_planning_context", "crop planning"),
    ):
        text = re.sub(r"\b" + tool + r"\b", label, text)
    return text.strip()


def artifact_receipts(contract, messages):
    import json

    receipts = []
    for message in messages[contract.get("start", 0) :]:
        if message["role"] != "tool":
            continue
        try:
            result = json.loads(message.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        artifact = result.get("artifact") if isinstance(result, dict) else None
        if isinstance(artifact, dict) and artifact.get("file_id"):
            receipts.append(
                {
                    key: artifact.get(key)
                    for key in (
                        "title",
                        "filename",
                        "format",
                        "section_titles",
                        "row_count",
                    )
                }
            )
    return receipts


def unverified_file_claims(text, receipts, known_names=()):
    names = {str(receipt.get("filename", "")).casefold() for receipt in receipts}
    names.update(str(name).casefold() for name in known_names)
    # Markdown-emphasized filenames and file-link labels are common completion
    # claims. Inspect exact names, leaving ordinary source citations untouched.
    claims = re.findall(
        r"(?<!\w)[*`\[]+([^*`\]\n]+\.(?:xlsx|docx|pdf|csv|pptx))(?=[*`\]])",
        text,
        re.IGNORECASE,
    )
    return [claim for claim in claims if claim.casefold() not in names]


def validate_seasonal_draft(arguments, contract):
    """A conditional seasonal draft must not become an unsourced dose sheet.

    Numerical lab reports and farmer-entered budgets have separate read/report
    workflows. This guard applies only to generated crop-calendar documents.
    """
    if "crop-calendar" not in contract.get("skills", []):
        return
    text = "\n".join(
        section.get("text", "") for section in arguments.get("sections", [])
    )
    chemical_rate = re.compile(
        r"\d(?:[\d.,–—−‑\- ]*)\s*(?:kg|g|ml|litres?|liters?)\s*(?:/|per\s+)\s*(?:acre|ha|hectare)",
        re.IGNORECASE,
    )
    water_rate = re.compile(
        r"\d(?:[\d.,–—−‑\- ]*)\s*mm\s*(?:/|per\s+)\s*(?:day|week)", re.IGNORECASE
    )
    for line in text.splitlines():
        if (
            chemical_rate.search(line)
            and re.search(
                r"urea|dap\b|fertili[sz]|pesticide|insecticide|fungicide",
                line,
                re.IGNORECASE,
            )
        ) or water_rate.search(line):
            raise ValueError(
                "This conditional seasonal draft contains an unverified fertilizer, pesticide or irrigation rate. Remove numeric application doses; compare relative water needs and include soil-test/local-adviser checks instead. Do not replace them with other guessed doses."
            )


def unsupported_seasonal_claims(answer, contract, messages):
    """Catch precise input/water claims in an unsourced crop-choice answer."""
    if "crop-calendar" not in contract.get("skills", []):
        return []
    calls = {}
    for message in messages[contract.get("start", 0) :]:
        for call in message.get("tool_calls", []):
            calls[call["id"]] = call["function"]["name"]
        if (
            message.get("role") != "tool"
            or calls.get(message.get("tool_call_id")) != "seasonal_planning_context"
        ):
            continue
        import json

        try:
            if json.loads(message.get("content", "{}")).get("references"):
                return []
        except (ValueError, TypeError, AttributeError):
            pass
    patterns = (
        r"\b\d[\d.,–—−‑\- ]*\s*mm\b",
        r"\b\d[\d.,–—−‑\- ]*\s*days?\b",
        r"(?:₹|INR\s*)\s*\d[\d.,–—−‑\- ]*\s*(?:per\s+|/\s*)(?:kg|acre|hectare|bag)\b",
        r"\b\d[\d.,–—−‑\- ]*\s*(?:kg|g|ml|litres?|liters?)\s*(?:/|per\s+)(?:acre|ha|hectare)\b",
    )
    return [
        match.group()
        for pattern in patterns
        for match in re.finditer(pattern, answer, re.IGNORECASE)
    ]


def unsupported_record_claims(answer, contract, messages):
    """Check simple factual claims against owned read results before publishing."""
    import json

    calls = {}
    results = {}
    for message in messages[contract.get("start", 0) :]:
        for call in message.get("tool_calls", []):
            calls[call["id"]] = call["function"]["name"]
        if message.get("role") != "tool":
            continue
        try:
            results[calls.get(message.get("tool_call_id"))] = json.loads(
                message.get("content", "{}")
            )
        except (ValueError, TypeError):
            continue
    issues = []
    if "list_expenses" in results and not re.search(
        r"\b(?:expense|expenses|kharcha|spend|spent)\b",
        answer,
        re.IGNORECASE,
    ):
        issues.append(
            "The farmer asked about spending; include the recorded expense count and dated total."
        )
    if "list_tasks" in results and not re.search(
        r"\b(?:tasks?|kaam|work|reminders?)\b",
        answer,
        re.IGNORECASE,
    ):
        issues.append(
            "The farmer asked about work; include actual pending task titles and due dates."
        )
    tasks = results.get("list_tasks", {}).get("tasks", [])
    pending_titles = {
        str(item.get("title", ""))
        for item in tasks
        if not item.get("completed") and not item.get("deleted") and item.get("title")
    }
    if pending_titles and not any(
        re.search(r"\b" + re.escape(title) + r"\b", answer, re.IGNORECASE)
        for title in pending_titles
    ):
        issues.append("The answer omitted the actual pending task titles.")
    if re.search(r"\b[0-9a-f]{32}\b|\bTask ID\b", answer, re.IGNORECASE):
        issues.append(
            "Do not display internal record identifiers; use task titles and due dates."
        )
    if re.search(r"\bDemo plan\b|\bDemo farm expense\b", answer, re.IGNORECASE):
        issues.append(
            "Do not quote internal fixture notes or generic ledger descriptions; summarize the actual task and amount."
        )
    expenses = results.get("list_expenses", {}).get("expenses", [])
    if expenses:
        if len(expenses) > 3 and re.search(
            r"(?:only|all) (?:the )?(?:expense|spend) rows|no other (?:entries|expenses) (?:are )?stored|koi aur (?:expense|kharcha).{0,50}(?:nahi|nahin)",
            answer,
            re.IGNORECASE,
        ):
            issues.append(
                f"Expense list contains {len(expenses)} rows; do not claim a displayed subset is complete."
            )
        total = sum(Decimal(str(item.get("amount", 0))) for item in expenses)
        claimed = re.search(
            r"total recorded (?:spend|expense|kharcha)[^\d₹]{0,30}₹?\s*([\d,]+(?:\.\d+)?)",
            answer,
            re.IGNORECASE,
        )
        if claimed:
            try:
                value = Decimal(claimed.group(1).replace(",", ""))
                if abs(value - total) > Decimal(1):
                    issues.append(
                        f"Claimed all-time total {value} does not equal {total} across {len(expenses)} returned expense rows. State a dated subset if summarizing only some rows."
                    )
            except InvalidOperation:
                pass
    context = results.get("seasonal_planning_context", {}).get("farm_context", {})
    user_text = " ".join(
        str(message.get("content", ""))
        for message in messages[contract.get("start", 0) :]
        if message.get("role") == "user"
    )
    if (
        context.get("soil_texture") in (None, "unknown")
        and re.search(r"\bloam\b", answer, re.IGNORECASE)
        and not re.search(r"\bloam\b", user_text, re.IGNORECASE)
    ):
        issues.append(
            "Farm soil texture is unknown; do not claim loam as a known farm fact."
        )
    market_rows = results.get("market_prices", {}).get("records", [])
    if market_rows and re.search(
        r"\bno dated (?:market|mandi|price) (?:data|records)\b"
        r"|\bno (?:matching )?(?:market|mandi|price) (?:data|records) (?:is|are) available\b",
        answer,
        re.IGNORECASE,
    ):
        issues.append(
            "Dated market records were returned. Do not say no dated data exists; distinguish planning records from reported observations."
        )
    priced_crops = {
        str(row.get("commodity", "")).casefold()
        for row in market_rows
        if isinstance(row, dict)
    }
    comparable_prices = bool(priced_crops & {"chana", "chickpea", "gram"}) and bool(
        priced_crops & {"wheat", "gehu"}
    )
    for line in answer.splitlines():
        if (
            not comparable_prices
            and re.search(r"\b(?:price|bhav|rate)\b", line, re.IGNORECASE)
            and re.search(r"\b(?:chana|chickpea)\b", line, re.IGNORECASE)
            and re.search(r"\b(?:gehu|wheat)\b", line, re.IGNORECASE)
            and re.search(
                r"\b(?:kam|zyada|higher|lower|more|less)\b", line, re.IGNORECASE
            )
        ):
            issues.append(
                "No comparable chickpea and wheat prices were returned; do not rank their prices."
            )
            break
    return issues


def verified_summary(contract, messages, *, hinglish=False):
    """Small evidence-only answer if a model repeatedly misstates read results."""
    import json

    calls = {}
    results = {}
    for message in messages[contract.get("start", 0) :]:
        for call in message.get("tool_calls", []):
            calls[call["id"]] = call["function"]["name"]
        if message.get("role") != "tool":
            continue
        try:
            results[calls.get(message.get("tool_call_id"))] = json.loads(
                message.get("content", "{}")
            )
        except (ValueError, TypeError):
            pass
    lines = []
    tasks = results.get("list_tasks", {}).get("tasks")
    if isinstance(tasks, list):
        pending = [
            item
            for item in tasks
            if not item.get("completed") and not item.get("deleted")
        ]
        lines.append(
            ("Pending kaam:" if hinglish else "Pending tasks:")
            + (
                " "
                + "; ".join(
                    f"{item.get('title', 'Task')} ({item.get('due_date', 'date unknown')})"
                    for item in pending[:5]
                )
                if pending
                else " none recorded."
            )
        )
        if len(pending) > 5:
            lines.append(f"{len(pending)} pending tasks in total.")
    expenses = results.get("list_expenses", {}).get("expenses")
    if isinstance(expenses, list):
        try:
            total = sum(Decimal(str(item.get("amount", 0))) for item in expenses)
            dates = sorted(
                str(item.get("date")) for item in expenses if item.get("date")
            )
            period = f" ({dates[0]} to {dates[-1]})" if dates else ""
            lines.append(
                ("Recorded kharcha" if hinglish else "Recorded expenses")
                + f": {len(expenses)} entries{period}, total INR {total:,.2f}."
            )
        except (InvalidOperation, TypeError):
            lines.append(f"{len(expenses)} recorded expense entries.")
    market = results.get("market_prices")
    if isinstance(market, dict):
        rows = market.get("records") or market.get("rates") or []
        if rows:
            row = rows[0]
            lines.append(
                f"Market record: {row.get('commodity', 'crop')} at {row.get('market', 'market')}, "
                f"{row.get('state', 'state')} on {row.get('arrival_date', 'date unknown')}: "
                f"{row.get('modal_price', 'unknown')} {row.get('unit', 'INR/quintal')} "
                f"({row.get('source', row.get('data_origin', 'source unknown'))}). "
                "Check the source and date before a sale decision."
            )
        else:
            lines.append("No matching market price was returned for this request.")
    seasonal = results.get("seasonal_planning_context")
    if isinstance(seasonal, dict):
        farm = seasonal.get("farm_context") or {}
        water = str(farm.get("water_availability", "unknown")).lower()
        if water in {"low", "limited"}:
            lines.append(
                "With limited water, chickpea may be a lower-water option than wheat. "
                "Confirm local variety, soil and reliable irrigation before sowing."
            )
        else:
            lines.append(
                "Crop choice is provisional; confirm local variety, soil and reliable irrigation before sowing."
            )
    files = artifact_receipts(contract, messages)
    if files:
        lines.append(
            "Created files: "
            + ", ".join(
                str(item.get("filename") or item.get("title")) for item in files
            )
            + "."
        )
    missing_reads, missing_formats = remaining(contract, messages)
    friendly = {
        "seasonal_planning_context": "crop planning",
        "market_prices": "market prices",
        "market_trend": "market trend",
        "list_tasks": "saved tasks",
        "list_expenses": "recorded expenses",
        "calculate_budget": "budget calculation",
        "weather_forecast": "weather outlook",
        "weather_archive": "weather history",
        "exchange_listings": "exchange listings",
    }
    unfinished = [friendly.get(item, "a requested lookup") for item in missing_reads]
    unfinished.extend(f"{item.upper()} file" for item in missing_formats)
    if unfinished:
        lines.append(
            "Still unfinished: "
            + ", ".join(dict.fromkeys(unfinished))
            + ". You can retry this part."
        )
    return (
        "\n\n".join(lines) or "The completed results are available in the cards below."
    )
