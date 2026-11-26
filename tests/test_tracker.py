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

    def test_activity_report_creates_leaderboard_and_streaks(self):
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
                    "total_solved": 360,
                },
            ),
            (
                "youngneezy",
                {
                    "dates": {date(2026, 11, 24)},
                    "avatar_url": "https://example.com/youngneezy.png",
                    "total_solved": 47,
                },
            ),
            (
                "amarz45",
                {
                    "dates": set(),
                    "avatar_url": "https://example.com/amarz45.png",
                    "total_solved": 18,
                },
            ),
            (
                "asnorkin",
                {
                    "dates": {
                        date(2026, 11, day) for day in range(1, 26)
                    },
                    "avatar_url": "https://example.com/asnorkin.png",
                    "total_solved": 2386,
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

        leaderboard, daily_streaks = (
            tracker.create_activity_report(user_activity, report_date)
        )

        self.assertEqual(
            leaderboard["title"],
            "🏆 Total Problems Completed",
        )
        self.assertEqual(
            leaderboard["description"].splitlines(),
            [
                "1. **asnorkin** — 2386",
                "2. **brandonpy** — 110",
                "3. **harshypoo** — 360",
                "4. **youngneezy** — 47",
                "5. **amarz45** — 18",
                "6. **sixthuser** — 0",
            ],
        )
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
                (
                    "asnorkin",
                    25,
                    "https://example.com/asnorkin.png",
                ),
            ],
        )
    def test_daily_challenge_embed_shows_dated_heading_and_link(self):
        embed = tracker.create_embed(
            {
                "date": "2026-11-26",
                "id": "3360",
                "title": "Stone Removal Game",
                "slug": "stone-removal-game",
                "difficulty": "Easy",
            }
        )

        self.assertEqual(embed["title"], "Daily Leetcode - November 26th")
        self.assertEqual(
            embed["description"],
            "[3360. Stone Removal Game]"
            "(https://leetcode.com/problems/stone-removal-game/)\n"
            "Difficulty: **Easy**",
        )
        self.assertNotIn("footer", embed)

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
