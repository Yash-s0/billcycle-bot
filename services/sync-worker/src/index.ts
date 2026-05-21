import type { Env, PullRequest, PushRequest } from './types';

const json = (body: unknown, status = 200): Response => {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
};

const badRequest = (message: string): Response => json({ error: message }, 400);

async function handlePush(request: Request, env: Env): Promise<Response> {
  const body = (await request.json()) as PushRequest;
  if (!body.deviceId || !Array.isArray(body.operations)) {
    return badRequest('Invalid push payload');
  }

  const acked: string[] = [];
  await env.DB.batch(
    body.operations.map((operation) =>
      env.DB.prepare(
        `
        INSERT OR IGNORE INTO operation_log (
          operation_id, device_id, entity_type, entity_id, operation_type, payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        `,
      ).bind(
        operation.id,
        body.deviceId,
        operation.entityType,
        operation.entityId,
        operation.operationType,
        operation.payload,
        operation.createdAt,
      ),
    ),
  );

  acked.push(...body.operations.map((op) => op.id));

  const cursorRow = await env.DB.prepare('SELECT COALESCE(MAX(seq), 0) AS cursor FROM operation_log').first<{ cursor: number }>();
  const cursor = String(cursorRow?.cursor ?? 0);

  await env.DB.prepare(
    `
    INSERT INTO device_sync_state(device_id, last_cursor, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(device_id) DO UPDATE SET
      last_cursor = excluded.last_cursor,
      updated_at = excluded.updated_at
    `,
  )
    .bind(body.deviceId, Number(cursor), new Date().toISOString())
    .run();

  return json({
    ackedOperationIds: acked,
    serverCursor: cursor,
    conflicts: [],
  });
}

async function handlePull(request: Request, env: Env): Promise<Response> {
  const body = (await request.json()) as PullRequest;
  if (!body.deviceId) {
    return badRequest('Invalid pull payload');
  }

  const cursor = Number(body.cursor ?? 0);
  const rows = await env.DB.prepare(
    `
    SELECT seq, operation_id, device_id, entity_type, entity_id, operation_type, payload, created_at
    FROM operation_log
    WHERE seq > ?
    ORDER BY seq ASC
    LIMIT 200
    `,
  )
    .bind(cursor)
    .all<{
      seq: number;
      operation_id: string;
      device_id: string;
      entity_type: string;
      entity_id: string;
      operation_type: string;
      payload: string;
      created_at: string;
    }>();

  const changes = (rows.results ?? []).map((row) => ({
    id: row.operation_id,
    entityType: row.entity_type,
    entityId: row.entity_id,
    operationType: row.operation_type,
    payload: row.payload,
    createdAt: row.created_at,
    sourceDeviceId: row.device_id,
  }));

  const serverCursor = rows.results && rows.results.length > 0
    ? String(rows.results[rows.results.length - 1].seq)
    : String(cursor);

  await env.DB.prepare(
    `
    INSERT INTO device_sync_state(device_id, last_cursor, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(device_id) DO UPDATE SET
      last_cursor = excluded.last_cursor,
      updated_at = excluded.updated_at
    `,
  )
    .bind(body.deviceId, Number(serverCursor), new Date().toISOString())
    .run();

  return json({
    changes,
    serverCursor,
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/health' && request.method === 'GET') {
      return json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        version: '0.1.0',
      });
    }

    if (url.pathname === '/sync/push' && request.method === 'POST') {
      return handlePush(request, env);
    }

    if (url.pathname === '/sync/pull' && request.method === 'POST') {
      return handlePull(request, env);
    }

    return json({ error: 'Not found' }, 404);
  },
};
