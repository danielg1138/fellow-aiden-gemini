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

if __name__ == '__main__':
    unittest.main()
