import unittest

from pknu_lms_sync.config import parse_courses, parse_selection, safe_name


class ConfigTest(unittest.TestCase):
    def test_parse_courses_deduplicates_keys_and_uses_title(self):
        html = """
        <div kj="A2026001" kj_auth="S" title="자료구조">긴 자료구조 표시 이름</div>
        <a kj="A2026002" kj_auth="S">컴퓨터 네트워크</a>
        <span kj="A2026001" kj_auth="S">중복</span>
        <span kj="../../bad" kj_auth="S">잘못된 키</span>
        """
        self.assertEqual(parse_courses(html), [
            {"name": "자료구조", "folder": "자료구조", "key": "A2026001"},
            {"name": "컴퓨터 네트워크", "folder": "컴퓨터 네트워크", "key": "A2026002"},
        ])

    def test_selection_defaults_to_all_and_accepts_ranges(self):
        self.assertEqual(parse_selection("", 4), [0, 1, 2, 3])
        self.assertEqual(parse_selection("1, 3-4", 4), [0, 2, 3])
        with self.assertRaises(ValueError):
            parse_selection("5", 4)

    def test_safe_name_removes_path_characters(self):
        self.assertEqual(safe_name("../../bad/name?.pdf"), "_.._bad_name_.pdf")


if __name__ == "__main__":
    unittest.main()
