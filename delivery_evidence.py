#!/usr/bin/env python3
"""Local instructional example. All default records are fictional."""
import argparse
import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

RULE_VERSION = "harbor-exercise-1"


def sample():
    owners = ["Intake team", "Intake team", "Supplier liaison",
              "Supplier liaison", "Data operations", "Data operations"]
    schedule = [
        {"delivery_id": key, "business_date": "2030-04-16",
         "deadline": "2030-04-16T09:00:00-07:00",
         "allow_empty": False, "owner": owner}
        for key, owner in zip("ABCDEF", owners)
    ]
    observations = [
        ("A", "2030-04-16", "08:42", 120, "example-a"),
        ("C", "2030-04-15", "08:51", 90, "example-c"),
        ("D", "2030-04-16", "08:55", 0, "example-d"),
        ("E", "2030-04-16", "08:40", 80, "example-e1"),
        ("E", "2030-04-16", "08:58", 82, "example-e2"),
        ("F", "2030-04-16", "09:17", 75, "example-f"),
    ]
    arrivals = [
        {"delivery_id": key, "business_date": day,
         "received_at": f"2030-04-16T{time}:00-07:00",
         "record_count": count, "content_fingerprint": fingerprint}
        for key, day, time, count, fingerprint in observations
    ]
    return {"as_of": "2030-04-16T09:30:00-07:00",
            "schedule": schedule, "arrivals": arrivals}


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Every timestamp needs an explicit UTC offset")
    return result


