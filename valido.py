import csv
import html
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

from neighbor_engine import PremierParams, intervals_overlap


OUTPUT_DIR = Path("output")
REPORTS_DIR = Path("validation_reports")
MAX_DETAILED_ERRORS = 1000
MAX_TIMELINE_ROWS = 80


def minutes_label(value):
    if value is None:
        return "-"

    try:
        value = int(value)
    except (TypeError, ValueError):
        return str(value)

    hours = value // 60
    minutes = value % 60

    if hours < 24:
        return f"{value} min ({hours:02d}:{minutes:02d})"

    days = hours // 24
    hour_in_day = hours % 24
    return f"{value} min (day {days}, {hour_in_day:02d}:{minutes:02d})"


def safe_file_part(value):
    allowed = []
    for char in str(value):
        if char.isalnum() or char in ("-", "_"):
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip("_") or "report"


def report_base(data, output_path):
    instance_name = data.get("instance")
    if instance_name:
        return safe_file_part(Path(instance_name).stem)
    return safe_file_part(output_path.stem)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path, content):
    REPORTS_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def get_output_files():
    return sorted(OUTPUT_DIR.glob("*.json"))


def choose_output_file():
    output_files = get_output_files()
    if not output_files:
        print(f"Nuk u gjet asnje output JSON ne folderin: {OUTPUT_DIR}")
        return None

    print("\nZgjedh output-in qe do ta validosh:\n")
    for index, path in enumerate(output_files):
        print(f"{index}. {path.name}")

    choice = input("\nShkruaj numrin e output-it: ").strip()

    try:
        selected_index = int(choice)
    except ValueError:
        print("Zgjedhje e pavlefshme.")
        return None

    if selected_index < 0 or selected_index >= len(output_files):
        print("Zgjedhje e pavlefshme.")
        return None

    return output_files[selected_index]


def choose_mode():
    print("\nZgjedh menyren e validimit:\n")
    print("1. Output i vogel per nje program specifik")
    print("2. Vizualizim timeline")
    print("3. Output CSV ne validation_reports")
    print("4. Validim automatik")
    print("5. Vizualizim HTML")

    choice = input("\nShkruaj 1, 2, 3, 4 ose 5: ").strip()
    if choice not in {"1", "2", "3", "4", "5"}:
        print("Menyre e pavlefshme.")
        return None
    return choice


def ask_program_index(program_count):
    value = input(f"\nShkruaj indeksin e programit (0 - {program_count - 1}): ").strip()

    try:
        program_index = int(value)
    except ValueError:
        print("Indeksi duhet te jete numer.")
        return None

    if program_index < 0 or program_index >= program_count:
        print("Indeks i pavlefshem.")
        return None

    return program_index


def validate_output_shape(data):
    errors = []

    if not isinstance(data, dict):
        return ["Output-i nuk eshte objekt JSON."]

    programs = data.get("programs")
    neighbors = data.get("neighbor_indices")

    if not isinstance(programs, list):
        errors.append("Mungon fusha 'programs' ose nuk eshte liste.")
    if not isinstance(neighbors, list):
        errors.append("Mungon fusha 'neighbor_indices' ose nuk eshte liste.")

    if errors:
        return errors

    if len(programs) != len(neighbors):
        errors.append(
            f"Numri i programeve ({len(programs)}) nuk perputhet me "
            f"numrin e listave te fqinjeve ({len(neighbors)})."
        )

    for index, program in enumerate(programs[:20]):
        for field in ("index", "program_id", "channel_id", "start", "end"):
            if field not in program:
                errors.append(f"Programi {index} nuk e ka fushen '{field}'.")

    return errors


def get_premier_params_from_data(data):
    raw = data.get("premier_params") or {}
    return PremierParams(
        delta_cross_channel=int(raw.get("delta_cross_channel", 75)),
        delta_advanced=int(raw.get("delta_advanced", 30)),
    )


def get_rule_info(data):
    variant = data.get("variant")
    delta = data.get("delta")

    if variant not in {"basic", "advanced", "premier"}:
        raise ValueError("Output-i duhet te kete variant 'basic', 'advanced' ose 'premier'.")

    if variant == "basic":
        return variant, None, None

    if variant == "advanced":
        if delta is None:
            raise ValueError("Output-i advanced duhet te kete vlere per delta.")
        return variant, delta, None

    return variant, None, get_premier_params_from_data(data)


