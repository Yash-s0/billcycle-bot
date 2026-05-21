class SchemaMigrations {
  static const int currentVersion = 3;

  static List<String> createStatementsV1() {
    return <String>[
      '''
      CREATE TABLE IF NOT EXISTS cards (
        id TEXT PRIMARY KEY,
        bank_name TEXT NOT NULL,
        card_name TEXT NOT NULL,
        billing_day INTEGER NOT NULL,
        due_day INTEGER NOT NULL,
        credit_limit REAL,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS people (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        created_at TEXT NOT NULL
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        card_id TEXT,
        payment_mode TEXT NOT NULL,
        amount REAL NOT NULL,
        discount_amount REAL NOT NULL DEFAULT 0,
        cashback_amount REAL NOT NULL DEFAULT 0,
        final_amount REAL NOT NULL,
        txn_date TEXT NOT NULL,
        is_for_someone_else INTEGER NOT NULL DEFAULT 0,
        person_id TEXT,
        reimbursement_status TEXT NOT NULL DEFAULT 'own',
        category TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE SET NULL,
        FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE SET NULL
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        person_id TEXT NOT NULL,
        amount_paid REAL NOT NULL,
        paid_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
        FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS pending_operations (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS sync_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        device_id TEXT NOT NULL,
        server_cursor TEXT,
        last_sync_at TEXT,
        sync_enabled INTEGER NOT NULL DEFAULT 0
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS reminder_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        reminders_enabled INTEGER NOT NULL DEFAULT 1,
        reminder_time TEXT NOT NULL DEFAULT '09:00',
        timezone TEXT NOT NULL DEFAULT 'UTC',
        updated_at TEXT NOT NULL
      )
      ''',
    ];
  }

  static List<String> createStatementsV2() {
    return <String>[
      '''
      CREATE TABLE IF NOT EXISTS card_bill_payments (
        id TEXT PRIMARY KEY,
        card_id TEXT NOT NULL,
        cycle_start TEXT NOT NULL,
        cycle_end TEXT NOT NULL,
        amount_paid REAL NOT NULL,
        paid_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS reminder_deliveries (
        id TEXT PRIMARY KEY,
        reminder_date TEXT NOT NULL,
        reminder_type TEXT NOT NULL,
        sent_at TEXT NOT NULL
      )
      ''',
      '''
      CREATE TABLE IF NOT EXISTS notification_events (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        read_at TEXT
      )
      ''',
      'CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(txn_date)',
      'CREATE INDEX IF NOT EXISTS idx_pending_ops_created ON pending_operations(created_at)',
      'CREATE INDEX IF NOT EXISTS idx_notifications_created ON notification_events(created_at DESC)',
    ];
  }

  static List<String> createStatementsV3() {
    return <String>[
      '''
      CREATE TABLE IF NOT EXISTS notification_ingestion_events (
        id TEXT PRIMARY KEY,
        source_key TEXT NOT NULL UNIQUE,
        package_name TEXT NOT NULL,
        title TEXT,
        body TEXT NOT NULL,
        amount REAL,
        card_last4 TEXT,
        transaction_id TEXT,
        created_at TEXT NOT NULL
      )
      ''',
      'CREATE INDEX IF NOT EXISTS idx_ingestion_created ON notification_ingestion_events(created_at DESC)',
    ];
  }
}
