function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-gray-300">{title}</h2>
      {children}
    </section>
  )
}

function TabCard({
  name,
  route,
  children,
}: {
  name: string
  route: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium text-white">{name}</h3>
        <code className="text-[11px] text-gray-500">{route}</code>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{children}</p>
    </div>
  )
}

export default function Info() {
  return (
    <div className="flex flex-col gap-8 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold">Info</h1>
        <p className="text-gray-400 text-sm mt-1">
          What this bot does, and what each tab is for.
        </p>
      </div>

      <Section title="What this bot can do">
        <div className="bg-gray-800 rounded-lg p-4">
          <p className="text-sm text-gray-300 leading-relaxed">
            An AI agent (Google Gemini) drives a real, logged-in Instagram browser
            session on your behalf. You give it a goal in plain English — it decides
            which posts to look at, whether they're worth engaging with, and what
            actions to take, the same way a person browsing Instagram would.
          </p>
          <ul className="mt-3 grid sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-gray-400 list-disc list-inside">
            <li>Browse hashtags, the Explore page, and Reels</li>
            <li>Read a post and decide if it's worth engaging with</li>
            <li>Like posts and individual comments</li>
            <li>Write and post a genuine, context-aware comment</li>
            <li>Reply to other people's comments</li>
            <li>Follow / unfollow accounts</li>
            <li>Send a personalized first DM, and reply to DM conversations</li>
            <li>Search for and open specific accounts, view followers/following</li>
            <li>Save a post, share a post via DM, follow a hashtag</li>
            <li>Post your own photo with an AI-written caption</li>
            <li>Read your notifications</li>
          </ul>
          <p className="text-xs text-gray-500 mt-3">
            Every goal names its own topic/niche — the bot never assumes real
            estate or any fixed subject; it derives hashtags and relevance
            criteria from what you actually typed.
          </p>
        </div>
      </Section>

      <Section title="Safety, always on">
        <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1.5">
          <p className="text-xs text-gray-400">
            • Hard per-session caps on comments/likes/follows/DMs/replies — the bot
            cannot exceed them no matter what a goal asks for (edit them in{' '}
            <span className="text-gray-200">Settings</span>).
          </p>
          <p className="text-xs text-gray-400">
            • Never comments on, or DMs, the same post/person twice — checked
            against permanent history, not just this session.
          </p>
          <p className="text-xs text-gray-400">
            • Only one browser session runs at a time for your account, to avoid
            Instagram flagging concurrent logins.
          </p>
        </div>
      </Section>

      <Section title="Tabs">
        <div className="grid sm:grid-cols-2 gap-3">
          <TabCard name="Integration" route="/">
            Log in to Instagram once, in a live mirror of the browser the bot
            uses. After you save the session, this tab shows "Connected" instead
            of the mirror — reopen it any time to re-login or watch the browser
            live. Also where you sign out of Instagram entirely.
          </TabCard>

          <TabCard name="Bot" route="/bot">
            Type a single goal and run it now (e.g. "comment on 3 posts about
            coffee shops and like them"). Goals queue if one is already running.
            Shows the live log and each goal's status: pending, processing, done,
            or error.
          </TabCard>

          <TabCard name="Day Plan" route="/day-plan">
            Describe an entire day's activity at once. Gemini splits it into
            several small sessions with randomized breaks between them (related
            actions on the same post are kept in one session). Review and edit
            the plan before starting — it then runs automatically through the
            day, respecting daily caps, and survives server restarts.
          </TabCard>

          <TabCard name="Posts" route="/posts">
            Upload photos/videos for the bot to post to your feed, with an
            optional "Write with AI" button that looks at the actual photo and
            writes a caption. Each upload is posted at most once — the Queue
            section shows what's waiting, Posted shows what's already gone live
            with a link to the real post.
          </TabCard>

          <TabCard name="Analytics" route="/analytics">
            Totals for comments/likes/DMs/follows/replies, an activity chart,
            goal outcomes, unique reach (posts commented on, people DM'd,
            accounts followed), and Gemini API cost — total spend, average per
            session, and a daily spend chart.
          </TabCard>

          <TabCard name="Prompts" route="/prompts">
            The actual text prompts sent to Gemini — the system prompt, post
            evaluator, comment writer, caption writer, and day planner. Edit and
            save any of them; changes take effect on the bot's next run with no
            redeploy. Reset any prompt back to its built-in default.
          </TabCard>

          <TabCard name="Settings" route="/settings">
            Session caps (max comments/likes/follows/DMs/replies, session
            length), the fallback hashtag used when a goal names no specific
            topic, and Day Plan defaults (break length range, daily caps across
            a whole day). Takes effect on the next session — no restart needed.
          </TabCard>

          <TabCard name="History" route="/history">
            Every past session: goal, what it did, tokens used, Gemini cost, how
            long it ran, and its outcome. Click a row to see the full breakdown.
          </TabCard>
        </div>
      </Section>
    </div>
  )
}
