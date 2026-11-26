import json
import os
from datetime import datetime, timedelta, timezone

import requests

LEETCODE_API = "https://leetcode.com/graphql"
LEETCODE_USERS = [
    "brandonpy",
    "harshypoo",
    "youngneezy",
    "amarz45",
]
DAILY_CHALLENGE_QUERY = """
query questionOfToday {
  activeDailyCodingChallengeQuestion {
    date
    question {
      questionFrontendId
      title
      titleSlug
      difficulty
    }
  }
}
"""
USER_CALENDAR_QUERY = """
query userActivity($username: String!) {
  matchedUser(username: $username) {
    userCalendar {
      submissionCalendar
    }
  }
}
"""
DIFFICULTY_COLORS = {
    "Easy": 0x00AF9B,
    "Medium": 0xFFB800,
    "Hard": 0xFF2D55,
}


def get_daily_problem():
    response = requests.post(
        LEETCODE_API,
        json={"query": DAILY_CHALLENGE_QUERY},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if result.get("errors"):
        raise RuntimeError(f"LeetCode GraphQL error: {result['errors']}")

    challenge = (
        result.get("data", {}).get("activeDailyCodingChallengeQuestion")
    )
    question = challenge.get("question") if challenge else None
    if not challenge or not challenge.get("date") or not question:
        raise RuntimeError("LeetCode did not return a daily problem")

    required_fields = (
        "questionFrontendId",
        "title",
        "titleSlug",
        "difficulty",
    )
    if any(not question.get(field) for field in required_fields):
        raise RuntimeError("LeetCode returned incomplete daily problem data")

    return {
        "date": challenge.get("date"),
        "id": question["questionFrontendId"],
        "title": question["title"],
        "slug": question["titleSlug"],
        "difficulty": question["difficulty"],
    }


def get_user_activity(username):
    response = requests.post(
        LEETCODE_API,
        json={
            "query": USER_CALENDAR_QUERY,
            "variables": {"username": username},
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if result.get("errors"):
        raise RuntimeError(
            f"LeetCode calendar error for {username}: {result['errors']}"
        )

    matched_user = result.get("data", {}).get("matchedUser")
    if not matched_user:
        raise ValueError(f"LeetCode user not found: {username}")

    calendar = matched_user.get("userCalendar")
    serialized_calendar = (
        calendar.get("submissionCalendar") if calendar else None
    )
    if serialized_calendar is None:
        raise RuntimeError(f"LeetCode returned no calendar for {username}")

    try:
        submissions_by_timestamp = json.loads(serialized_calendar)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"LeetCode returned an invalid calendar for {username}"
        ) from error

    if not isinstance(submissions_by_timestamp, dict):
        raise RuntimeError(
            f"LeetCode returned an invalid calendar for {username}"
        )

    active_dates = set()
    try:
        for timestamp, submission_count in submissions_by_timestamp.items():
            if int(submission_count) > 0:
                active_dates.add(
                    datetime.fromtimestamp(
                        int(timestamp), tz=timezone.utc
                    ).date()
                )
    except (OverflowError, OSError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"LeetCode returned invalid calendar dates for {username}"
        ) from error

    return active_dates


def create_embed(problem):
    difficulty = problem["difficulty"]
    return {
        "title": f"{problem['id']}. {problem['title']}",
        "url": f"https://leetcode.com/problems/{problem['slug']}/",
        "description": f"Difficulty: **{difficulty}**",
        "color": DIFFICULTY_COLORS.get(difficulty, 0x5865F2),
        "footer": {"text": f"LeetCode Daily Challenge | {problem['date']}"},
    }


def create_activity_embeds(user_activity, report_date):
    month_start = report_date.replace(day=1)
    monthly_active_days = [
        (
            username,
            sum(
                month_start <= active_date <= report_date
                for active_date in dates
            ),
        )
        for username, dates in user_activity
    ]
    leaderboard = sorted(
        monthly_active_days, key=lambda entry: entry[1], reverse=True
    )[:5]
    leaderboard_text = "\n".join(
        f"{position}. **{username}** — {active_days} active "
        f"{'day' if active_days == 1 else 'days'}"
        for position, (username, active_days) in enumerate(leaderboard, start=1)
    )
    leaderboard_embed = {
        "title": f"Monthly Leaderboard — {report_date.strftime('%B %Y')}",
        "description": leaderboard_text or "No submissions this month yet.",
        "color": 0xFEE75C,
    }

    active_yesterday = []
    inactive_yesterday = []
    for username, active_dates in user_activity:
        if report_date not in active_dates:
            inactive_yesterday.append(username)
            continue

        streak = 0
        streak_date = report_date
        while streak_date in active_dates:
            streak += 1
            streak_date -= timedelta(days=1)
        active_yesterday.append((username, streak))

    streak_text = "\n".join(
        f"**{username}** — {streak}-day streak"
        for username, streak in active_yesterday
    )
    streak_embed = {
        "title": f"Submission Streaks — {report_date.isoformat()}",
        "description": streak_text or "No tracked users submitted yesterday.",
        "color": 0x57F287,
    }

    no_submission_embed = {
        "title": f"No LeetCode Submissions — {report_date.isoformat()}",
        "description": (
            "\n".join(inactive_yesterday)
            if inactive_yesterday
            else "Everyone submitted something!"
        ),
        "color": 0xED4245,
    }
    return [leaderboard_embed, streak_embed, no_submission_embed]


def send_discord_report(embeds):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    response = requests.post(
        webhook_url,
        json={"embeds": embeds},
        timeout=30,
    )
    response.raise_for_status()


def main():
    problem = get_daily_problem()
    report_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    user_activity = [
        (username, get_user_activity(username))
        for username in LEETCODE_USERS
    ]
    embeds = [create_embed(problem)]
    embeds.extend(create_activity_embeds(user_activity, report_date))
    send_discord_report(embeds)
    print("Daily LeetCode report sent to Discord.")


if __name__ == "__main__":
    main()
