import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import tracker
from PIL import Image


class UserActivityTests(unittest.TestCase):
    @patch("tracker.requests.post")
    def test_get_user_activity_parses_submission_dates(self, post):
        response = post.return_value
        response.json.return_value = {
            "data": {
                "matchedUser": {
                    "profile": {"userAvatar": "https://example.com/avatar.png"},
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
                    },
                    "submitStats": {
                        "acSubmissionNum": [
                            {"difficulty": "All", "count": 110}
                        ]
                    },
                }
            }
        }

        self.assertEqual(
            tracker.get_user_activity("brandonpy"),
            {
                "dates": {date(2026, 11, 24)},
                "avatar_url": "https://example.com/avatar.png",
                "total_solved": 110,
            },
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
                    "dates": {
                        date(2026, 11, 23),
                        date(2026, 11, 24),
                        date(2026, 11, 25),
                    },
                    "avatar_url": "https://example.com/brandonpy.png",
                    "total_solved": 110,
                },
            ),
            (
                "harshypoo",
                {
                    "dates": {date(2026, 11, 20), report_date},
                    "avatar_url": "https://example.com/harshypoo.png",
                    "total_solved": 75,
                },
            ),
            (
                "youngneezy",
                {
                    "dates": {date(2026, 11, 24)},
                    "avatar_url": "https://example.com/youngneezy.png",
                    "total_solved": 24,
                },
            ),
            (
                "amarz45",
                {
                    "dates": set(),
                    "avatar_url": "https://example.com/amarz45.png",
                    "total_solved": 3,
                },
            ),
            (
                "asnorkin",
                {
                    "dates": set(),
                    "avatar_url": "https://example.com/asnorkin.png",
                    "total_solved": 1,
                },
            ),
            (
                "sixthuser",
                {
                    "dates": set(),
                    "avatar_url": "https://example.com/sixthuser.png",
                    "total_solved": 0,
                },
            ),
        ]

        (leaderboard, no_submissions), daily_streaks = (
            tracker.create_activity_report(user_activity, report_date)
        )

        self.assertIn("brandonpy", leaderboard["description"])
        self.assertIn("3 days active", leaderboard["description"])
        self.assertIn("110 problems completed", leaderboard["description"])
        self.assertIn("sixthuser", leaderboard["description"])
        self.assertEqual(leaderboard["description"].count("\n"), 5)
        self.assertEqual(
            daily_streaks,
            [
                (
                    "brandonpy",
                    3,
                    "https://example.com/brandonpy.png",
                ),
                (
                    "harshypoo",
                    1,
                    "https://example.com/harshypoo.png",
                ),
            ],
        )
        self.assertIn("youngneezy", no_submissions["description"])
        self.assertIn("amarz45", no_submissions["description"])
        self.assertNotIn("brandonpy", no_submissions["description"])

    @patch("tracker.load_avatar", return_value=Image.new("RGB", (92, 92)))
    def test_dashboard_renders_streak_cards(self, _load_avatar):
        activity = [
            ("brandonpy", 3, "https://example.com/avatar.png"),
        ]

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "activity.png"
            tracker.create_activity_dashboard(activity, output_path)

            with Image.open(output_path) as dashboard:
                self.assertEqual(dashboard.size, (228, 278))

    def test_dashboard_renders_no_submissions_message(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "activity.png"
            tracker.create_activity_dashboard([], output_path)

            with Image.open(output_path) as dashboard:
                self.assertEqual(dashboard.size, (600, 180))


if __name__ == "__main__":
    unittest.main()
