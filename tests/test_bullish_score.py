import sys
import unittest
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from traffic_lights import bullish_score, combine, empty_signal


class BullishScoreTests(unittest.TestCase):
    def test_all_state_combinations_use_exact_weights(self):
        for states in product(('up', 'down', 'mixed', 'insufficient'), repeat=3):
            with self.subTest(states=states):
                frames = {key: {'state': state} for key, state in zip(('monthly', 'weekly', 'daily'), states)}
                expected = None if 'insufficient' in states else sum(w for w, s in zip((50, 30, 20), states) if s == 'up')
                self.assertEqual(bullish_score(combine(states), frames), expected)

    def test_gray_stale_missing_and_invalid_states_are_unavailable(self):
        self.assertIsNone(empty_signal()['bullish_score'])
        self.assertIsNone(bullish_score('green', {}))
        self.assertIsNone(bullish_score('yellow', {'monthly': {'state': 'unknown'}}))
        frames = {key: {'state': 'up'} for key in ('monthly', 'weekly', 'daily')}
        self.assertIsNone(bullish_score('gray', frames))