def build_starts(programs):
    return [program["start"] for program in programs]


def expected_neighbor_indices(programs, starts, index, variant, delta, premier_params):
    current = programs[index]
    left = bisect_left(starts, current["start"])

    if variant == "basic":
        right = bisect_left(starts, current["end"])
    elif variant == "advanced":
        right = bisect_right(starts, current["end"] + delta)
    else:
        horizon = max(premier_params.delta_advanced, premier_params.delta_cross_channel)
        right = bisect_right(starts, current["end"] + horizon)

    expected = []
    for candidate_index in range(left, right):
        if candidate_index == index:
            continue

        candidate = programs[candidate_index]
        if is_expected_neighbor(current, candidate, variant, delta, premier_params):
            expected.append(candidate_index)

    return expected


def is_expected_neighbor(current, candidate, variant, delta, premier_params):
    if candidate["index"] == current["index"]:
        return False

    if candidate["start"] < current["start"]:
        return False

    if variant == "basic":
        return current["start"] < candidate["end"] and candidate["start"] < current["end"]

    if variant == "advanced":
        return candidate["start"] <= current["end"] + delta

    assert premier_params is not None
    if candidate["channel_id"] == current["channel_id"]:
        return intervals_overlap(current, candidate)
    return candidate["start"] <= current["end"] + premier_params.delta_cross_channel


def validation_window_end(variant, delta, premier_params, current):
    if variant == "basic":
        return current["end"]
    if variant == "advanced":
        return current["end"] + delta
    return current["end"] + max(premier_params.delta_advanced, premier_params.delta_cross_channel)


def rejection_reason(current, candidate, variant, delta, premier_params):
    if candidate["index"] == current["index"]:
        return "same_program"

    if candidate["start"] < current["start"]:
        return "starts_before_current"

    if variant == "basic":
        has_overlap = current["start"] < candidate["end"] and candidate["start"] < current["end"]
        if not has_overlap:
            return "no_overlap"
        return "expected_by_basic_rule"

    if variant == "advanced":
        if candidate["start"] > current["end"] + delta:
            return "after_delta_window"
        return "expected_by_advanced_rule"

    assert premier_params is not None
    if candidate["channel_id"] == current["channel_id"]:
        if not intervals_overlap(current, candidate):
            return "premier_same_channel_requires_overlap"
        return "expected_by_premier_rule"
    if candidate["start"] > current["end"] + premier_params.delta_cross_channel:
        return "after_premier_cross_window"
    return "expected_by_premier_rule"


def rule_description(variant, delta, premier_params):
    if variant == "basic":
        return "Basic: candidate.start >= current.start dhe programet duhet te kene overlap."
    if variant == "advanced":
        return (
            "Advanced: candidate.start >= current.start dhe "
            f"candidate.start <= current.end + delta ({delta})."
        )
    assert premier_params is not None
    return (
        "Premier: same-channel overlap only; cross-channel start <= end + "
        f"{premier_params.delta_cross_channel} (horizon max(adv,cross)={max(premier_params.delta_advanced, premier_params.delta_cross_channel)})."
    )


def variant_params_label(variant, delta, premier_params):
    if variant == "basic":
        return "-"
    if variant == "advanced":
        return str(delta) if delta is not None else "-"
    assert premier_params is not None
    return f"x_ch={premier_params.delta_cross_channel},adv={premier_params.delta_advanced}"


def observed_neighbors(data, index):
    neighbors = data["neighbor_indices"][index]
    if not isinstance(neighbors, list):
        return []
    return neighbors


