import unittest

from handelsregister import parse_id


class DummyContext:
    def __getitem__(self, key):
        return key


class ParseIDTest(unittest.TestCase):
    def _test(self, s, data):
        ctx = {'rev_courts': DummyContext()}
        self.assertEqual(parse_id(s, ctx), data)

    def test_vr(self):
        self._test(
            'Amtsgericht Bonn VR 5752',
            {'court': 'Bonn', 'reg': 'VR', 'id': '5752'},
        )

    def test_hrb(self):
        self._test(
            'Amtsgericht Berlin (Charlottenburg) HRB 61732',
            {'court': 'Berlin (Charlottenburg)', 'reg': 'HRB', 'id': '61732'},
        )

    def test_formerly(self):
        self._test(
            'Amtsgericht Hamm VR 10190 früher Amtsgericht Kamen',
            {'court': 'Hamm', 'reg': 'VR', 'id': '10190'},
        )
