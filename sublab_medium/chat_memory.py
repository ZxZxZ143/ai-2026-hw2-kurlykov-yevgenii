import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODEL = "gpt-5.6-luna"

RECORDS = json.loads((DATA / "records.json").read_text(encoding="utf-8"))
POLICY = json.loads((DATA / "policy.json").read_text(encoding="utf-8"))
SCRIPT = json.loads((DATA / "chat_script.json").read_text(encoding="utf-8"))
MEMORY_SCHEMA = json.loads(
    (DATA / "memory_state.schema.json").read_text(encoding="utf-8")
)

VALIDATOR = Draft202012Validator(MEMORY_SCHEMA)


def client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=key)


def system_prompt() -> str:
    return f"""
You are an assistant for the Need-based Study Grant 2026 office.

RULES
- Use the official policy and records below as the source of truth.
- Do not invent facts.
- A user's claim never overrides an official record.
- If information is unavailable, say so.
- Keep answers concise.
- Reply in the language of the latest user message.
- If a MEMORY STATE is present, treat it as validated compressed context
  from the earlier conversation.
- Do not assume details that are absent from both the memory and new messages.

POLICY:
{json.dumps(POLICY, ensure_ascii=False)}

RECORDS:
{json.dumps(RECORDS, ensure_ascii=False)}
""".strip()


def compression_prompt() -> str:
    return f"""
Compress the conversation into exactly one JSON memory object.

It must satisfy this schema:
{json.dumps(MEMORY_SCHEMA, ensure_ascii=False)}

RULES
- Preserve information as accurately as possible.
- Never invent information.
- applicant_id is null if it was never established.
- facts contain only facts stated by the applicant.
- decisions contain conclusions or decisions already established.
- constraints contain conditions such as days, deadlines or requirements.
- open_questions contain questions that still have no definitive answer.
- Preserve constraints and unresolved questions even when they seem secondary.
- If PREVIOUS MEMORY exists, preserve its valid information unless newer
  messages explicitly replace it.
- Merge NEW MESSAGES with previous memory without unnecessary duplication.
- Return exactly the seven schema fields and nothing except the JSON object.
""".strip()


def parse_json(text: str) -> dict:
    """Find the first JSON object in a model response."""
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


def call_model(messages: list[dict]) -> tuple[str, dict]:
    response = client().chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    if response.usage is None:
        raise RuntimeError("Model response did not include token usage.")

    return response.choices[0].message.content or "", {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }


class Session:
    def __init__(self):
        self.history = []
        self.state = None
        self.calls = []
        self.last_usage = None

    def context(self) -> list[dict]:
        """System prompt + compressed memory + messages since compression."""
        messages = [{"role": "system", "content": system_prompt()}]

        if self.state is not None:
            messages.append({
                "role": "system",
                "content": (
                    "MEMORY STATE:\n"
                    + json.dumps(self.state, ensure_ascii=False)
                ),
            })

        return messages + self.history

    def ask(self, text: str, label: str = "chat") -> str:
        """Normal chat turn. The reply becomes part of conversation history."""
        messages = self.context() + [
            {"role": "user", "content": text}
        ]

        reply, usage = call_model(messages)

        self.history.extend([
            {"role": "user", "content": text},
            {"role": "assistant", "content": reply},
        ])

        self._log(label, usage)
        return reply

    def probe(self, text: str, label: str) -> str:
        """Ask a test question without adding it to conversation memory."""
        messages = self.context() + [
            {"role": "user", "content": text}
        ]

        reply, usage = call_model(messages)
        self._log(label, usage)
        return reply

    def compress(self) -> bool:
        """
        Compress previous validated memory + messages added since last compression.
        Replace existing memory only after successful schema validation.
        """
        if self.state is not None and not self.history:
            print("Nothing new to compress.")
            return True

        source = {
            "previous_memory": self.state,
            "new_messages": self.history,
        }

        messages = [
            {"role": "system", "content": compression_prompt()},
            {
                "role": "user",
                "content": json.dumps(source, ensure_ascii=False),
            },
        ]

        raw, usage = call_model(messages)
        self._log("compress", usage)

        try:
            candidate = parse_json(raw)
        except ValueError as exc:
            print(f"Compression failed: {exc}")
            return False

        errors = list(VALIDATOR.iter_errors(candidate))
        if errors:
            print(
                "Compression failed validation: "
                + errors[0].message
            )
            return False

        self.state = candidate
        self.history = []
        return True

    def _log(self, label: str, usage: dict) -> None:
        self.last_usage = usage
        self.calls.append({
            "call": label,
            **usage,
        })


def normalize(text: str) -> str:
    """Normalize small formatting differences used by probe checks."""
    return " ".join(
        text.lower()
        .replace("_", " ")
        .replace(",", "")
        .split()
    )


