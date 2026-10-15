# Orchestrating Intelligence companion exercises

This package accompanies Chapter 11 and Appendix B of the book.

## Included files

- `delivery_evidence.py` — complete local evidence builder, using Python's standard library.
- `example-input.json` — the six fictional delivery cases.
- `expected/evidence-packet.json` — expected classifications and supporting observations.
- `expected/review-draft.md` — the deterministic internal review draft.
- `manuscript.md` — the complete book in editable plain-text Markdown.

## Run the example

Open a terminal in the extracted folder. Use an installed, organization-approved Python 3.10 or later interpreter.

```text
python delivery_evidence.py --self-test
python delivery_evidence.py --output my-demo
python delivery_evidence.py --input example-input.json --output my-input-demo
```

Use `python3` instead of `python` if that is your interpreter's command name.

The first command should print `PASS: eight instructional checks`. The other commands create local files in the named output folders. Reusing an output folder replaces the example's output files there.

## Expected result

| Delivery | Status |
| --- | --- |
| A | RECEIVED |
| B | MISSING |
| C | STALE |
| D | EMPTY |
| E | CONFLICT |
| F | RECEIVED_LATE |

There are five attention items when late arrivals are included.

The script does not call an AI model, contact network services, inspect real source files, send messages, or change business records. The content fingerprints in the sample are illustrative labels, not hashes of actual delivery files. The packet's `input_sha256` is a real hash of the supplied JSON input after canonical serialization.

Use the bounded instruction in Chapter 11 to have an approved assistant explain the JSON evidence packet. Review its output against the computed statuses and source evidence. This separates a deterministic evidence check from an agent's language interpretation.

Before adapting the example for production, establish approved source collection, data access, scheduling, durable state, recovery, and an operating owner as described in the book.