def compare_program(data, index):
    programs = data["programs"]
    starts = build_starts(programs)
    variant, delta, premier_params = get_rule_info(data)
    observed = observed_neighbors(data, index)
    expected = expected_neighbor_indices(programs, starts, index, variant, delta, premier_params)

    observed_valid = [
        neighbor_index
        for neighbor_index in observed
        if isinstance(neighbor_index, int) and 0 <= neighbor_index < len(programs)
    ]

    observed_set = set(observed_valid)
    expected_set = set(expected)

    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    duplicate_count = len(observed_valid) - len(observed_set)
    invalid_values = [
        value
        for value in observed
        if not isinstance(value, int) or value < 0 or value >= len(programs)
    ]
    order_mismatch = not missing and not extra and observed_valid != expected

    same_channel = [
        neighbor_index
        for neighbor_index in observed_valid
        if programs[neighbor_index]["channel_id"] == programs[index]["channel_id"]
    ]

    return {
        "observed": observed,
        "observed_valid": observed_valid,
        "expected": expected,
        "missing": missing,
        "extra": extra,
        "duplicate_count": duplicate_count,
        "invalid_values": invalid_values,
        "order_mismatch": order_mismatch,
        "same_channel": same_channel,
    }


def program_line(program):
    return (
        f"{program['index']} | id={program['program_id']} | ch={program['channel_id']} | "
        f"start={minutes_label(program['start'])} | end={minutes_label(program['end'])} | "
        f"genre={program.get('genre')} | score={program.get('score')}"
    )


def format_program_table(title, programs, indices, empty_text):
    lines = [title]
    if not indices:
        lines.append(empty_text)
        return lines

    for index in indices:
        lines.append(f"- {program_line(programs[index])}")
    return lines


def report_for_program(data, output_path, index):
    programs = data["programs"]
    variant, delta, premier_params = get_rule_info(data)
    current = programs[index]
    comparison = compare_program(data, index)
    limit = validation_window_end(variant, delta, premier_params, current)
    status = "VALID" if not comparison["missing"] and not comparison["extra"] else "NOT VALID"

    lines = [
        "PROGRAM VALIDATION REPORT",
        "=" * 25,
        f"Output file: {output_path.name}",
        f"Instance: {data.get('instance')}",
        f"Variant: {variant}",
        f"Rule: {rule_description(variant, delta, premier_params)}",
        "",
        "Current program:",
        f"- {program_line(current)}",
        f"- Validation window: {minutes_label(current['start'])} -> {minutes_label(limit)}",
        "",
        f"Status: {status}",
        f"Observed neighbors: {len(comparison['observed_valid'])}",
        f"Expected neighbors: {len(comparison['expected'])}",
        f"Missing neighbors: {comparison['missing']}",
        f"Extra neighbors: {comparison['extra']}",
        f"Duplicate observed neighbors: {comparison['duplicate_count']}",
        f"Invalid neighbor values: {comparison['invalid_values']}",
        f"Same-channel observed neighbors: {comparison['same_channel']}",
        "",
        "Note: same-channel neighbors are reported, but not treated as invalid by the current rules.",
        "",
    ]

    lines.extend(format_program_table("Observed neighbor details:", programs, comparison["observed_valid"], "- None"))
    lines.append("")
    lines.extend(format_program_table("Expected neighbor details:", programs, comparison["expected"], "- None"))

    if comparison["missing"]:
        lines.append("")
        lines.extend(format_program_table("Missing neighbor details:", programs, comparison["missing"], "- None"))

    if comparison["extra"]:
        lines.append("")
        lines.extend(format_program_table("Extra neighbor details:", programs, comparison["extra"], "- None"))

    report_path = REPORTS_DIR / f"{report_base(data, output_path)}_prog_{index}_summary.txt"
    write_text(report_path, "\n".join(lines) + "\n")

    print("\n".join(lines[:24]))
    print(f"\nRaporti u ruajt ne: {report_path}")


def candidate_indices_for_program(data, index, extra_minutes=60):
    programs = data["programs"]
    starts = build_starts(programs)
    variant, delta, premier_params = get_rule_info(data)
    current = programs[index]
    limit = validation_window_end(variant, delta, premier_params, current)
    display_limit = limit + extra_minutes
    left = bisect_left(starts, current["start"])
    right = bisect_right(starts, display_limit)

    candidates = list(range(left, right))
    comparison = compare_program(data, index)
    important = set(comparison["observed_valid"]) | set(comparison["expected"]) | {index}

    for important_index in sorted(important):
        if important_index not in candidates:
            candidates.append(important_index)

    return sorted(candidates)[:MAX_TIMELINE_ROWS]


