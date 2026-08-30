import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "yg98_cross_ripple.py"
SPEC = importlib.util.spec_from_file_location("yg98_cross_ripple", MODULE_PATH)
APP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP)


class ProfileMigrationTests(unittest.TestCase):
    def test_legacy_two_color_profile_is_migrated(self):
        profile = APP.normalize_profile({
            "press_color": [1, 2, 3],
            "outer_color": [4, 5, 6],
            "speed": 9,
            "life": 1.2,
            "gradient_strength": 0.8,
        })

        self.assertEqual([item["rgb"] for item in profile["colors"]], [[1, 2, 3], [4, 5, 6]])
        self.assertTrue(all(item["enabled"] for item in profile["colors"]))
        self.assertEqual(profile["brightness"], 100.0)
        self.assertEqual(profile["speed"], 9.0)

    def test_profile_always_has_an_enabled_color(self):
        profile = APP.normalize_profile({
            "colors": [
                {"rgb": [10, 20, 30], "enabled": False},
                {"rgb": [40, 50, 60], "enabled": False},
            ]
        })
        self.assertTrue(profile["colors"][0]["enabled"])


class ColorCalculationTests(unittest.TestCase):
    def test_single_color_stays_solid(self):
        self.assertEqual(APP.ripple_rgb([(12, 34, 56)], 5, 10, 1), (12, 34, 56))

    def test_three_color_gradient_hits_each_endpoint_and_midpoint(self):
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        self.assertEqual(APP.ripple_rgb(colors, 0, 10, 1), colors[0])
        self.assertEqual(APP.ripple_rgb(colors, 5, 10, 1), colors[1])
        self.assertEqual(APP.ripple_rgb(colors, 10, 10, 1), colors[2])

    def test_disabled_colors_are_skipped_without_removal(self):
        items = [
            {"rgb": (255, 0, 0), "enabled": True},
            {"rgb": (0, 255, 0), "enabled": False},
            {"rgb": (0, 0, 255), "enabled": True},
        ]
        self.assertEqual(APP.enabled_colors(items), [(255, 0, 0), (0, 0, 255)])
        self.assertEqual(len(items), 3)

    def test_brightness_scaling(self):
        self.assertEqual(APP.scale_rgb((255, 128, 1), 0), (0, 0, 0))
        self.assertEqual(APP.scale_rgb((255, 128, 1), 50), (127, 64, 0))
        self.assertEqual(APP.scale_rgb((255, 128, 1), 100), (255, 128, 1))
        self.assertEqual(APP.scale_rgb((300, -5, 20), 100), (255, 0, 20))


if __name__ == "__main__":
    unittest.main()
