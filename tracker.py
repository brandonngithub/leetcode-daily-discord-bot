import os

import requests

LEETCODE_API = "https://leetcode.com/graphql"
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


def create_embed(problem):
    difficulty = problem["difficulty"]
    return {
        "title": f"{problem['id']}. {problem['title']}",
        "url": f"https://leetcode.com/problems/{problem['slug']}/",
        "description": f"Difficulty: **{difficulty}**",
        "color": DIFFICULTY_COLORS.get(difficulty, 0x5865F2),
        "footer": {"text": f"LeetCode Daily Challenge | {problem['date']}"},
    }


def send_discord_report(embed):
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=30,
    )
    response.raise_for_status()


def main():
    problem = get_daily_problem()
    send_discord_report(create_embed(problem))
    print("Daily LeetCode problem sent to Discord.")


if __name__ == "__main__":
    main()
