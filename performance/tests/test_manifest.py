import json
import tempfile
import unittest
from pathlib import Path

from performance.scripts.validate_manifest import (
    REQUIRED_PROFILES,
    build_coverage_plan,
    load_and_validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "performance" / "config" / "endpoints.manifest.json"


class ManifestTests(unittest.TestCase):
    def test_manifest_has_unique_ids_and_all_required_profiles(self):
        manifest = load_and_validate_manifest(MANIFEST)
        ids = [endpoint["id"] for endpoint in manifest["endpoints"]]
        self.assertEqual(len(ids), len(set(ids)))
        for endpoint in manifest["endpoints"]:
            self.assertEqual(set(endpoint["enabled_profiles"]), set(REQUIRED_PROFILES))

    def test_duplicate_ids_are_rejected(self):
        payload = {"endpoints": [{"id": "same"}, {"id": "same"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as file:
            json.dump(payload, file)
            path = Path(file.name)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "duplicate endpoint id"):
            load_and_validate_manifest(path)

    def test_invalid_profiles_are_rejected(self):
        payload = {"endpoints": [{"id": "one", "enabled_profiles": ["smoke", "bogus"]}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as file:
            json.dump(payload, file)
            path = Path(file.name)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "invalid enabled profile"):
            load_and_validate_manifest(path)

    def test_insufficient_selected_coverage_is_rejected(self):
        endpoints = [
            {"id": "p0", "priority": "P0", "traffic_weight": 79},
            {"id": "p1", "priority": "P1", "traffic_weight": 21},
        ]
        with self.assertRaisesRegex(ValueError, "80%"):
            build_coverage_plan({"coverage_target": 0.8, "endpoints": endpoints}, selected_ids=["p0"])

    def test_coverage_plan_selects_descending_weight_with_id_tie_break(self):
        manifest = {
            "coverage_target": 0.8,
            "endpoints": [
                {"id": "z", "priority": "P0", "traffic_weight": 40},
                {"id": "b", "priority": "P0", "traffic_weight": 40},
                {"id": "a", "priority": "P0", "traffic_weight": 20},
            ],
        }
        plan = build_coverage_plan(manifest)
        self.assertEqual(plan["selected_endpoint_ids"], ["b", "z"])
        self.assertEqual(plan["normalized_prioritized_traffic_coverage"], 0.8)

    def test_generated_coverage_plan_meets_target(self):
        manifest = load_and_validate_manifest(MANIFEST)
        plan_path = MANIFEST.with_name("coverage-plan.json")
        self.assertTrue(plan_path.exists())
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(plan["normalized_prioritized_traffic_coverage"], manifest["coverage_target"])
        self.assertEqual(plan["selected_endpoint_ids"], build_coverage_plan(manifest)["selected_endpoint_ids"])


if __name__ == "__main__":
    unittest.main()
