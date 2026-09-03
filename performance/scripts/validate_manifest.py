"""Validate the endpoint manifest and generate its deterministic P0 plan."""

import argparse
import json
from pathlib import Path

REQUIRED_PROFILES = ("smoke", "load", "stress", "spike")
REQUIRED_FIELDS = ("id", "method", "path", "module", "role", "mutation", "objective", "priority", "traffic_weight", "enabled_profiles")
VALID_PRIORITIES = {"P0", "P1", "P2"}


def load_and_validate_manifest(path):
    with Path(path).open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    endpoints = manifest.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("manifest endpoints must be a non-empty list")
    ids = [endpoint.get("id") for endpoint in endpoints]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate endpoint id")
    for endpoint in endpoints:
        profiles = endpoint.get("enabled_profiles", [])
        invalid = set(profiles) - set(REQUIRED_PROFILES)
        if invalid:
            raise ValueError(f"invalid enabled profile: {sorted(invalid)[0]}")
        missing = set(REQUIRED_PROFILES) - set(profiles)
        if missing:
            raise ValueError(f"missing enabled profile: {sorted(missing)[0]}")
        missing_fields = [field for field in REQUIRED_FIELDS if field not in endpoint]
        if missing_fields:
            raise ValueError(f"missing manifest field: {missing_fields[0]}")
        if endpoint["priority"] not in VALID_PRIORITIES:
            raise ValueError(f"invalid priority: {endpoint['priority']}")
        if not isinstance(endpoint["traffic_weight"], (int, float)) or endpoint["traffic_weight"] <= 0:
            raise ValueError(f"invalid traffic_weight for {endpoint['id']}")
    target = manifest.get("coverage_target", 0.8)
    if not 0 < target <= 1:
        raise ValueError("coverage_target must be between 0 and 1")
    return manifest


def build_coverage_plan(manifest, selected_ids=None):
    endpoints = manifest["endpoints"]
    total_weight = sum(endpoint["traffic_weight"] for endpoint in endpoints)
    ordered = sorted((endpoint for endpoint in endpoints if endpoint["priority"] == "P0"), key=lambda endpoint: (-endpoint["traffic_weight"], endpoint["id"]))
    target = manifest.get("coverage_target", 0.8)
    if selected_ids is None:
        selected_ids = []
        selected_weight = 0
        for endpoint in ordered:
            selected_ids.append(endpoint["id"])
            selected_weight += endpoint["traffic_weight"]
            if selected_weight / total_weight >= target:
                break
    else:
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("duplicate selected endpoint id")
        known_ids = {endpoint["id"] for endpoint in endpoints}
        unknown_ids = set(selected_ids) - known_ids
        if unknown_ids:
            raise ValueError(f"unknown selected endpoint id: {sorted(unknown_ids)[0]}")
        p0_ids = {endpoint["id"] for endpoint in ordered}
        non_p0_ids = set(selected_ids) - p0_ids
        if non_p0_ids:
            raise ValueError(f"selected endpoint must be P0: {sorted(non_p0_ids)[0]}")
        selected = [endpoint for endpoint in ordered if endpoint["id"] in selected_ids]
        selected_ids = [endpoint["id"] for endpoint in selected]
        selected_weight = sum(endpoint["traffic_weight"] for endpoint in selected)
    coverage = selected_weight / total_weight
    if coverage < target:
        raise ValueError(f"selected P0 coverage {coverage:.4%} is below 80% target")
    return {
        "coverage_target": target,
        "normalized_prioritized_traffic_coverage": round(coverage, 10),
        "total_traffic_weight": total_weight,
        "selected_endpoint_ids": selected_ids,
        "selected_endpoints": [endpoint for endpoint in ordered if endpoint["id"] in selected_ids],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parents[1] / "config" / "endpoints.manifest.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = load_and_validate_manifest(args.manifest)
    plan = build_coverage_plan(manifest)
    output = args.output or args.manifest.with_name("coverage-plan.json")
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(manifest['endpoints'])} endpoints")
    print(f"Selected {len(plan['selected_endpoint_ids'])} P0 endpoints")
    print(f"Coverage: {plan['normalized_prioritized_traffic_coverage']:.2%}")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
