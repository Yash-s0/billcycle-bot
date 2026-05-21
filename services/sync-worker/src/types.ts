export interface Env {
  DB: D1Database;
}

export interface PushOperation {
  id: string;
  entityType: string;
  entityId: string;
  operationType: string;
  payload: string;
  createdAt: string;
  attempts?: number;
}

export interface PushRequest {
  deviceId: string;
  lastKnownCursor?: string | null;
  operations: PushOperation[];
}

export interface PullRequest {
  deviceId: string;
  cursor?: string | null;
}