def timeline_bounds(programs, indices, current, variant, delta, premier_params):
    limit = validation_window_end(variant, delta, premier_params, current)
    min_time = current["start"]
    max_time = max([limit, current["end"]] + [programs[index]["end"] for index in indices])

    if max_time <= min_time:
        max_time = min_time + 1

    return min_time, max_time, limit


def ascii_bar(start, end, min_time, max_time, width=70, marker="#"):
    span = max_time - min_time
    left = int(((start - min_time) / span) * width)
    right = int(((end - min_time) / span) * width)
    left = max(0, min(width - 1, left))
    right = max(left + 1, min(width, right))
    return " " * left + marker * (right - left) + " " * (width - right)


def timeline_report(data, output_path, index):
    programs = data["programs"]
    variant, delta, premier_params = get_rule_info(data)
    current = programs[index]
    comparison = compare_program(data, index)
    indices = candidate_indices_for_program(data, index)
    min_time, max_time, limit = timeline_bounds(programs, indices, current, variant, delta, premier_params)

    expected = set(comparison["expected"])
    observed = set(comparison["observed_valid"])

    lines = [
        "TIMELINE VALIDATION REPORT",
        "=" * 26,
        f"Output file: {output_path.name}",
        f"Program: {program_line(current)}",
        f"Rule: {rule_description(variant, delta, premier_params)}",
        f"Timeline range: {minutes_label(min_time)} -> {minutes_label(max_time)}",
        f"Window end: {minutes_label(limit)}",
        "",
        "Legend: CURRENT=#, EXPECTED/OBSERVED==, REJECTED=-",
        "",
    ]

    for candidate_index in indices:
        candidate = programs[candidate_index]

        if candidate_index == index:
            status = "CURRENT"
            marker = "#"
        elif candidate_index in expected and candidate_index in observed:
            status = "OK"
            marker = "="
        elif candidate_index in expected:
            status = "MISSING"
            marker = "="
        elif candidate_index in observed:
            status = "EXTRA"
            marker = "!"
        else:
            status = rejection_reason(current, candidate, variant, delta, premier_params)
            marker = "-"

        bar = ascii_bar(candidate["start"], candidate["end"], min_time, max_time, marker=marker)
        lines.append(
            f"{candidate_index:>6} ch={candidate['channel_id']:<4} "
            f"{candidate['program_id'][:28]:<28} |{bar}| {status}"
        )

    report_path = REPORTS_DIR / f"{report_base(data, output_path)}_prog_{index}_timeline.txt"
    write_text(report_path, "\n".join(lines) + "\n")

    print("\n".join(lines))
    print(f"\nTimeline u ruajt ne: {report_path}")


def csv_report(data, output_path, index):
    REPORTS_DIR.mkdir(exist_ok=True)

    programs = data["programs"]
    variant, delta, premier_params = get_rule_info(data)
    current = programs[index]
    comparison = compare_program(data, index)
    candidate_indices = candidate_indices_for_program(data, index)
    expected = set(comparison["expected"])
    observed = set(comparison["observed_valid"])

    csv_path = REPORTS_DIR / f"{report_base(data, output_path)}_prog_{index}_candidates.csv"

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "current_index",
                "current_id",
                "current_channel",
                "current_start",
                "current_end",
                "current_genre",
                "candidate_index",
                "candidate_id",
                "candidate_channel",
                "candidate_start",
                "candidate_end",
                "candidate_genre",
                "observed_neighbor",
                "expected_neighbor",
                "status",
                "reason",
                "same_channel",
            ]
        )

        for candidate_index in candidate_indices:
            candidate = programs[candidate_index]
            observed_neighbor = candidate_index in observed
            expected_neighbor = candidate_index in expected

            if observed_neighbor and expected_neighbor:
                status = "ok"
            elif expected_neighbor:
                status = "missing"
            elif observed_neighbor:
                status = "extra"
            else:
                status = "rejected"

            writer.writerow(
                [
                    current["index"],
                    current["program_id"],
                    current["channel_id"],
                    current["start"],
                    current["end"],
                    current.get("genre"),
                    candidate["index"],
                    candidate["program_id"],
                    candidate["channel_id"],
                    candidate["start"],
                    candidate["end"],
                    candidate.get("genre"),
                    observed_neighbor,
                    expected_neighbor,
                    status,
                    rejection_reason(current, candidate, variant, delta, premier_params),
                    candidate["channel_id"] == current["channel_id"],
                ]
            )

    print(f"\nCSV u ruajt ne: {csv_path}")


