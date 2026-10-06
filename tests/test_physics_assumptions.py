"""No-key regression tests for the active physics response contract."""
import math
import unittest
from unittest.mock import patch

from app import create_app
from services.claude_pipeline import manual_pipeline, validate_and_normalize_response


COMPLETE = '斜抛，初速度=20m/s，角度=45°，初始高度=0米，g=9.8m/s²，忽略空气阻力。'


class PhysicsAssumptionsTests(unittest.TestCase):
    def test_complete_input(self):
        result = manual_pipeline(COMPLETE)
        anim = result['animation_instructions']
        self.assertEqual(result['assumptions'], [])
        self.assertEqual(result['warnings'], [])
        self.assertEqual((anim['initial_speed'], anim['angle'], anim['initial_y']), (20, 45, 0))
        self.assertAlmostEqual(anim['duration'], 2 * 20 * math.sin(math.pi / 4) / 9.8)
        self.assertIsNone(anim['mass'])

    def test_gravity_assumption(self):
        result = manual_pipeline(COMPLETE.replace('g=9.8m/s²，', ''))
        self.assertEqual(result['assumptions'], [{
            'parameter': 'gravity', 'value': 9.8,
            'reason': '题目未给出重力加速度，假设地球标准重力 g=9.8 m/s²。',
        }])
        self.assertEqual(result['animation_instructions']['gravity'], 9.8)

    def test_missing_essentials_block_animation(self):
        for text, missing in [
            ('斜抛，角度=45°，高度=0米，g=9.8', 'initial_speed'),
            ('斜抛，初速度=20m/s，高度=0米，g=9.8', 'angle'),
            ('水平抛出，初速度=10m/s，g=9.8', 'initial_height'),
            ('自由落体，g=9.8', 'initial_height'),
        ]:
            with self.subTest(text=text):
                result = manual_pipeline(text)
                self.assertIsNone(result['animation_instructions'])
                self.assertTrue(any(missing in w for w in result['warnings']))

    def test_final_speed_or_acceleration_is_not_initial_speed(self):
        for text in ['斜抛，落地速度=20m/s，角度=45°', '斜抛，重力加速度=9.8m/s²，角度=45°']:
            result = manual_pipeline(text)
            self.assertIsNone(result['parameters']['initial_speed'])
            self.assertIsNone(result['animation_instructions'])

    def test_unsupported_units_and_partial_numeric_values_do_not_animate(self):
        for text in [COMPLETE.replace('20m/s', '20km/h'), COMPLETE.replace('0米', '20cm'),
                     COMPLETE.replace('45°', '1rad'), COMPLETE + '质量=500g',
                     COMPLETE.replace('20m/s', '1e3m/s'), COMPLETE.replace('20m/s', '1/2m/s')]:
            with self.subTest(text=text):
                result = manual_pipeline(text)
                self.assertIsNone(result['animation_instructions'])
                self.assertTrue(result['warnings'])

    def test_zero_values_are_preserved(self):
        for speed, angle, height in [(10, 0, 0), (0, 45, 0), (0, 0, 0), (10.0, 0.0, 0.0), (0.0, 45.0, 0.0)]:
            with self.subTest(speed=speed, angle=angle):
                result = manual_pipeline(f'抛体，初速度={speed}m/s，角度={angle}°，高度={height}米，g=9.8，忽略空气阻力。')
                self.assertEqual(result['warnings'], [])
                anim = result['animation_instructions']
                self.assertEqual((anim['initial_speed'], anim['angle'], anim['initial_y']), (speed, angle, height))
                self.assertEqual(anim['duration'], 0)

    def test_supplied_unsupported_values_are_not_missing_parameter_assumptions(self):
        cases = [
            (COMPLETE.replace('45°', '1/2°'), 'angle'),
            (COMPLETE.replace('0米', '1/2米'), 'initial_height'),
            (COMPLETE.replace('9.8m/s²', '1/2m/s²'), 'gravity'),
            (COMPLETE.replace('9.8m/s²', '1e1m/s²'), 'gravity'),
            (COMPLETE.replace('0米', '.5米'), 'initial_height'),
            ('水平抛出，从1/2米高处以10m/s抛出，g=9.8', 'initial_height'),
            ('抛体，以1/2m/s的初速度，角度=45°，高度=0米，g=9.8', 'initial_speed'),
            ('匀速直线，初速度=10m/s，角度=1/2°，高度=0米', 'angle'),
            ('匀速直线，初速度=10m/s，角度=0°，高度=0米，运动时间=1/2秒', 'duration'),
        ]
        for text, key in cases:
            with self.subTest(text=text, parameter=key):
                result = manual_pipeline(text)
                self.assertIsNone(result['animation_instructions'])
                self.assertIsNone(result['parameters'][key])
                self.assertFalse(any(a['parameter'] == key for a in result['assumptions']))
                self.assertTrue(any(key in w for w in result['warnings']))

    def test_free_fall_zero_height_is_not_replaced(self):
        result = manual_pipeline('自由落体，高度=0米，g=9.8')
        self.assertEqual(result['animation_instructions']['initial_y'], 0)
        self.assertEqual(result['animation_instructions']['duration'], 0)

    def test_uniform_window_and_direction_are_explicit(self):
        result = manual_pipeline('匀速直线，初速度=0m/s，高度=0米')
        assumptions = {a['parameter']: a['value'] for a in result['assumptions']}
        self.assertEqual(assumptions, {'angle': 0, 'duration': 5})
        self.assertIsNone(result['animation_instructions']['gravity'])
        self.assertEqual(result['animation_instructions']['initial_speed'], 0)
        specified = manual_pipeline('匀速直线，初速度=10m/s，角度=0°，高度=0米，运动时间=0秒')
        self.assertEqual(specified['animation_instructions']['duration'], 0)

    def test_invalid_and_unsupported_inputs_are_not_substituted(self):
        for text in [COMPLETE.replace('g=9.8', 'g=0'), COMPLETE.replace('20m/s', '-20m/s'),
                     COMPLETE.replace('0米', '-2米'), COMPLETE + '质量=0kg',
                     '斜面，初速度=10m/s，角度=30°', '匀速圆周，角度=45°',
                     '随便一个物理题', COMPLETE + '考虑空气阻力', COMPLETE + '反弹']:
            with self.subTest(text=text):
                result = manual_pipeline(text)
                self.assertIsNone(result['animation_instructions'])
                self.assertTrue(result['warnings'])

    def test_model_cannot_invent_parameters_or_animation(self):
        result = validate_and_normalize_response({
            'problem_text': '斜抛，角度=45°，高度=0米，g=9.8',
            'problem_type': 'projectile', 'parameters': {'initial_speed': 20},
            'animation_instructions': {'type': 'projectile', 'initial_speed': 20},
            'solution_steps': ['Pretend the speed is known'],
        })
        self.assertIsNone(result['animation_instructions'])
        self.assertIsNone(result['parameters']['initial_speed'])
        self.assertNotIn('Pretend the speed is known', result['solution_steps'])

    def test_model_conflict_is_flagged_and_blocks_animation(self):
        result = validate_and_normalize_response({
            'problem_text': COMPLETE, 'problem_type': 'projectile',
            'parameters': {'initial_speed': 999},
        })
        self.assertEqual(result['parameters']['initial_speed'], 20)
        self.assertIsNone(result['animation_instructions'])
        self.assertTrue(result['warnings'])

    def test_model_uses_same_assumption_policy(self):
        text = COMPLETE.replace('g=9.8m/s²，', '')
        self.assertEqual(validate_and_normalize_response({'problem_text': text, 'problem_type': 'projectile'}),
                         manual_pipeline(text))

    def test_model_cannot_relabel_an_inclined_plane_as_a_projectile(self):
        result = validate_and_normalize_response({
            'problem_text': '斜面，初速度=20m/s，角度=45°，高度=0米，g=9.8',
            'problem_type': 'projectile',
        })
        self.assertEqual(result['problem_type'], 'inclined_plane')
        self.assertIsNone(result['animation_instructions'])
        self.assertTrue(result['warnings'])

    def test_upload_contract_without_claude(self):
        client = create_app().test_client()
        with patch('services.claude_pipeline.call_claude_pipeline', side_effect=AssertionError('No API call allowed')):
            for text in [COMPLETE, '水平抛出，初速度=10m/s']:
                response = client.post('/upload', data={'manual_text': text})
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertEqual(data['problem_text'], text)
                self.assertNotIn('ocr_text', data)
                self.assertIsInstance(data['assumptions'], list)
                self.assertIsInstance(data['warnings'], list)
                self.assertIsInstance(data['solution_steps'], list)
                self.assertEqual(data['animation_instructions'], manual_pipeline(text)['animation_instructions'])
        html = client.get('/').get_data(as_text=True)
        self.assertIn('id="assumptionsContainer"', html)
        self.assertIn('id="warningsContainer"', html)


if __name__ == '__main__':
    unittest.main()
