# Astra AI - Demo Video Script

**Target Length:** 1:30 - 2:00
**Aspect Ratio:** 16:9 (YouTube/Portfolio) or 9:16 (Shorts/TikTok)
**Format:** Screen recording of Telegram Desktop split with a stylized terminal showing background agent logs. Voiceover (optional but recommended) or clean text overlays.

---

## The Hook (0:00 - 0:15)

**Visual:** Telegram chat interface with Astra AI open.
**Action:** User types: *"Hey Astra, I'm trying to learn Rust this week."*
**Bot Response:** *"Got it. I'll remember you are focusing on learning Rust."*

**Overlay Text / Voiceover:**
> "Most AI bots forget who you are. Astra AI learns and remembers."

**Visual (Fast Cut):** User types `/memory`. The bot responds with the extracted `pgvector` store data, clearly displaying:
`- User is learning Rust this week.`

---

## Hybrid Task Routing (0:15 - 0:45)

**Overlay Text / Voiceover:**
> "It routes simple questions instantly, and orchestrates complex tasks automatically."

**Visual:** User types a simple question: *"What's the weather like in Paris today?"*
**Bot Response (Instant, <1s):** *"It's currently 15°C and partly cloudy in Paris."* (Show how fast this is).

**Visual:** User types a complex prompt: *"Research the top 3 resources for learning Rust and generate a study plan for me. Put it in my calendar."*

**Bot Response:** 
*"Routing to CrewAI Pipeline: Research & Calendar Agents..."*
*(Show a quick split-screen or pop-up of your terminal where the Python console is logging the CrewAI agents actively scraping the web and talking to each other).*

---

## Human-In-The-Loop Approval (0:45 - 1:15)

**Overlay Text / Voiceover:**
> "And for critical actions, it requires your explicit approval."

**Visual:** The bot finishes the research and pings the user with an interactive Telegram message.

**Bot Response:**
*"I've generated a 3-day Rust Study Plan. I am preparing to add blocks to your Google Calendar."*
*⚠️ [APPROVAL REQUIRED] ⚠️*
*Action: Create 3 Calendar Events for Rust Study.*

*(Show the interactive `[ APPROVE ]` and `[ REJECT ]` Telegram buttons).*

**Action:** User clicks `[ APPROVE ]`.
**Visual:** The bot instantly responds: *"Action Verified. Events created successfully."* 
*(Quick cut to a Google Calendar tab showing the newly created events).*

---

## The Call to Action (1:15 - 1:30)

**Overlay Text / Voiceover:**
> "A dual-layer memory system, hybrid LLM routing, and enterprise-grade safety. Built with Python, LiteLLM, CrewAI, and PostgreSQL."

**Visual:** A clean title card:
**Astra AI**
*Built by [Your Name]*
*GitHub: github.com/Ksawyoux/MyBot-ksawyoux-*

---

## Production Tips for the Recording:
- **Clean the Screen:** Hide your desktop icons and use a clean, dark-mode wallpaper.
- **Telegram Theme:** Ensure Telegram is in Dark Mode (it looks much better for developer tools).
- **Log Visibility:** When showing the terminal, bump the font size up by 2-3 stops so the `[CREWAI AGENT LOGS]` are actually readable on a mobile phone.
- **Pacing:** Speed up any "waiting" periods in editing. Don't make the recruiter watch the bot spin for 60 seconds while CrewAI does web research. Add a small 'Fast Forward' icon. 
