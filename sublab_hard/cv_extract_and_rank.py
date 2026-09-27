import json
import os
from pathlib import Path

from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CANDIDATES = DATA / "candidates"
MODEL = "gpt-5.6-luna"

RUBRIC = json.loads(
    (DATA / "candidate_rubric.json").read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------

EVIDENCE_VALUE = {
    "oneOf": [
        {"type": "string"},
        {
            "type": "array",
            "items": {"type": "string"},
        },
        {"type": "null"},
    ]
}

CV_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_id": {
            "type": ["string", "null"]
        },
        "full_name": {
            "type": ["string", "null"]
        },
        "degree": {
            "type": ["string", "null"]
        },
        "graduation_year": {
            "type": ["integer", "null"]
        },
        "gpa": {
            "type": "object",
            "properties": {
                "gpa_4_scale": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 4,
                },
                "original_value": {
                    "type": ["number", "null"]
                },
                "original_scale": {
                    "type": ["number", "null"]
                },
            },
            "required": [
                "gpa_4_scale",
                "original_value",
                "original_scale",
            ],
            "additionalProperties": False,
        },
        "languages": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "published_peer_reviewed_outputs": {
            "type": "integer",
            "minimum": 0,
        },
        "other_publication_statuses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["status", "evidence"],
                "additionalProperties": False,
            },
        },
        "relevant_experience_months": {
            "type": "integer",
            "minimum": 0,
        },
        "uncountable_experience": {
            "type": "array",
            "items": {"type": "string"},
        },
        "evidence": {
            "type": "object",
            "properties": {
                "candidate_id": EVIDENCE_VALUE,
                "full_name": EVIDENCE_VALUE,
                "degree": EVIDENCE_VALUE,
                "graduation_year": EVIDENCE_VALUE,
                "gpa": EVIDENCE_VALUE,
                "languages": EVIDENCE_VALUE,
                "published_outputs": EVIDENCE_VALUE,
                "experience": EVIDENCE_VALUE,
            },
            "required": [
                "candidate_id",
                "full_name",
                "degree",
                "graduation_year",
                "gpa",
                "languages",
                "published_outputs",
                "experience",
            ],
            "additionalProperties": False,
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "claims": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                },
                "required": ["field", "claims"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "candidate_id",
        "full_name",
        "degree",
        "graduation_year",
        "gpa",
        "languages",
        "published_peer_reviewed_outputs",
        "other_publication_statuses",
        "relevant_experience_months",
        "uncountable_experience",
        "evidence",
        "ambiguities",
    ],
    "additionalProperties": False,
}

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        criterion["id"]: {
            "type": "number",
            "minimum": 0,
            "maximum": 5,
        }
        for criterion in RUBRIC["criteria"]
    },
    "required": [
        criterion["id"]
        for criterion in RUBRIC["criteria"]
    ],
    "additionalProperties": False,
}

CV_VALIDATOR = Draft202012Validator(CV_SCHEMA)
SCORE_VALIDATOR = Draft202012Validator(SCORE_SCHEMA)


# ---------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------

def client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")

    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    return OpenAI(api_key=key)


def call_model(system: str, user: str) -> str:
    response = client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    return response.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    decoder = json.JSONDecoder()

    for i, char in enumerate(text):
        if char != "{":
            continue

        try:
            value, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            return value

    raise ValueError("No JSON object found in model response.")


# ---------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------

