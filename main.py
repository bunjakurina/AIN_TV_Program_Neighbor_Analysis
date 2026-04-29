import json
import tracemalloc
from pathlib import Path

from neighbor_engine import (
    flatten_programs,
    neighbor_counts,
    prepare_sorted_programs,
    premier_params_to_dict,
    validate_advanced_delta_edge,
    validate_basic_edge,
    validate_premier_edge,
)
from basic_neighbors import calculate_statistics as basic_stats
from basic_neighbors import generate_basic_neighbors
from advanced_neighbors import calculate_statistics as advanced_stats
from advanced_neighbors import generate_advanced_neighbors
from premier_neighbors import calculate_statistics as premier_stats
from premier_neighbors import default_premier_params
from premier_neighbors import generate_premier_neighbors
from premier_neighbors import PREMIER_MAX_OUTPUT_BYTES_ESTIMATE, premier_should_skip_json_write


INSTANCES_DIR = Path("instances")
OUTPUT_DIR = Path("output")
DEFAULT_DELTA = 30

# Beyond this program count, only summary JSON is written (no neighbor_indices / programs).
LARGE_PROGRAM_COUNT_THRESHOLD = 100_000


INSTANCE_ORDER = [
    "toy.json",
    "croatia_tv_input.json",
    "germany_tv_input.json",
    "kosovo_tv_input.json",
    "netherlands_tv_input.json",
    "uk_tv_input.json",
    "usa_tv_input.json",
    "australia_iptv.json",
    "france_iptv.json",
    "spain_iptv.json",
    "uk_iptv.json",
    "us_iptv.json",
    "singapore_pw.json",
    "canada_pw.json",
    "china_pw.json",
    "youtube_gold.json",
    "youtube_premium.json",
]

INSTANCE_DISPLAY_NAMES = {
    "toy.json": "Toy instance",
    "croatia_tv_input.json": "croatia_tv",
    "germany_tv_input.json": "germany_tv",
    "kosovo_tv_input.json": "kosovo_tv",
    "netherlands_tv_input.json": "netherlands_tv",
    "uk_tv_input.json": "uk_tv",
    "usa_tv_input.json": "usa_tv",
}


