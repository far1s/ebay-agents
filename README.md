# EbayAgents — Automated eBay Digital Product Sales

A fully automated multi-agent system that researches trending digital products on eBay, generates professional PDF files, and lists them for sale — with Telegram approval before any listing goes live.

## Architecture

```
Market Agent → Design Agent → Telegram Agent → Listing Agent
                                    ↓
                              Boss Agent (orchestrates + scores)
```

**Tech Stack:** Python 3.11 · CrewAI · FastAPI · Next.js · Supabase · ReportLab · eBay REST API · Telegram Bot

---

## Quick Start

### 1. Clone and set up Python environment

```bash
git clone https://github.com/your-username/ebay-agents.git
cd ebay-agents
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Copy and fill in your environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in all values (see sections below for how to get each key).

### 3. Set up Supabase database

1. Go to [supabase.com](https://supabase.com) → create a free project
2. Open **SQL Editor** → paste the contents of `supabase/schema.sql` → click **Run**
3. Copy your project URL and API keys to `.env`

### 4. Start the backend API

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 6. Run your first pipeline

Click **▶ Run Now** on the dashboard, or:

```bash
python -c "from crew.main_crew import EbayAgentsCrew; EbayAgentsCrew().run()"
```

---

## How to Get Each API Key

### Anthropic (Claude AI)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account → **API Keys** → **Create Key**
3. Copy the `sk-ant-...` key to `ANTHROPIC_API_KEY`

---

### eBay Developer API

1. Go to [developer.ebay.com](https://developer.ebay.com)
2. Sign in with your eBay account → click **My Account** → **Application Keys**
3. Create a new keyset — choose **Sandbox** for testing
4. Copy **App ID**, **Cert ID**, **Dev ID** to your `.env`

**Getting the User Token (for creating listings):**

1. In the eBay Developer portal → **User Tokens** → **Get a Token from eBay via Your Application**
2. Use the OAuth flow to authorise with your seller account
3. Copy the resulting token to `EBAY_USER_TOKEN`

> **Important:** You must have an eBay seller account with payment and fulfillment policies set up.  
> In Seller Hub → Account → create:
> - A **shipping policy** with "No shipping — digital delivery"
> - A **payment policy** (PayPal / managed payments)
> - A **return policy**
>
> The Listing Agent will automatically use the first policy it finds for each type.

**Switching to Production:**
```env
EBAY_SANDBOX_MODE=false
```
Replace sandbox keys with production keys.

---

### Telegram Bot

1. Open Telegram → search for **@BotFather**
2. Send `/newbot` → follow the prompts → give your bot a name and username
3. BotFather gives you a token like `1234567890:AABBCCxx...` → copy to `TELEGRAM_BOT_TOKEN`

**Getting your Chat ID:**
1. Search for **@userinfobot** on Telegram → send `/start`
2. It replies with your user ID (a number like `123456789`) → copy to `TELEGRAM_CHAT_ID`

**Test your bot:**
```bash
python -c "
from tools.telegram_client import TelegramClient
t = TelegramClient()
t.send_message('EbayAgents connected!')
"
```

---

## Deploying to Vercel

### Prerequisites
- [Vercel CLI](https://vercel.com/docs/cli): `npm i -g vercel`
- A GitHub repo with this code

### Steps

1. **Deploy**
   ```bash
   vercel --prod
   ```

2. **Set environment variables** in the Vercel dashboard:
   - Go to your project → **Settings** → **Environment Variables**
   - Add every variable from `.env.example`

3. **Enable cron jobs**
   - Vercel Pro plan required for cron jobs
   - The `vercel.json` already configures the daily 9:00 AM UTC run
   - Alternatively, use any external cron service to call `POST /api/schedule/run`

4. **Set `NEXT_PUBLIC_API_URL`** in dashboard env:
   ```
   NEXT_PUBLIC_API_URL=https://your-project.vercel.app
   ```

---

## Project Structure

```
ebay-agents/
├── agents/           # CrewAI agent definitions
│   ├── boss_agent.py     # Manager/orchestrator
│   ├── market_agent.py   # eBay market research
│   ├── design_agent.py   # PDF generation
│   ├── telegram_agent.py # Approval flow
│   └── listing_agent.py  # eBay listing creation
├── tools/            # Core implementation
│   ├── supabase_client.py
│   ├── ebay_client.py
│   ├── telegram_client.py
│   ├── pdf_generator.py
│   └── market_scraper.py
├── crew/
│   └── main_crew.py  # CrewAI orchestration
├── api/              # FastAPI backend
│   ├── main.py
│   └── routes/
├── dashboard/        # Next.js frontend
├── supabase/
│   └── schema.sql
├── generated_pdfs/   # Auto-created, stores PDF output
├── .env.example
├── requirements.txt
└── vercel.json
```

---

## Free Tier Limitations

| Service | Free Tier Limit | Notes |
|---------|----------------|-------|
| **Supabase** | 500 MB database, 5 GB bandwidth | More than enough to start |
| **Vercel** | 100 GB bandwidth, no cron jobs | Cron requires Pro ($20/mo) |
| **Anthropic** | Pay-per-use (~$0.003/1K tokens) | Each pipeline run ≈ $0.05–0.20 |
| **eBay Sandbox** | Unlimited sandbox calls | Switch to prod when ready |
| **eBay Production** | No listing fees for digital items | eBay takes ~10% final value fee |
| **Telegram** | Unlimited | Free forever |

**Estimated monthly cost (5 runs/day):**
- Anthropic: ~$10–20
- Vercel Pro (for cron): $20
- Supabase: $0
- eBay: $0 to list (% on sales)
- **Total: ~$30–40/month**

---

## Running in Development (No API Keys)

The system includes a **sandbox/fallback mode**:
- eBay sandbox mode (`EBAY_SANDBOX_MODE=true`) uses test servers with no real money
- If the eBay Browse API returns no results (common in sandbox), the Market Scraper falls back to pre-set "calendar" product data
- PDF generation works completely offline — no API calls needed
- Telegram approval works as long as bot token + chat ID are valid

---

## Customisation

### Add a new product type
1. Add generation logic to `tools/pdf_generator.py` in the `generators` dict
2. Add keywords to `PRODUCT_TYPE_KEYWORDS` in `tools/market_scraper.py`
3. Add item specifics to `build_item_specifics()` in `tools/ebay_client.py`

### Change the schedule
- Dashboard → Settings → edit the cron expression
- Or edit `vercel.json` cron directly

### Run multiple pipelines per day
The system prevents concurrent runs. To run multiple products per day, modify `crew/main_crew.py` to loop over multiple product recommendations.

---

## Troubleshooting

**`EBAY_USER_TOKEN` errors:** Your user token may have expired (they last ~18 months). Re-generate via the eBay OAuth flow.

**`No fulfillment policies found`:** Create a digital delivery policy in eBay Seller Hub before listing.

**Telegram approval timeout:** The bot waits up to 24 hours. Check your `TELEGRAM_CHAT_ID` is correct and the bot has been started (`/start`).

**CrewAI version conflicts:** Pin to `crewai>=0.80.0`. CrewAI updates frequently — check the [changelog](https://github.com/crewAIInc/crewAI) if you hit import errors.
