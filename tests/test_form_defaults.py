import unittest
from dataclasses import asdict
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from simulation import SimulationConfig


class NumberInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            attributes = dict(attrs)
            if attributes.get("type") == "number":
                self.inputs.append(attributes)


class FormDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        page = Path(__file__).resolve().parents[1] / "static" / "index.html"
        parser = NumberInputParser()
        parser.feed(page.read_text(encoding="utf-8"))
        cls.inputs = parser.inputs

    def test_numeric_defaults_respect_browser_min_max_and_step(self):
        for field in self.inputs:
            with self.subTest(field=field.get("name") or field.get("id")):
                value = Decimal(field["value"])
                base = Decimal(field.get("min", "0"))
                self.assertGreaterEqual(value, base)
                if "max" in field:
                    self.assertLessEqual(value, Decimal(field["max"]))
                if field.get("step") != "any":
                    step = Decimal(field.get("step", "1"))
                    self.assertEqual((value - base) % step, 0)

    def test_config_form_defaults_match_backend(self):
        defaults = asdict(SimulationConfig())
        for field in self.inputs:
            name = field.get("name")
            if name:
                with self.subTest(field=name):
                    self.assertEqual(Decimal(field["value"]), Decimal(str(defaults[name])))