def extraction_prompt() -> str:
    return f"""
You extract structured CV records from scholarship application stories.

Return exactly one JSON object matching this schema:

{json.dumps(CV_SCHEMA, ensure_ascii=False)}

RULES

1. SOURCE
- Use only facts explicitly stated in the supplied story.
- Never use outside knowledge.
- Never infer or estimate missing facts.
- If a fact is not stated, return null.

2. GPA
- Preserve the original GPA value and original scale.
- If the GPA uses another numeric scale, convert it proportionally to 4.0.
- If no GPA is stated, gpa_4_scale, original_value and original_scale
  must all be null.
- Never estimate GPA from the degree, university, distinction, wording,
  or general impression.

3. PUBLICATIONS
- Count an output as published only if the story explicitly says
  published or accepted.
- In preparation, submitted, under review, planned and in press
  are NOT published.
- Record those separately in other_publication_statuses.
- Do not count posters or other outputs as published peer-reviewed work
  unless the story explicitly establishes that they meet that definition.

4. EXPERIENCE
- Count months, not jobs.
- Overlapping periods count only once.
- A period without dates is not countable.
- Put relevant but undated experience in uncountable_experience.
- Do not invent start or end dates.

5. CONTRADICTIONS
- Never resolve contradictory claims.
- Never choose the more plausible value.
- Never average conflicting numbers.
- Set the contradicted field to null.
- Copy both conflicting claims into ambiguities.

6. EVIDENCE
- Evidence must be copied verbatim from the supplied story.
- Do not paraphrase or rewrite evidence.
- One quote may support several extracted values.
- Evidence may therefore be either one string or an array of strings.
- Every non-null extracted field must have supporting evidence.
- If the extracted field is null, its evidence may be null.
- Ambiguity claims must also be copied from the story.

7. COUNTS
- published_peer_reviewed_outputs and relevant_experience_months are
  computed only from explicit story evidence and the rules above.

Return JSON only.
Do not add commentary before or after the JSON.
""".strip()


def extract_cv(story: str) -> tuple[dict | None, str]:
    raw = call_model(
        extraction_prompt(),
        story,
    )

    try:
        return parse_json(raw), raw
    except ValueError:
        return None, raw


# ---------------------------------------------------------------------
# Extraction validation
# ---------------------------------------------------------------------

def validation_errors(
    validator: Draft202012Validator,
    value: dict | None,
) -> list[str]:

    if value is None:
        return ["Response did not parse as a JSON object."]

    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: list(error.path),
    )

    result = []

    for error in errors:
        path = ".".join(
            str(part)
            for part in error.path
        ) or "<root>"

        result.append(
            f"{path}: {error.message}"
        )

    return result


def normalize_quote(text: str) -> str:
    """
    Ignore formatting differences such as line breaks and case,
    but still require the model's evidence words to exist in the story.
    """
    return " ".join(
        text.split()
    ).casefold()


def evidence_quotes(cv: dict) -> list[str]:
    quotes = []

    for value in cv["evidence"].values():
        if isinstance(value, str):
            quotes.append(value)

        elif isinstance(value, list):
            quotes.extend(
                item
                for item in value
                if isinstance(item, str)
            )

    for item in cv["other_publication_statuses"]:
        evidence = item.get("evidence")

        if isinstance(evidence, str):
            quotes.append(evidence)

    quotes.extend(
        item
        for item in cv["uncountable_experience"]
        if isinstance(item, str)
    )

    for ambiguity in cv["ambiguities"]:
        quotes.extend(ambiguity["claims"])

    return [
        quote
        for quote in quotes
        if quote.strip()
    ]


def invalid_evidence(
    cv: dict,
    story: str,
) -> list[str]:

    source = normalize_quote(story)

    return [
        quote
        for quote in evidence_quotes(cv)
        if normalize_quote(quote) not in source
    ]


def has_evidence(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, list):
        return any(
            isinstance(item, str) and item.strip()
            for item in value
        )

    return False


def missing_evidence(cv: dict) -> list[str]:
    """
    Check that every important non-null value has supporting evidence.
    """
    evidence = cv["evidence"]
    missing = []

    direct = (
        "candidate_id",
        "full_name",
        "degree",
        "graduation_year",
        "languages",
    )

    for field in direct:
        if (
            cv[field] is not None
            and not has_evidence(evidence[field])
        ):
            missing.append(field)

    if (
        cv["gpa"]["gpa_4_scale"] is not None
        and not has_evidence(evidence["gpa"])
    ):
        missing.append("gpa")

    if (
        cv["published_peer_reviewed_outputs"] > 0
        and not has_evidence(
            evidence["published_outputs"]
        )
    ):
        missing.append(
            "published_peer_reviewed_outputs"
        )

    if (
        cv["relevant_experience_months"] > 0
        and not has_evidence(
            evidence["experience"]
        )
    ):
        missing.append(
            "relevant_experience_months"
        )

    return missing


def null_fields(cv: dict) -> list[str]:
    nulls = []

    for field in (
        "candidate_id",
        "full_name",
        "degree",
        "graduation_year",
        "languages",
    ):
        if cv[field] is None:
            nulls.append(field)

    if cv["gpa"]["gpa_4_scale"] is None:
        nulls.append("gpa_4_scale")

    return nulls


