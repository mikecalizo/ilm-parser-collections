import json
import re

def strip_trailing_date(index_name):
    # Remove date pattern like -2024.09.27-000001 from index names
    return re.sub(r'-\d{4}\.\d{2}\.\d{2}-\d{6}$', '', index_name)

def parse_ilm_file(file_path):
    with open(file_path, 'r') as f:
        ilm_data = json.load(f)

    seen = set()  # Keep track of unique index + policy + phase
    rows = []

    for policy_name, policy_info in ilm_data.items():
        if (
            "metrics" in policy_name.lower() or
            ("logs" in policy_name.lower() and "logs-" not in policy_name.lower()) or
            "elastic-agent-ilm" in policy_name.lower() or
            "kibana-event-log-policy" in policy_name.lower()
        ):
            continue

        indices = policy_info.get("in_use_by", {}).get("indices", [])
        phases = policy_info["policy"].get("phases", {})
        retention = phases.get("delete", {}).get("min_age", "N/A")

        # Filter out 'partial' and 'internal' indices
        filtered_indices = [
            idx for idx in indices if not (
                "partial" in idx.lower() or "internal" in idx.lower()
            )
        ]

        for index in filtered_indices:
            short_index = strip_trailing_date(index)

            for phase_name, phase_data in phases.items():
                if phase_name.lower() in ["hot", "cold", "warm", "frozen"]:
                    continue

                # Only include if retention is non-empty
                min_age = phase_data.get("min_age", "N/A")
                if min_age == "N/A" or min_age == "":
                    continue 

                key = (short_index, policy_name, phase_name)
                if key in seen:
                    continue  
                seen.add(key)

                row = [
                    short_index,
                    policy_name,
                    min_age if phase_name == "delete" else "",
                    phase_name
                ]
                rows.append(row)

    print(f"{'Index Name':<80} {'ILM Policy':<25} {'Retention':<10} {'Phase':<10}")
    print("-" * 130)

    for row in rows:
        print(f"{row[0]:<80} {row[1]:<25} {row[2]:<10} {row[3]:<10}")

if __name__ == "__main__":
    parse_ilm_file("ilm_policies.json")
