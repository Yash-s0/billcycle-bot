# BillCycle Sync Worker

Cloudflare Worker + D1 scaffold for optional sync.

## Endpoints
- `GET /health`
- `POST /sync/push`
- `POST /sync/pull`

## Local dev
```bash
npm install
npm run dev
```

## Deploy
1. Create a D1 database.
2. Update `database_id` in `wrangler.toml`.
3. Run migrations:
```bash
npx wrangler d1 migrations apply billcycle-sync
```
4. Deploy:
```bash
npm run deploy
```