def trap_labels(cv: dict) -> list[str]:
    traps = []
    gpa = cv["gpa"]

    if (
        gpa["gpa_4_scale"] is not None
        and gpa["original_scale"] not in (None, 4, 4.0)
    ):
        traps.append("gpa_conversion")

    if cv["other_publication_statuses"]:
        traps.append("non_published_outputs")

    if cv["uncountable_experience"]:
        traps.append("uncountable_experience")

    if cv["ambiguities"]:
        traps.append("contradiction")

    if null_fields(cv):
        traps.append("missing_information")

    return traps


# ---------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------

def scoring_prompt() -> str:
    return f"""
Score one scholarship candidate using only the supplied structured CV.

RUBRIC:

{json.dumps(RUBRIC, ensure_ascii=False, indent=2)}

Return exactly one JSON object matching:

{json.dumps(SCORE_SCHEMA)}

RULES

- Return exactly one 0-5 score for each rubric criterion.
- Scores may be integers or decimals.
- Use only information present in the structured CV.
- Respect every counting rule in the rubric.
- Never reconstruct a field that extraction marked null.
- Never resolve a contradiction yourself.
- Do not compute the weighted total.
- Do not rank candidates.
- Do not select a winner.
- Do not add explanations or extra fields.

Return JSON only.
""".strip()


def score_cv(cv: dict) -> tuple[dict | None, str]:
    raw = call_model(
        scoring_prompt(),
        json.dumps(
            cv,
            ensure_ascii=False,
            indent=2,
        ),
    )

    try:
        return parse_json(raw), raw
    except ValueError:
        return None, raw


def weighted_total(scores: dict) -> float:
    weights = {
        criterion["id"]: criterion["weight"]
        for criterion in RUBRIC["criteria"]
    }

    total = sum(
        scores[criterion_id] * weight
        for criterion_id, weight
        in weights.items()
    )

    return round(total, 2)


# ---------------------------------------------------------------------
# Separate qualitative winner
# ---------------------------------------------------------------------

def prose_winner(
    candidates: list[dict],
) -> str:

    system = """
You are reviewing candidates for one funded scholarship.

Use only the supplied structured CVs and rubric.

Give a short prose recommendation naming which candidate you think should
receive the scholarship and why.

This is deliberately separate from the deterministic ranking performed
by Python.

Do not claim that your recommendation is the program's computed winner.
""".strip()

    user = json.dumps(
        {
            "rubric": RUBRIC,
            "candidates": candidates,
        },
        ensure_ascii=False,
        indent=2,
    )

    return call_model(system, user)


# ---------------------------------------------------------------------
# Input files
# ---------------------------------------------------------------------