def nonempty(record, field):
    value = record[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def validate(data):
    timestamp(data["as_of"])
    if not isinstance(data["schedule"], list) or not data["schedule"]:
        raise ValueError("schedule must be a nonempty list")
    if not isinstance(data["arrivals"], list):
        raise ValueError("arrivals must be a list")
    keys = []
    days = set()
    for row in data["schedule"]:
        keys.append(nonempty(row, "delivery_id"))
        days.add(date.fromisoformat(row["business_date"]))
        timestamp(row["deadline"])
        nonempty(row, "owner")
        if type(row["allow_empty"]) is not bool:
            raise ValueError("allow_empty must be true or false")
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate scheduled delivery identifier")
    if len(days) != 1:
        raise ValueError("This example evaluates one business date per run")
    for row in data["arrivals"]:
        nonempty(row, "delivery_id")
        nonempty(row, "content_fingerprint")
        date.fromisoformat(row["business_date"])
        timestamp(row["received_at"])
        count = row["record_count"]
        if type(count) is not int or count < 0:
            raise ValueError("record_count must be a nonnegative integer")


def classify(data):
    validate(data)
    cutoff = timestamp(data["as_of"])
    visible = [r for r in data["arrivals"]
               if timestamp(r["received_at"]) <= cutoff]
    cases = []
    for expected in data["schedule"]:
        key = expected["delivery_id"]
        deadline = timestamp(expected["deadline"])
        observed = [r for r in visible if r["delivery_id"] == key]
        current = [r for r in observed
                   if r["business_date"] == expected["business_date"]]
        if not current:
            if cutoff < deadline:
                status, reason = "PENDING", "Deadline has not been reached"
            elif observed:
                prior_only = all(r["business_date"] < expected["business_date"]
                                 for r in observed)
                status = "STALE" if prior_only else "DATE_MISMATCH"
                reason = "No expected-date observation; other dates observed: "
                reason += ", ".join(sorted({r["business_date"] for r in observed}))
            else:
                status, reason = "MISSING", "No arrival observed by cutoff"
        else:
            versions = {(r["content_fingerprint"], r["record_count"])
                        for r in current}
            first = min(current, key=lambda r: timestamp(r["received_at"]))
            if len(versions) > 1:
                status = "CONFLICT"
                reason = "Multiple content versions or inconsistent count evidence"
            elif first["record_count"] == 0 and not expected["allow_empty"]:
                status, reason = "EMPTY", "Zero records; empty delivery not permitted"
            elif timestamp(first["received_at"]) > deadline:
                status, reason = "RECEIVED_LATE", "Qualifying arrival after deadline"
            else:
                status, reason = "RECEIVED", "Qualifying arrival by deadline"
        cases.append({**expected, "status": status, "reason": reason,
                      "evidence": observed})
    known = {r["delivery_id"] for r in data["schedule"]}
    unexpected = [r for r in visible if r["delivery_id"] not in known]
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    return {"rule_version": RULE_VERSION, "input_sha256": fingerprint,
            "as_of": data["as_of"],
            "business_date": data["schedule"][0]["business_date"],
            "counts": dict(sorted(Counter(c["status"] for c in cases).items())),
            "attention_items": sum(c["status"] not in ("RECEIVED", "PENDING")
                                   for c in cases),
            "cases": cases, "unexpected_arrivals": unexpected}


def report(packet):
    lines = ["# Internal delivery review draft", "",
             f"Business date: {packet['business_date']}",
             f"Observation cutoff: {packet['as_of']}",
             f"Rule version: {packet['rule_version']}", "",
             f"Expected deliveries: {len(packet['cases'])}",
             f"Attention items, including late arrivals: {packet['attention_items']}",
             "Arrival evidence does not prove downstream processing.", ""]
    for row in packet["cases"]:
        lines += [f"## {row['delivery_id']} — {row['status']}",
                  f"Owner: {row['owner']}", f"Reason: {row['reason']}",
                  f"Deadline: {row['deadline']}",
                  f"Evidence observations: {len(row['evidence'])}", ""]
    lines += [f"Unexpected arrival observations: {len(packet['unexpected_arrivals'])}",
              "Review the JSON packet for source details before acting."]
    return "\n\n".join(lines) + "\n"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def self_test():
    def check(condition, message):
        if not condition:
            raise AssertionError(message)
    base = sample()
    expected = ["RECEIVED", "MISSING", "STALE", "EMPTY", "CONFLICT", "RECEIVED_LATE"]
    check([c["status"] for c in classify(base)["cases"]] == expected, "Six cases")
    repeat = copy.deepcopy(base)
    repeat["arrivals"].append(copy.deepcopy(repeat["arrivals"][0]))
    check(classify(repeat)["cases"][0]["status"] == "RECEIVED", "Duplicate observation")
    early = copy.deepcopy(base)
    early["as_of"] = "2030-04-16T08:30:00-07:00"
    check(all(c["status"] == "PENDING" for c in classify(early)["cases"]), "Early cutoff")
    future = copy.deepcopy(base)
    future["arrivals"][0]["received_at"] = "2030-04-16T09:45:00-07:00"
    check(classify(future)["cases"][0]["status"] == "MISSING", "Future arrival")
    unknown = copy.deepcopy(base)
    extra = copy.deepcopy(unknown["arrivals"][0])
    extra["delivery_id"] = "Z"
    unknown["arrivals"].append(extra)
    check(len(classify(unknown)["unexpected_arrivals"]) == 1, "Unknown identifier")
    conflict = copy.deepcopy(repeat)
    conflict["arrivals"][-1]["record_count"] = 121
    check(classify(conflict)["cases"][0]["status"] == "CONFLICT", "Count conflict")
    wrong_date = copy.deepcopy(base)
    wrong_date["arrivals"][0]["business_date"] = "2030-04-17"
    check(classify(wrong_date)["cases"][0]["status"] == "DATE_MISMATCH", "Future business date")
    invalid = copy.deepcopy(base)
    invalid["as_of"] = "2030-04-16T09:30:00"
    try:
        classify(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Naive timestamp accepted")
    print("PASS: eight instructional checks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("demo-output"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    try:
        data = json.loads(args.input.read_text(encoding="utf-8")) if args.input else sample()
        packet = classify(data)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"Input rejected: {error}\n")
    for name, value in (("example-input.json", data), ("evidence-packet.json", packet)):
        atomic_write(args.output / name, json.dumps(value, indent=2) + "\n")
    atomic_write(args.output / "review-draft.md", report(packet))
    print(f"Draft files written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