def automatic_validation(data, output_path):
    programs = data["programs"]
    neighbors = data["neighbor_indices"]
    variant, delta, premier_params = get_rule_info(data)
    starts = build_starts(programs)

    errors = []
    warnings = []
    missing_total = 0
    extra_total = 0
    invalid_total = 0
    duplicate_total = 0
    order_mismatch_total = 0
    same_channel_total = 0

    if len(programs) != len(neighbors):
        errors.append(
            f"Length mismatch: programs={len(programs)}, neighbor_indices={len(neighbors)}"
        )

    for index, current in enumerate(programs):
        observed = neighbors[index] if index < len(neighbors) else []
        if not isinstance(observed, list):
            invalid_total += 1
            if len(errors) < MAX_DETAILED_ERRORS:
                errors.append(f"Program {index}: neighbor list is not a list.")
            continue

        expected = expected_neighbor_indices(programs, starts, index, variant, delta, premier_params)
        observed_valid = [
            neighbor_index
            for neighbor_index in observed
            if isinstance(neighbor_index, int) and 0 <= neighbor_index < len(programs)
        ]

        invalid_values = [
            value
            for value in observed
            if not isinstance(value, int) or value < 0 or value >= len(programs)
        ]
        duplicate_count = len(observed_valid) - len(set(observed_valid))
        missing = sorted(set(expected) - set(observed_valid))
        extra = sorted(set(observed_valid) - set(expected))
        same_channel = [
            neighbor_index
            for neighbor_index in observed_valid
            if programs[neighbor_index]["channel_id"] == current["channel_id"]
        ]

        invalid_total += len(invalid_values)
        duplicate_total += duplicate_count
        missing_total += len(missing)
        extra_total += len(extra)
        same_channel_total += len(same_channel)

        if not missing and not extra and observed_valid != expected:
            order_mismatch_total += 1

        if invalid_values and len(errors) < MAX_DETAILED_ERRORS:
            errors.append(f"Program {index}: invalid neighbor values {invalid_values}")
        if duplicate_count and len(errors) < MAX_DETAILED_ERRORS:
            errors.append(f"Program {index}: {duplicate_count} duplicate neighbor(s)")
        if missing and len(errors) < MAX_DETAILED_ERRORS:
            errors.append(f"Program {index}: missing expected neighbors {missing[:20]}")
        if extra and len(errors) < MAX_DETAILED_ERRORS:
            errors.append(f"Program {index}: extra neighbors {extra[:20]}")

    if order_mismatch_total:
        warnings.append(
            f"{order_mismatch_total} program(e) kane te njejtet fqinje, por ne rend tjeter."
        )

    if same_channel_total:
        warnings.append(
            f"{same_channel_total} fqinje jane ne te njejtin kanal me programin aktual. "
            "Kjo raportohet si informacion, jo si gabim, sepse rregullat aktuale e lejojne."
        )

    valid = not errors and missing_total == 0 and extra_total == 0 and invalid_total == 0 and duplicate_total == 0

    lines = [
        "AUTOMATIC VALIDATION REPORT",
        "=" * 27,
        f"Output file: {output_path.name}",
        f"Instance: {data.get('instance')}",
        f"Variant: {variant}",
        f"Rule: {rule_description(variant, delta, premier_params)}",
        f"Program count: {len(programs)}",
        "",
        f"Valid: {valid}",
        f"Missing expected neighbors: {missing_total}",
        f"Extra neighbors: {extra_total}",
        f"Invalid neighbor values: {invalid_total}",
        f"Duplicate neighbors: {duplicate_total}",
        f"Order mismatches: {order_mismatch_total}",
        f"Same-channel observed neighbors: {same_channel_total}",
        "",
        "Warnings:",
    ]

    lines.extend([f"- {warning}" for warning in warnings] or ["- None"])
    lines.append("")
    lines.append("Errors:")
    lines.extend([f"- {error}" for error in errors[:MAX_DETAILED_ERRORS]] or ["- None"])

    if len(errors) > MAX_DETAILED_ERRORS:
        lines.append(f"- ... edhe {len(errors) - MAX_DETAILED_ERRORS} gabime tjera.")

    report_path = REPORTS_DIR / f"{report_base(data, output_path)}_automatic.txt"
    write_text(report_path, "\n".join(lines) + "\n")

    print("\n".join(lines[:18]))
    print(f"\nRaporti automatik u ruajt ne: {report_path}")


