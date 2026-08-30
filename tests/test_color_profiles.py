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
        self.assertEqual(profile["effect"], "cross_ripple")

    def test_effect_is_preserved_and_invalid_values_fall_back(self):
        self.assertEqual(
            APP.normalize_profile({"effect": "radial_ripple"})["effect"],
            "radial_ripple",
        )
        self.assertEqual(
            APP.normalize_profile({"effect": "unknown"})["effect"],
            "cross_ripple",
        )
        self.assertEqual(
            APP.normalize_profile({"effect": "follower"})["effect"],
            "follower",
        )

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


class RadialRippleTests(unittest.TestCase):
    def test_physical_positions_cover_every_active_led(self):
        self.assertEqual(set(APP.PHYSICAL_POS), APP.ACTIVE_LEDS)

    def test_radial_distance_covers_keyboard_and_starts_at_center(self):
        distances = APP.RADIAL_DIST[68]
        self.assertEqual(set(distances), APP.ACTIVE_LEDS)
        self.assertEqual(distances[68], 0.0)
        self.assertAlmostEqual(distances[67], distances[69])

    def test_radial_wave_lives_long_enough_to_reach_farthest_key(self):
        total_life, fade_start = APP.ripple_timing("radial_ripple", 68, 4.0, 1.0)
        farthest = max(APP.RADIAL_DIST[68].values())
        self.assertAlmostEqual(fade_start, farthest / 4.0)
        self.assertAlmostEqual(total_life, fade_start + 1.0)

    def test_cross_ripple_timing_is_unchanged(self):
        self.assertEqual(APP.ripple_timing("cross_ripple", 68, 4.0, 1.0), (1.0, None))


class FollowerTests(unittest.TestCase):
    def test_cycle_color_uses_enabled_color_order(self):
        colors = APP.enabled_colors([
            {"rgb": (255, 0, 0), "enabled": True},
            {"rgb": (0, 255, 0), "enabled": False},
            {"rgb": (0, 0, 255), "enabled": True},
        ])
        first, cursor = APP.cycle_color(colors, 0)
        second, cursor = APP.cycle_color(colors, cursor)
        third, cursor = APP.cycle_color(colors, cursor)
        self.assertEqual((first, second, third), ((255, 0, 0), (0, 0, 255), (255, 0, 0)))

    def test_single_cycle_color_repeats(self):
        color, cursor = APP.cycle_color([(1, 2, 3)], 20)
        self.assertEqual(color, (1, 2, 3))
        self.assertEqual(cursor, 0)

    def test_follower_power_fades_smoothly_to_zero(self):
        self.assertEqual(APP.follower_power(0.0, 1.0), 255)
        self.assertGreater(APP.follower_power(0.5, 1.0), 0)
        self.assertLess(APP.follower_power(0.5, 1.0), 255)
        self.assertEqual(APP.follower_power(1.0, 1.0), 0)

    def test_same_follower_key_replaces_previous_event(self):
        events = [
            {"center": 64, "time": 1.0, "color": (255, 0, 0)},
            {"center": 65, "time": 1.0, "color": (0, 255, 0)},
        ]
        replacement = {"center": 64, "time": 2.0, "color": (0, 0, 255)}
        APP.add_trigger_event(events, replacement, "follower")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1], replacement)
        self.assertEqual([event["center"] for event in events], [65, 64])

    def test_different_follower_keys_can_coexist(self):
        events = []
        APP.add_trigger_event(events, {"center": 64, "time": 1.0, "color": (1, 2, 3)}, "follower")
        APP.add_trigger_event(events, {"center": 65, "time": 1.1, "color": (4, 5, 6)}, "follower")
        self.assertEqual([event["center"] for event in events], [64, 65])


if __name__ == "__main__":
    unittest.main()
