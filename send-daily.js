async function fetchDailyProblem() {
  const response = await fetch("https://leetcode.com/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: `query {
        activeDailyCodingChallengeQuestion {
          question {
            questionFrontendId
            title
            difficulty
            titleSlug
          }
        }
      }`
    })
  });

  if (!response.ok) {
    throw new Error(`LeetCode returned ${response.status}`);
  }

  const { data, errors } = await response.json();
  if (errors?.length) {
    throw new Error(errors[0].message);
  }

  const problem = data?.activeDailyCodingChallengeQuestion?.question;
  if (!problem) {
    throw new Error("LeetCode did not return a daily problem");
  }
  return problem;
}

async function sendToDiscord(problem) {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;
  if (!webhookUrl) {
    throw new Error("DISCORD_WEBHOOK_URL is not configured");
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      embeds: [{
        title: `${problem.questionFrontendId}. ${problem.title}`,
        url: `https://leetcode.com/problems/${problem.titleSlug}/`,
        description: `Difficulty: ${problem.difficulty}`,
        color: problem.difficulty === "Easy" ? 0x00af9b :
          problem.difficulty === "Medium" ? 0xffb800 : 0xff2d55
      }]
    })
  });

  if (!response.ok) {
    throw new Error(`Discord returned ${response.status}`);
  }
}

async function main() {
  await sendToDiscord(await fetchDailyProblem());
  console.log("Daily LeetCode problem sent to Discord.");
}

if (require.main === module) {
  main().catch(error => {
    console.error(error);
    process.exit(1);
  });
}

module.exports = { fetchDailyProblem, sendToDiscord };
