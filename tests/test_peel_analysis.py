import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from peel_analysis import analyze_manifest, summarize_curves


class PeelAnalysisTests(unittest.TestCase):
    def test_width_conversion_uses_raw_force(self):
        frame = pd.DataFrame({"力_1": [0.0, 0.02071, 0.019], "力_2": [0.0, 0.01, 0.005]})
        results = summarize_curves(frame, width_mm=4)
        self.assertAlmostEqual(results[0]["peak_force_per_width_N_per_m"], 5.1775)
        self.assertAlmostEqual(results[1]["peak_force_per_width_N_per_m"], 2.5)

    def test_curves_from_one_batch_do_not_become_independent_batches(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            raw = base / "instrument.csv"
            raw.write_text("力_1,力_2\n0.010,0.020\n0.020,0.010\n", encoding="gb18030")
            manifest = base / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "sample_set_id": "S001",
                            "batch_id": "B001",
                            "formulation_id": "A",
                            "treatment": "untreated",
                            "substrate": "glass",
                            "width_mm": 4,
                            "raw_file": "instrument.csv",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            result = analyze_manifest(manifest)
        self.assertEqual(len(result["curves"]), 2)
        self.assertEqual(result["conditions"][0]["n_independent_batches"], 1)
        self.assertIsNone(result["conditions"][0]["sd_between_batches_N_per_m"])

    def test_width_must_be_measured_positive_value(self):
        with self.assertRaises(ValueError):
            summarize_curves(pd.DataFrame({"力_1": [0.01]}), width_mm=0)


if __name__ == "__main__":
    unittest.main()