def load_stories() -> list[tuple[str, str]]:
    files = sorted(
        CANDIDATES.glob("story-*.md")
    )

    if not files:
        raise RuntimeError(
            "No candidate stories found in data/candidates/"
        )

    return [
        (
            path.name,
            path.read_text(encoding="utf-8"),
        )
        for path in files
    ]


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    extracted = []
    ranking = []

    print("### Extraction")
    print(
        "| Story | Parsed | Schema | Evidence | "
        "Null fields | Traps |"
    )
    print(
        "|---|---|---|---|---|---|"
    )

    for filename, story in load_stories():
        source_id = Path(filename).stem

        cv, raw = extract_cv(story)

        parsed = cv is not None

        schema_errors = validation_errors(
            CV_VALIDATOR,
            cv,
        )

        schema_ok = (
            parsed
            and not schema_errors
        )

        if schema_ok:
            bad_quotes = invalid_evidence(
                cv,
                story,
            )

            evidence_missing = missing_evidence(
                cv
            )
        else:
            bad_quotes = []
            evidence_missing = []

        evidence_ok = (
            schema_ok
            and not bad_quotes
            and not evidence_missing
        )

        nulls = (
            null_fields(cv)
            if schema_ok
            else []
        )

        traps = (
            trap_labels(cv)
            if schema_ok
            else []
        )

        print(
            f"| {filename} "
            f"| {'yes' if parsed else 'no'} "
            f"| {'yes' if schema_ok else 'no'} "
            f"| {'yes' if evidence_ok else 'no'} "
            f"| {', '.join(nulls) if nulls else 'none'} "
            f"| {', '.join(traps) if traps else 'none'} |"
        )

        if schema_errors:
            print(
                f"\n[{filename}] SCHEMA ERRORS"
            )

            for error in schema_errors:
                print(f"  - {error}")

        if bad_quotes:
            print(
                f"\n[{filename}] UNMATCHED EVIDENCE"
            )

            for quote in bad_quotes:
                print(f"  - {quote!r}")

        if evidence_missing:
            print(
                f"\n[{filename}] MISSING EVIDENCE"
            )

            for field in evidence_missing:
                print(f"  - {field}")

        record = {
            "source_id": source_id,
            "story": filename,
            "parsed": parsed,
            "schema_valid": schema_ok,
            "evidence_valid": evidence_ok,
            "schema_errors": schema_errors,
            "unmatched_evidence": bad_quotes,
            "missing_evidence": evidence_missing,
            "null_fields": nulls,
            "traps": traps,
            "raw_extraction": raw,
            "cv": cv,
        }

        extracted.append(record)

        # Only a fully valid extraction is scored.
        if not (
            schema_ok
            and evidence_ok
        ):
            continue

        scores, raw_scores = score_cv(cv)

        score_errors = validation_errors(
            SCORE_VALIDATOR,
            scores,
        )

        score_valid = (
            scores is not None
            and not score_errors
        )

        scoring = {
            "raw": raw_scores,
            "scores": scores,
            "valid": score_valid,
            "errors": score_errors,
        }

        record["scoring"] = scoring

        if not score_valid:
            print(
                f"\n[{filename}] SCORE ERRORS"
            )

            for error in score_errors:
                print(f"  - {error}")

            continue

        ranking.append({
            "source_id": source_id,
            "story": filename,
            "candidate_id": cv["candidate_id"],
            "full_name": cv["full_name"],
            "scores": scores,
            "weighted_total": weighted_total(
                scores
            ),
        })

    # -----------------------------------------------------------------
    # Ranking
    # -----------------------------------------------------------------

    ranking.sort(
        key=lambda row: row["weighted_total"],
        reverse=True,
    )

    print("\n### Ranking")

    print(
        "| Candidate | Academic | Research | "
        "Experience | Total |"
    )

    print(
        "|---|---:|---:|---:|---:|"
    )

    for row in ranking:
        scores = row["scores"]

        label = (
            row["candidate_id"]
            or row["source_id"]
        )

        print(
            f"| {label} "
            f"| {scores['academic']} "
            f"| {scores['research']} "
            f"| {scores['experience']} "
            f"| {row['weighted_total']:.2f} |"
        )

    winner = (
        ranking[0]
        if ranking
        else None
    )

    if winner:
        label = (
            winner["candidate_id"]
            or winner["source_id"]
        )

        print(
            "\nComputed winner: "
            f"{label} "
            f"({winner['weighted_total']:.2f})"
        )

        if len(ranking) >= 2:
            gap = round(
                ranking[0]["weighted_total"]
                - ranking[1]["weighted_total"],
                2,
            )

            print(
                "Top-two gap: "
                f"{gap:.2f}"
            )
    else:
        print(
            "\nNo valid ranking could be computed."
        )

    # -----------------------------------------------------------------
    # Prose comparison
    # -----------------------------------------------------------------

    valid_candidates = [
        {
            "source_id": row["source_id"],
            "story": row["story"],
            "cv": row["cv"],
        }
        for row in extracted
        if (
            row["schema_valid"]
            and row["evidence_valid"]
        )
    ]

    prose = (
        prose_winner(valid_candidates)
        if valid_candidates
        else "No valid candidates available."
    )

    print("\n### Prose winner")
    print(prose)

    # -----------------------------------------------------------------
    # Save result
    # -----------------------------------------------------------------

    output_dir = ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)

    result = {
        "extractions": extracted,
        "ranking": ranking,
        "computed_winner": winner,
        "top_two_gap": (
            round(
                ranking[0]["weighted_total"]
                - ranking[1]["weighted_total"],
                2,
            )
            if len(ranking) >= 2
            else None
        ),
        "prose_winner": prose,
    }

    (
        output_dir
        / "cv_ranking_results.json"
    ).write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\nwrote outputs/cv_ranking_results.json"
    )


if __name__ == "__main__":
    main()