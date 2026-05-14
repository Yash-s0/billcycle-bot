# BillCycle Bot

BillCycle Bot is a Telegram bot for tracking:
- credit cards (safe metadata only)
- transactions with separate discount and cashback tracking
- billing cycles and upcoming due dates
- purchases made for other people
- reimbursements, including partial payments
- monthly and card-level reports

## Tech stack
- Python 3.11+
- aiogram v3
- SQLAlchemy ORM (async)
- PostgreSQL (`asyncpg`)
- Alembic migrations
- APScheduler (daily reminders)
- python-dotenv

## Quick start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and set your Telegram bot token.
4. Make sure PostgreSQL is running and the target database exists.
5. Run the bot:
   ```bash
   python -m src.bot.main
   ```

## Environment variables
Example `.env`:

```env
BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cardbot
TIMEZONE=Asia/Kolkata
```

## Database migrations
Alembic files are included.

- Upgrade to latest:
  ```bash
  alembic upgrade head
  ```
- Create new revision (manual/autogenerate as needed):
  ```bash
  alembic revision -m "your message"
  ```

Note: The app also tries to run `alembic upgrade head` on startup, and falls back to SQLAlchemy `create_all` if migration execution fails.

## Commands
- `/start` - Register user and show welcome
- `/help` - Show command help
- `/add_card` - Add a card
- `/list_cards` - List cards
- `/add_txn` - Add transaction
- `/recent_txns` - Show latest 10 transactions
- `/who_owes_me` - Person-wise pending receivables
- `/mark_paid` - Mark a reimbursement payment
- `/card_summary` - Card cycle summary
- `/monthly_report` - Month-wise report
- `/delete_txn` - Delete your transaction with confirmation
- `/settings` - Basic bot settings info

`/add_txn` behavior notes:
- asks only card + amount upfront, then shows inline buttons for optional fields
- lets you fill only needed fields (merchant/category/date/discount/cashback/reimbursement)
- stores both in DB (`discount_amount`, `cashback_amount`)
- uses `total = amount - discount`
- uses `owes = total - cashback` for reimbursements

## Reminder behavior
A daily scheduler runs at `09:00` in `TIMEZONE` and sends reminders for:
- cards due in 3 days
- cards due tomorrow
- cards due today
- pending reimbursements older than 7 days

## Privacy and security
- Full card numbers are never requested or stored.
- CVV, PIN, OTP, expiry, and passwords are never requested or stored.
- Every query is scoped by the current Telegram user.
- The bot displays card labels using only bank/card nickname and last 4 digits.

## Project structure

```text
src/
  bot/
    __init__.py
    main.py
    config.py
    db.py
    models.py
    keyboards.py
    states.py
    handlers/
      start.py
      cards.py
      transactions.py
      reports.py
      payments.py
    services/
      billing.py
      reports.py
      reminders.py
```