def html_escape(value):
    return html.escape(str(value), quote=True)


def percent(value, min_time, max_time):
    span = max_time - min_time
    if span <= 0:
        return 0
    return max(0, min(100, ((value - min_time) / span) * 100))


def html_timeline(data, output_path, index):
    REPORTS_DIR.mkdir(exist_ok=True)

    programs = data["programs"]
    variant, delta, premier_params = get_rule_info(data)
    current = programs[index]
    comparison = compare_program(data, index)
    indices = candidate_indices_for_program(data, index)
    min_time, max_time, limit = timeline_bounds(programs, indices, current, variant, delta, premier_params)
    expected = set(comparison["expected"])
    observed = set(comparison["observed_valid"])

    rows = []
    for candidate_index in indices:
        candidate = programs[candidate_index]

        if candidate_index == index:
            status = "Current"
            row_class = "current"
        elif candidate_index in expected and candidate_index in observed:
            status = "OK"
            row_class = "ok"
        elif candidate_index in expected:
            status = "Missing"
            row_class = "missing"
        elif candidate_index in observed:
            status = "Extra"
            row_class = "extra"
        else:
            status = "Rejected"
            row_class = "rejected"

        left = percent(candidate["start"], min_time, max_time)
        width = max(0.8, percent(candidate["end"], min_time, max_time) - left)
        reason = rejection_reason(current, candidate, variant, delta, premier_params)
        same_channel = candidate["channel_id"] == current["channel_id"]

        rows.append(
            f"""
            <tr class="{row_class}">
              <td>{candidate_index}</td>
              <td>{html_escape(candidate["program_id"])}</td>
              <td>{html_escape(candidate["channel_id"])}</td>
              <td>{html_escape(candidate.get("genre"))}</td>
              <td>{html_escape(minutes_label(candidate["start"]))}</td>
              <td>{html_escape(minutes_label(candidate["end"]))}</td>
              <td><span class="badge {row_class}">{status}</span></td>
              <td>{html_escape(reason)}</td>
              <td>{'Yes' if same_channel else 'No'}</td>
              <td>
                <div class="track">
                  <div class="bar {row_class}" style="left:{left:.2f}%;width:{width:.2f}%"></div>
                </div>
              </td>
            </tr>
            """
        )

    limit_left = percent(limit, min_time, max_time)
    current_left = percent(current["start"], min_time, max_time)
    current_width = max(0.8, percent(current["end"], min_time, max_time) - current_left)

    valid_for_program = not comparison["missing"] and not comparison["extra"] and not comparison["invalid_values"]
    html_content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Validation Report - Program {index}</title>
  <style>
    :root {{
      --bg: #f6f7fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5c6675;
      --line: #dfe4ec;
      --ok: #1f9d55;
      --missing: #d97706;
      --extra: #dc2626;
      --current: #2563eb;
      --rejected: #8a94a6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      background: #121826;
      color: white;
      padding: 28px 36px;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    header p {{
      margin: 0;
      color: #cfd6e4;
    }}
    main {{
      max-width: 1220px;
      margin: 24px auto 48px;
      padding: 0 20px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 7px;
    }}
    .metric strong {{
      font-size: 22px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 16px;
      padding: 18px;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 18px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      color: var(--muted);
      font-size: 14px;
    }}
    .window {{
      position: relative;
      height: 52px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9fafc;
      margin-top: 8px;
      overflow: hidden;
    }}
    .window .current-window {{
      position: absolute;
      top: 13px;
      height: 24px;
      border-radius: 5px;
      background: var(--current);
    }}
    .window .limit {{
      position: absolute;
      top: 0;
      bottom: 0;
      border-left: 2px dashed #111827;
    }}
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      color: var(--muted);
      font-weight: 700;
      background: #fafbfe;
    }}
    .track {{
      position: relative;
      width: 240px;
      height: 18px;
      border-radius: 99px;
      background: #eef1f6;
      overflow: hidden;
    }}
    .bar {{
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: 99px;
    }}
    .bar.ok, .badge.ok {{ background: var(--ok); }}
    .bar.missing, .badge.missing {{ background: var(--missing); }}
    .bar.extra, .badge.extra {{ background: var(--extra); }}
    .bar.current, .badge.current {{ background: var(--current); }}
    .bar.rejected, .badge.rejected {{ background: var(--rejected); }}
    .badge {{
      display: inline-block;
      min-width: 70px;
      color: white;
      padding: 4px 8px;
      border-radius: 99px;
      text-align: center;
      font-weight: 700;
      font-size: 12px;
    }}
    .note {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    @media (max-width: 760px) {{
      .grid, .summary {{ grid-template-columns: 1fr; }}
      header {{ padding: 22px 20px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Validation Report</h1>
    <p>{html_escape(output_path.name)} | Program {index} | {html_escape(data.get("instance"))}</p>
  </header>
  <main>
    <div class="grid">
      <div class="metric"><span>Status</span><strong>{'Valid' if valid_for_program else 'Needs review'}</strong></div>
      <div class="metric"><span>Observed</span><strong>{len(comparison["observed_valid"])}</strong></div>
      <div class="metric"><span>Expected</span><strong>{len(comparison["expected"])}</strong></div>
      <div class="metric"><span>Params</span><strong>{html_escape(variant_params_label(variant, delta, premier_params))}</strong></div>
    </div>

    <section>
      <h2>Current Program</h2>
      <div class="summary">
        <div><strong>ID:</strong> {html_escape(current["program_id"])}</div>
        <div><strong>Channel:</strong> {html_escape(current["channel_id"])}</div>
        <div><strong>Start:</strong> {html_escape(minutes_label(current["start"]))}</div>
        <div><strong>End:</strong> {html_escape(minutes_label(current["end"]))}</div>
        <div><strong>Genre:</strong> {html_escape(current.get("genre"))}</div>
        <div><strong>Rule:</strong> {html_escape(rule_description(variant, delta, premier_params))}</div>
      </div>
      <div class="window" title="Current program and validation limit">
        <div class="current-window" style="left:{current_left:.2f}%;width:{current_width:.2f}%"></div>
        <div class="limit" style="left:{limit_left:.2f}%"></div>
      </div>
      <p class="note">Dashed line marks scan horizon end: {html_escape(minutes_label(limit))}. Interpret neighbor validity using the rule text above (premier uses channel-dependent logic).</p>
    </section>

    <section>
      <h2>Candidate Timeline</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Index</th>
              <th>Program ID</th>
              <th>Channel</th>
              <th>Genre</th>
              <th>Start</th>
              <th>End</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Same channel</th>
              <th>Timeline</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>
"""

    html_path = REPORTS_DIR / f"{report_base(data, output_path)}_prog_{index}_visual.html"
    with open(html_path, "w", encoding="utf-8", newline="") as f:
        f.write(html_content)

    print(f"\nHTML raporti u ruajt ne: {html_path}")


def main():
    print("=== Valido Zgjidhjen ===")

    output_path = choose_output_file()
    if output_path is None:
        return

    print("\nDuke lexuar output-in...")
    data = load_json(output_path)

    shape_errors = validate_output_shape(data)
    if shape_errors:
        print("\nOutput-i nuk ka strukturen e pritur:")
        for error in shape_errors:
            print(f"- {error}")
        return

    try:
        get_rule_info(data)
    except ValueError as error:
        print(f"\n{error}")
        return

    mode = choose_mode()
    if mode is None:
        return

    program_count = len(data["programs"])

    if mode in {"1", "2", "3", "5"}:
        program_index = ask_program_index(program_count)
        if program_index is None:
            return

        if mode == "1":
            report_for_program(data, output_path, program_index)
        elif mode == "2":
            timeline_report(data, output_path, program_index)
        elif mode == "3":
            csv_report(data, output_path, program_index)
        else:
            html_timeline(data, output_path, program_index)

    if mode == "4":
        automatic_validation(data, output_path)


if __name__ == "__main__":
    main()
