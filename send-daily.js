async function main() {
  if (!process.env.DISCORD_WEBHOOK_URL) {
    throw new Error("DISCORD_WEBHOOK_URL is not configured");
  }

  const leetcodeResponse = await fetch("https://leetcode.com/graphql", {
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

  if (!leetcodeResponse.ok) {
    throw new Error(`LeetCode returned ${leetcodeResponse.status}`);
  }

  const { data, errors } = await leetcodeResponse.json();
  if (errors?.length) {
    throw new Error(errors[0].message);
  }

  const problem = data?.activeDailyCodingChallengeQuestion?.question;
  if (!problem) {
    throw new Error("LeetCode did not return a daily problem");
  }

  const discordResponse = await fetch(process.env.DISCORD_WEBHOOK_URL, {
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

  if (!discordResponse.ok) {
    throw new Error(`Discord returned ${discordResponse.status}`);
  }

  console.log("Daily LeetCode problem sent to Discord.");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