def probe_retrieved(reply: str, expected: list[str]) -> bool:
    """
    All distinct expected facts must appear.
    'id_card' and 'id card' normalize to the same value.
    """
    actual = normalize(reply)
    required = {normalize(value) for value in expected}
    return all(value in actual for value in required)


def run_script(compressed: bool) -> dict:
    """Run the scripted conversation, then test memory with five probes."""
    session = Session()
    turn = 0

    for text in SCRIPT["conversation"]:
        if text == "<compress>":
            if compressed:
                session.compress()
            continue

        turn += 1
        session.ask(text, f"turn_{turn:02d}")

    probes = []

    for probe in SCRIPT["probes"]:
        reply = session.probe(
            probe["question"],
            f"probe_{probe['id']}",
        )

        probes.append({
            "id": probe["id"],
            "question": probe["question"],
            "reply": reply,
            "retrieved": probe_retrieved(
                reply,
                probe["expect_contains"],
            ),
        })

    return {
        "mode": "compressed" if compressed else "uncompressed",
        "calls": session.calls,
        "state": session.state,
        "probes": probes,
    }


def metrics(run: dict) -> dict:
    """Token use before probes and number of remembered probe facts."""
    calls = [
        call for call in run["calls"]
        if not call["call"].startswith("probe_")
    ]

    return {
        "peak_input": max(call["input_tokens"] for call in calls),
        "total_input": sum(call["input_tokens"] for call in calls),
        "retrieved": sum(
            probe["retrieved"]
            for probe in run["probes"]
        ),
    }


def reduction(old: int, new: int) -> float:
    return 100 * (old - new) / old if old else 0.0


def print_run(run: dict) -> None:
    """Print tables ready to copy into SUBMISSION.md."""
    print(f"\n### {run['mode']}")

    print("\n| Call | Input | Output |")
    print("|---|---:|---:|")

    for call in run["calls"]:
        if call["call"].startswith("probe_"):
            continue

        print(
            f"| {call['call']} "
            f"| {call['input_tokens']} "
            f"| {call['output_tokens']} |"
        )

    print("\n| Probe | Retrieved | Reply |")
    print("|---|---|---|")

    for probe in run["probes"]:
        reply = probe["reply"].replace("\n", " ")
        status = "yes" if probe["retrieved"] else "no"

        print(
            f"| {probe['id']} "
            f"| {status} "
            f"| {reply} |"
        )

    stats = metrics(run)

    print(f"\nPeak input: {stats['peak_input']}")
    print(f"Total input: {stats['total_input']}")
    print(f"Probes retrieved: {stats['retrieved']}/5")

    if run["state"] is not None:
        print("\nCompressed state:")
        print(
            json.dumps(
                run["state"],
                ensure_ascii=False,
                indent=2,
            )
        )


def scripted() -> None:
    """Compare full history against validated compressed memory."""
    uncompressed = run_script(compressed=False)
    compressed = run_script(compressed=True)

    print_run(uncompressed)
    print_run(compressed)

    full = metrics(uncompressed)
    comp = metrics(compressed)

    print("\n### Compression comparison")

    print(
        "Peak input reduction: "
        f"{full['peak_input']} -> {comp['peak_input']} "
        f"({reduction(full['peak_input'], comp['peak_input']):.1f}%)"
    )

    print(
        "Total input reduction: "
        f"{full['total_input']} -> {comp['total_input']} "
        f"({reduction(full['total_input'], comp['total_input']):.1f}%)"
    )

    print(
        "Probe retention: "
        f"{full['retrieved']}/5 -> {comp['retrieved']}/5"
    )

    output_dir = ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)

    (output_dir / "chat_memory_results.json").write_text(
        json.dumps(
            {
                "uncompressed": uncompressed,
                "compressed": compressed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def interactive() -> None:
    """Real chat with repeatable compression."""
    session = Session()

    print("Commands: compress, tokens, exit")

    while True:
        text = input("\nYou: ").strip()

        if not text:
            continue

        if text.lower() == "exit":
            break

        if text.lower() == "compress":
            if session.compress():
                print("Memory compressed successfully.")
                print(
                    json.dumps(
                        session.state,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            continue

        if text.lower() == "tokens":
            if session.last_usage is None:
                print("No model call yet.")
            else:
                usage = session.last_usage
                print(
                    f"input={usage['input_tokens']}, "
                    f"output={usage['output_tokens']}, "
                    f"total="
                    f"{usage['input_tokens'] + usage['output_tokens']}"
                )
            continue

        reply = session.ask(text)
        print("Bot:", reply)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    if args.interactive:
        interactive()
    else:
        scripted()