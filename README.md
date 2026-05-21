# BillCycle Monorepo

This repository now contains three parts:
1. Telegram bot backend (existing Python app).
2. Android-first Flutter mobile app (`apps/mobile`) with offline-first local DB architecture.
3. Optional Cloudflare Worker sync scaffold (`services/sync-worker`) for future cloud sync.

## Workspace Structure

```text
.
├── apps/
│   └── mobile/                 # Flutter + Riverpod + go_router + Drift (local-first)
├── services/
│   └── sync-worker/            # Cloudflare Worker + D1 optional sync API scaffold
├── src/
│   └── bot/                    # Existing Telegram bot
├── alembic/
├── requirements.txt
└── README.md
```

## Mobile App (Flutter)

### Stack
- Flutter + Dart
- Riverpod for state management
- go_router for navigation
- Drift + SQLite for local persistence
- Local-first writes with sync outbox (`pending_operations`)

### Key features implemented
- Dark Android-first app shell with bottom navigation
- Cards: add/edit/delete/list + card summary
- Transactions: add/edit/delete/list with card/UPI/cash modes
- Reports: today/weekly/monthly period summaries
- Receivables: person-wise pending amounts
- Card bill tracker: full/partial payment updates
- Settings: reminder toggles/time + sync controls
- In-app notification center persisted in local DB
- Android transaction notification ingestion:
  - Reads bank/SMS app transaction-style notifications
  - Parses amount + card hint (last 4 / bank/card keywords)
  - Auto-creates local card transaction when confidently matched
  - Falls back to review event in notification center when unmatched
- Optional sync trigger (`run sync now`) if `SYNC_BASE_URL` is configured

### Local DB schema (v1 + migration-ready)
Core tables:
- `cards`
- `people`
- `transactions`
- `payments`
- `card_bill_payments`
- `reminder_settings`
- `reminder_deliveries`
- `notification_events`
- `pending_operations`
- `sync_state`

### Run mobile app
From repo root:
```bash
cd apps/mobile
# one-time bootstrap if platform folders are missing
flutter create --platforms=android .
flutter pub get
flutter run -d android
```

Optional sync endpoint configuration:
```bash
flutter run -d android --dart-define=SYNC_BASE_URL=https://<your-worker-domain>
```

Enable Android transaction message capture:
1. Open app -> Settings -> `Transaction message capture`.
2. Tap `Open notification access settings`.
3. Enable access for BillCycle.
4. Keep card names/notes tagged with last 4 digits (example: `HDFC Regalia 1234`) for higher match accuracy.

### Mobile quality checks
```bash
cd apps/mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter analyze
flutter test
```

## Optional Sync Backend (Cloudflare Worker)

### Endpoints
- `GET /health`
- `POST /sync/push`
- `POST /sync/pull`

### Local run
```bash
cd services/sync-worker
npm install
npm run dev
```

### Deploy
1. Create D1 database.
2. Update `database_id` in `wrangler.toml`.
3. Apply migrations:
```bash
npx wrangler d1 migrations apply billcycle-sync
```
4. Deploy:
```bash
npm run deploy
```

## Existing Telegram Bot (Python)

### Stack
- Python 3.11+
- aiogram v3
- SQLAlchemy ORM (async)
- PostgreSQL (`asyncpg`)
- Alembic migrations
- APScheduler (daily reminders)

### Run bot
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env
python -m src.bot.main
```

### Bot DB migrations
```bash
alembic upgrade head
```

## DB Migration Strategy (Mobile)

Mobile schema versioning is handled in `apps/mobile/lib/core/db/schema_migrations.dart` and applied at app startup.

Policy:
1. Every schema change increments migration version.
2. Each migration includes forward SQL statements.
3. Each migration includes/updates migration tests (`test/unit/db_migration_test.dart`).
4. Breaking data transforms must be documented in release notes.

## Release Notes (Mobile)

### 0.1.0
- Initial offline-first Flutter foundation with local DB + outbox queue.
- Core finance flows implemented for cards/transactions/reports/receivables/card bills.
- Reminder and notification persistence implemented.
- Cloudflare Worker optional sync scaffold added.

## Testing Coverage Included

- Unit:
  - validation rules
  - DB migration bootstrap
  - local-first write + outbox enqueue
- Widget:
  - cards screen rendering
- Golden:
  - placeholder test scaffold (kept skipped until final design assets/fonts are fixed in CI)

## Known TODOs

- Shared expense invite/auth parity with Telegram deep-link collaboration model.
- iOS-specific hardening pass (permissions/background lifecycle behavior).
- Full visual parity pass once final Figma exports/tokens are locked.
