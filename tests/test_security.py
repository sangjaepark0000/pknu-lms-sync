import unittest

from pknu_lms_sync.security import same_origin


class SecurityTest(unittest.TestCase):
    def test_same_origin_accepts_only_pknu_https(self):
        self.assertEqual(same_origin("/ilos/test"), "https://lms.pknu.ac.kr/ilos/test")
        with self.assertRaises(ValueError):
            same_origin("https://example.com/steal")
        with self.assertRaises(ValueError):
            same_origin("http://lms.pknu.ac.kr/insecure")


if __name__ == "__main__":
    unittest.main()
