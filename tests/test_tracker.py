import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

import tracker


class UserActivityTests(unittest.TestCase):
    @patch("tracker.requests.post")
    def test_get_user_activity_parses_submission_dates(self, post):
        response = post.return_value
        response.json.return_value = {
            "data": {
                "matchedUser": {
                    "userCalendar": {
                        "submissionCalendar": json.dumps(
                            {
                                str(
                                    int(
                                        datetime(
                                            2026, 11, 24, tzinfo=timezone.utc
                                        ).timestamp()
                                    )
                                ): 2,
                                str(
                                    int(
                                        datetime(
                                            2026, 11, 25, tzinfo=timezone.utc
                                        ).timestamp()
                                    )
                                ): 0,
                            }
                        )
                    }
                }
            }
        }

        self.assertEqual(
            tracker.get_user_activity("brandonpy"),
            {date(2026, 11, 24)},
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["variables"],
            {"username": "brandonpy"},
        )

    def test_activity_embeds_report_monthly_days_streaks_and_inactive_users(
        self,
    ):
        report_date = date(2026, 11, 25)
        user_activity = [
            (
                "brandonpy",
                {
                    date(2026, 11, 23),
                    date(2026, 11, 24),
                    date(2026, 11, 25),
                },
            ),
            ("harshypoo", {date(2026, 11, 20), report_date}),
            ("youngneezy", {date(2026, 11, 24)}),
            ("amarz45", set()),
        ]

        leaderboard, streaks, no_submissions = (
            tracker.create_activity_embeds(user_activity, report_date)
        )

        self.assertIn("brandonpy", leaderboard["description"])
        self.assertIn("3 active days", leaderboard["description"])
        self.assertIn("3-day streak", streaks["description"])
        self.assertIn("1-day streak", streaks["description"])
        self.assertIn("youngneezy", no_submissions["description"])
        self.assertIn("amarz45", no_submissions["description"])
        self.assertNotIn("brandonpy", no_submissions["description"])


if __name__ == "__main__":
    unittest.main()