def load_instance(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def bytes_to_mb(value):
    return value / (1024 * 1024)


def get_instance_files():
    existing_files = {file_path.name: file_path for file_path in INSTANCES_DIR.glob("*.json")}
    ordered_files = [
        existing_files[file_name]
        for file_name in INSTANCE_ORDER
        if file_name in existing_files
    ]
    extra_files = sorted(
        file_path
        for file_name, file_path in existing_files.items()
        if file_name not in INSTANCE_ORDER
    )
    return ordered_files + extra_files


def display_instance_name(file_path):
    return INSTANCE_DISPLAY_NAMES.get(file_path.name, file_path.stem)


def print_instances(instance_files):
    print("\nZgjedh instancen:\n")
    for index, file_path in enumerate(instance_files):
        print(f"{index}. {display_instance_name(file_path)}")


def validate_neighbors(programs, neighbors, variant, delta=None, premier_params=None):
    errors = []

    if len(neighbors) != len(programs):
        errors.append(
            f"Numri i listave te fqinjeve ({len(neighbors)}) nuk perputhet "
            f"me numrin e programeve ({len(programs)})."
        )
        return errors

    for i, neighbor_list in enumerate(neighbors):
        for neighbor_index in neighbor_list:
            if not isinstance(neighbor_index, int):
                errors.append(
                    f"Fqinji i programit {i} nuk eshte indeks numerik: {neighbor_index}"
                )
                continue

            if neighbor_index < 0 or neighbor_index >= len(programs):
                errors.append(
                    f"Fqinji i programit {i} eshte jashte intervalit: {neighbor_index}"
                )
                continue

            if neighbor_index == i:
                errors.append(f"Programi {i} eshte fqinj me vetveten.")
                continue

            candidate = programs[neighbor_index]

            if candidate["start"] < programs[i]["start"]:
                errors.append(f"Programi {i} ka fqinj {neighbor_index} qe fillon para tij.")

            if variant == "basic":
                if not validate_basic_edge(programs, i, neighbor_index):
                    errors.append(f"Programi {i} ka fqinj {neighbor_index} jo-valid sipas basic.")

            elif variant == "advanced":
                if not validate_advanced_delta_edge(programs, i, neighbor_index, delta):
                    errors.append(
                        f"Programi {i} ka fqinj {neighbor_index} jashte dritares kohore (advanced)."
                    )

            elif variant == "premier":
                if premier_params is None or not validate_premier_edge(
                    programs, i, neighbor_index, premier_params
                ):
                    errors.append(
                        f"Programi {i} ka fqinj {neighbor_index} jo-valid sipas premier."
                    )

    return errors


def write_output(
    file_name,
    variant,
    delta,
    programs,
    neighbors,
    stats,
    validation_errors,
    premier_params=None,
):
    OUTPUT_DIR.mkdir(exist_ok=True)

    instance_name = Path(file_name).stem
    if variant == "advanced":
        delta_part = f"_delta{delta}" if delta is not None else ""
        output_path = OUTPUT_DIR / f"{instance_name}_{variant}{delta_part}.json"
    elif variant == "premier":
        output_path = OUTPUT_DIR / f"{instance_name}_premier.json"
    else:
        output_path = OUTPUT_DIR / f"{instance_name}_basic.json"

    n = len(programs)
    max_n, min_n, avg_n = stats[0], stats[1], stats[2]

    if n > LARGE_PROGRAM_COUNT_THRESHOLD:
        slim = {
            "instance": file_name,
            "variant": variant,
            "delta": delta,
            "program_count": n,
            "statistics": {
                "max_neighbors": max_n,
                "min_neighbors": min_n,
                "avg_neighbors": avg_n,
            },
        }
        text = json.dumps(slim, ensure_ascii=False, indent=2)
        print("\n--- Permbledhje output (>100k programe; vetem statistika) ---")
        print(text)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        return output_path

    if variant == "premier":
        skip, est = premier_should_skip_json_write(programs, neighbors)
        if skip:
            mb_lim = PREMIER_MAX_OUTPUT_BYTES_ESTIMATE / (1024 * 1024)
            print(
                f"\nPremier: estimimi i madhesis se JSON (~{est / (1024 * 1024):.1f} MB) "
                f"tejkalon limitin (~{mb_lim:.0f} MB). Output-i i plote nuk u ruajt."
            )
            print("Rregullo PREMIER_MAX_OUTPUT_MB (environment) ose ul limitin ne premier_neighbors.py.")
            return None

    output = {
        "instance": file_name,
        "variant": variant,
        "delta": delta,
        "program_count": n,
        "statistics": {
            "max_neighbors": max_n,
            "min_neighbors": min_n,
            "avg_neighbors": avg_n,
        },
        "neighbor_counts": neighbor_counts(neighbors),
        "validation": {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
        },
        "programs": [
            {
                "index": program["global_index"],
                "program_id": program["program_id"],
                "channel_id": program["channel_id"],
                "start": program["start"],
                "end": program["end"],
                "genre": program["genre"],
                "score": program["score"],
            }
            for program in programs
        ],
        "neighbor_indices": neighbors,
    }

    if variant == "premier" and premier_params is not None:
        output["premier_params"] = premier_params_to_dict(premier_params)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    tracemalloc.start()

    print("=== Program Neighbors Generator ===")

    instance_files = get_instance_files()
    if not instance_files:
        print(f"Nuk u gjet asnje instance JSON ne folderin: {INSTANCES_DIR}")
        return

    print("\nZgjedh variantin:")
    print("1. Basic variant - only overlap (bisect i shpejte)")
    print("2. Advanced variant - future time-window delta (bisect i shpejte)")
    print("3. Premier variant - channel-aware + horizon i zgjeruar (optimized)")

    variant = input("\nShkruaj 1, 2 ose 3: ").strip()

    if variant not in ["1", "2", "3"]:
        print("Variant i pavlefshem.")
        return

    print_instances(instance_files)
    instance_choice = input("\nShkruaj numrin e instances: ").strip()

    try:
        instance_index = int(instance_choice)
    except ValueError:
        print("Instance e pavlefshme.")
        return

    if instance_index < 0 or instance_index >= len(instance_files):
        print("Instance e pavlefshme.")
        return

    file_path = instance_files[instance_index]
    file_name = file_path.name

    instance = load_instance(file_path)
    programs = flatten_programs(instance)
    programs, starts = prepare_sorted_programs(programs)

    premier_params = None
    delta = None

    print(f"\nInstanca: {file_name}")
    print(f"Numri total i programeve: {len(programs)}")

    if variant == "1":
        neighbors = generate_basic_neighbors(programs, starts)
        stats = basic_stats(neighbors)
        variant_name = "basic"
        print("\nVarianti: Basic - vetem overlap")

    elif variant == "2":
        delta = DEFAULT_DELTA
        neighbors = generate_advanced_neighbors(programs, starts, delta)
        stats = advanced_stats(neighbors)
        variant_name = "advanced"
        print("\nVarianti: Advanced - dritare kohore me delta")
        print(f"Delta: {delta} minuta")

    else:
        premier_params = default_premier_params()
        neighbors = generate_premier_neighbors(programs, starts, premier_params)
        stats = premier_stats(neighbors)
        variant_name = "premier"
        print("\nVarianti: Premier - cross-channel horizon i zgjeruar + overlap per te njejtin kanal")
        print(f"Premier params: {premier_params_to_dict(premier_params)}")

    n_programs = len(programs)
    if n_programs > LARGE_PROGRAM_COUNT_THRESHOLD:
        validation_errors = []
    else:
        validation_errors = validate_neighbors(
            programs,
            neighbors,
            variant_name,
            delta=delta,
            premier_params=premier_params,
        )

    output_path = write_output(
        file_name,
        variant_name,
        delta,
        programs,
        neighbors,
        stats,
        validation_errors,
        premier_params=premier_params,
    )

    max_n, min_n, avg_n = stats

    if n_programs <= LARGE_PROGRAM_COUNT_THRESHOLD:
        print("\n--- Statistikat ---")
        print(f"Max no. of neighbours: {max_n}")
        print(f"Min no. of neighbours: {min_n}")
        print(f"Avg no. of neighbours: {avg_n:.2f}")

        print("\n--- Validimi ---")
        if validation_errors:
            print(f"Validimi deshtoi: {len(validation_errors)} gabime.")
            for error in validation_errors[:20]:
                print(f"- {error}")
            if len(validation_errors) > 20:
                print(f"... edhe {len(validation_errors) - 20} gabime tjera.")
        else:
            print("Validimi kaloi: vektori i fqinjeve respekton rregullat e variantit.")
    else:
        print("\n--- Validimi ---")
        print(
            f"Validimi u anashkalua (>{LARGE_PROGRAM_COUNT_THRESHOLD:,} programe; "
            "kontrolli i plote do te ishte shume i ngadalte)."
        )

    if output_path is not None:
        print(f"\nOutput u ruajt ne: {output_path}")
    else:
        print("\nOutput JSON nuk u ruajt (premier: skedar shume i madh).")

    current_memory, peak_memory = tracemalloc.get_traced_memory()
    instance_file_size = file_path.stat().st_size

    print("\n--- Memory ---")
    print(f"Instance file size: {bytes_to_mb(instance_file_size):.2f} MB")
    if output_path is not None:
        output_file_size = output_path.stat().st_size
        print(f"Output file size: {bytes_to_mb(output_file_size):.2f} MB")
    else:
        print("Output file size: —")
    print(f"Current memory: {bytes_to_mb(current_memory):.2f} MB")
    print(f"Peak memory: {bytes_to_mb(peak_memory):.2f} MB")

    tracemalloc.stop()


if __name__ == "__main__":
    main()
