import unittest

from pknu_lms_sync.timer import unit_contents


class TimerTest(unittest.TestCase):
    def test_timer_uses_absolute_command_and_hourly_schedule(self):
        service, timer = unit_contents("/home/student/.local/bin/pknu-lms-sync")
        self.assertIn("ExecStart=/home/student/.local/bin/pknu-lms-sync sync", service)
        self.assertIn("OnCalendar=hourly", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main()
