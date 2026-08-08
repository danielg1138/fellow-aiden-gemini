import unittest
import json
from brew_studio.brew_studio import parse_manual_gem_recipe

class TestGeminiParser(unittest.TestCase):

    def test_parse_gem_json_block(self):
        gem_output = """Here is a recipe strategy for your washed Ethiopian coffee:

I chose a 1:16 ratio and a longer bloom duration to highlight floral aromas.

```json
{
  "profileType": 0,
  "title": "Ethiopian Bloom Master",
  "ratio": 16,
  "bloomEnabled": true,
  "bloomRatio": 2.5,
  "bloomDuration": 45,
  "bloomTemperature": 95,
  "ssPulsesEnabled": true,
  "ssPulsesNumber": 2,
  "ssPulsesInterval": 20,
  "ssPulseTemperatures": [95, 93],
  "batchPulsesEnabled": true,
  "batchPulsesNumber": 2,
  "batchPulsesInterval": 25,
  "batchPulseTemperatures": [95, 93]
}
```

Enjoy your pour over!"""

        recipe = parse_manual_gem_recipe(gem_output)
        self.assertEqual(recipe["title"], "Ethiopian Bloom Master")
        self.assertEqual(recipe["ratio"], 16)
        self.assertEqual(recipe["bloomRatio"], 2.5)
        self.assertEqual(recipe["ssPulseTemperatures"], [95, 93])

    def test_parse_raw_json(self):
        raw_json = json.dumps({
            "profileType": 0,
            "title": "Raw JSON Recipe",
            "ratio": 15.5,
            "bloomEnabled": True,
            "bloomRatio": 2.0,
            "bloomDuration": 30,
            "bloomTemperature": 94,
            "ssPulsesEnabled": False,
            "ssPulsesNumber": 1,
            "ssPulsesInterval": 10,
            "ssPulseTemperatures": [94],
            "batchPulsesEnabled": False,
            "batchPulsesNumber": 1,
            "batchPulsesInterval": 10,
            "batchPulseTemperatures": [94]
        })
        recipe = parse_manual_gem_recipe(raw_json)
        self.assertEqual(recipe["title"], "Raw JSON Recipe")
        self.assertEqual(recipe["ratio"], 15.5)

    def test_espresso_profile_validation(self):
        from fellow_aiden.profile import EspressoProfile
        espresso_data = {
            "title": "Modern Light Roast Espresso",
            "dose_grams": 18.0,
            "yield_grams": 45.0,
            "ratio": "1:2.5",
            "temperature_celsius": 94.5,
            "pre_infusion_seconds": 6,
            "pre_infusion_pressure_bar": 2.5,
            "peak_pressure_bar": 8.5,
            "target_shot_time_seconds": 30,
            "grind_recommendation": "Fine - Niche Zero #14"
        }
        validated = EspressoProfile.model_validate(espresso_data)
        self.assertEqual(validated.dose_grams, 18.0)
        self.assertEqual(validated.yield_grams, 45.0)

if __name__ == '__main__':
    unittest.main()
