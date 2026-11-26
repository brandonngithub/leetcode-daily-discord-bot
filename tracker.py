import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

LEETCODE_API = "https://leetcode.com/graphql"
LEETCODE_USERS = [
    "brandonpy",
    "harshypoo",
    "youngneezy",
    "amarz45",
    # "asnorkin",
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
USER_ACTIVITY_QUERY = """
query userActivity($username: String!) {
  matchedUser(username: $username) {
    profile {
      userAvatar
    }
    userCalendar {
      submissionCalendar
    }
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
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
        "date": challenge["date"],
        "id": question["questionFrontendId"],
        "title": question["title"],
        "slug": question["titleSlug"],
        "difficulty": question["difficulty"],
    }


def get_user_activity(username):
    response = requests.post(
        LEETCODE_API,
        json={
            "query": USER_ACTIVITY_QUERY,
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

    profile = matched_user.get("profile")
    avatar_url = profile.get("userAvatar") if profile else None
    if not avatar_url:
        raise RuntimeError(f"LeetCode returned no avatar for {username}")

    submit_stats = matched_user.get("submitStats")
    accepted_submissions = (
        submit_stats.get("acSubmissionNum") if submit_stats else None
    )
    total_solved = next(
        (
            entry.get("count")
            for entry in accepted_submissions or []
            if entry.get("difficulty") == "All"
        ),
        None,
    )
    if not isinstance(total_solved, int) or total_solved < 0:
        raise RuntimeError(
            f"LeetCode returned no accepted problem total for {username}"
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

    return {
        "dates": active_dates,
        "avatar_url": avatar_url,
        "total_solved": total_solved,
    }


def create_embed(problem):
    difficulty = problem["difficulty"]
    challenge_date = datetime.strptime(problem["date"], "%Y-%m-%d").date()
    problem_url = f"https://leetcode.com/problems/{problem['slug']}/"
    return {
        "title": f"🧩 Daily Leetcode - {format_report_date(challenge_date)}",
        "url": problem_url,
        "description": (
            f"[{problem['id']}. {problem['title']}]"
            f"({problem_url})\n"
            f"Difficulty: **{difficulty}**"
        ),
        "color": DIFFICULTY_COLORS.get(difficulty, 0x5865F2),
    }


def format_report_date(report_date):
    day = report_date.day
    if 10 < day % 100 < 14:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{report_date.strftime('%B')} {day}{suffix}"


def create_activity_report(user_activity, report_date):
    leaderboard = sorted(
        [
            (
                username,
                sum(
                    report_date.replace(day=1) <= active_date <= report_date
                    for active_date in activity["dates"]
                ),
                activity["total_solved"],
            )
            for username, activity in user_activity
        ],
        key=lambda entry: entry[1],
        reverse=True,
    )
    leaderboard_text = "\n".join(
        f"{position}. **{username}** — {total_solved}"
        for position, (username, _, total_solved) in enumerate(
            leaderboard, start=1
        )
    )
    leaderboard_embed = {
        "title": "🏆 Total Problems Completed",
        "description": leaderboard_text or "No completed problems yet.",
        "color": 0xFEE75C,
    }

    daily_streaks = []
    for username, activity in user_activity:
        active_dates = activity["dates"]
        if report_date not in active_dates:
            continue

        streak = 0
        current_date = report_date
        while current_date in active_dates:
            streak += 1
            current_date -= timedelta(days=1)
        daily_streaks.append(
            (username, streak, activity["avatar_url"])
        )

    return leaderboard_embed, daily_streaks


def load_avatar(avatar_url, username):
    response = requests.get(avatar_url, timeout=30)
    response.raise_for_status()

    try:
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as error:
        raise RuntimeError(f"Unable to decode avatar for {username}") from error


def get_font(size, bold=False):
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_paths = [
        f"/usr/share/fonts/truetype/dejavu/{font_name}",
        f"/Library/Fonts/{font_name}",
    ]

    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def draw_fire_icon(draw, x, y, size=18):
    draw.polygon(
        [
            (x + size * 0.52, y),
            (x + size * 0.82, y + size * 0.42),
            (x + size * 0.72, y + size),
            (x + size * 0.25, y + size),
            (x + size * 0.08, y + size * 0.62),
            (x + size * 0.35, y + size * 0.46),
        ],
        fill="#ff6b35",
    )
    draw.polygon(
        [
            (x + size * 0.53, y + size * 0.38),
            (x + size * 0.68, y + size * 0.7),
            (x + size * 0.58, y + size),
            (x + size * 0.35, y + size * 0.88),
            (x + size * 0.4, y + size * 0.62),
        ],
        fill="#ffd166",
    )


def create_activity_dashboard(activity, output_path):
    if not activity:
        image = Image.new("RGB", (600, 180), "#17181c")
        draw = ImageDraw.Draw(image)
        message = "NO SUBMISSIONS"
        font = get_font(32, bold=True)
        text_bbox = draw.textbbox((0, 0), message, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        draw.text(
            (
                (image.width - text_width) // 2 - text_bbox[0],
                (image.height - text_height) // 2 - text_bbox[1],
            ),
            message,
            fill="#ed4245",
            font=font,
        )
        image.save(output_path, format="PNG")
        return

    card_width = 180
    card_height = 230
    gap = 14
    padding = 24
    image = Image.new(
        "RGB",
        (
            padding * 2 + len(activity) * card_width + (len(activity) - 1) * gap,
            padding * 2 + card_height,
        ),
        "#17181c",
    )
    draw = ImageDraw.Draw(image)

    for index, (username, streak, avatar_url) in enumerate(activity):
        x = padding + index * (card_width + gap)
        y = padding
        draw.rounded_rectangle(
            (x, y, x + card_width, y + card_height),
            radius=16,
            fill="#23252b",
            outline="#3d414b",
            width=2,
        )

        username_font = get_font(15, bold=True)
        username_width = draw.textbbox(
            (0, 0), username, font=username_font
        )[2]
        draw.text(
            (x + (card_width - username_width) // 2, y + 14),
            username,
            fill="#f2f3f5",
            font=username_font,
        )

        avatar = ImageOps.fit(
            load_avatar(avatar_url, username),
            (92, 92),
            method=Image.Resampling.LANCZOS,
        )
        mask = Image.new("L", avatar.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, *avatar.size), fill=255)
        image.paste(avatar, (x + (card_width - 92) // 2, y + 42), mask)

        draw.text(
            (x + 42, y + 158),
            f"{streak} day streak",
            fill="#57f287",
            font=get_font(15, bold=True),
        )
        draw_fire_icon(draw, x + 18, y + 158, size=18)

    image.save(output_path, format="PNG")


def send_discord_report(embeds, image_path):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    response = requests.post(
        webhook_url,
        json={"embeds": embeds},
        timeout=30,
    )
    response.raise_for_status()

    with open(image_path, "rb") as image_file:
        image_response = requests.post(
            webhook_url,
            data={"payload_json": json.dumps({})},
            files={
                "file": ("daily-activity.png", image_file, "image/png"),
            },
            timeout=30,
        )
    image_response.raise_for_status()


def main():
    problem = get_daily_problem()
    report_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    user_activity = []
    for username in LEETCODE_USERS:
        print(f"Checking {username}...")
        user_activity.append((username, get_user_activity(username)))

    leaderboard_embed, daily_streaks = create_activity_report(
        user_activity, report_date
    )
    embeds = [create_embed(problem), leaderboard_embed]

    with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
        create_activity_dashboard(daily_streaks, image_file.name)
        send_discord_report(embeds, image_file.name)

    print("Daily LeetCode report sent to Discord.")


if __name__ == "__main__":
    main()
