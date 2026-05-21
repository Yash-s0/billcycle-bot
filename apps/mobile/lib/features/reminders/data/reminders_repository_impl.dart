import 'dart:convert';

import 'package:uuid/uuid.dart';

import '../../../core/contracts/repositories.dart';
import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/db/table_names.dart';
import '../../../core/utils/billing_cycle.dart';
import '../../notifications/domain/notification_event.dart';
import '../domain/reminder_settings.dart';

class RemindersRepositoryImpl implements RemindersRepository {
  RemindersRepositoryImpl(this._database);

  final AppDatabase _database;
  final Uuid _uuid = const Uuid();

  @override
  Future<ReminderSettings> getSettings() async {
    final List<Map<String, Object?>> rows = await _database.query(
      'SELECT reminders_enabled, reminder_time, timezone FROM reminder_settings WHERE id = 1',
    );

    if (rows.isEmpty) {
      return const ReminderSettings(
        enabled: true,
        reminderTime: '09:00',
        timezone: 'Asia/Kolkata',
      );
    }

    final Map<String, Object?> row = rows.first;
    return ReminderSettings(
      enabled: readInt(row, 'reminders_enabled') == 1,
      reminderTime: readString(row, 'reminder_time'),
      timezone: readString(row, 'timezone'),
    );
  }

  @override
  Future<void> updateSettings(ReminderSettings settings) async {
    await _database.executeUpdate(
      '''
      UPDATE reminder_settings
      SET reminders_enabled = ?, reminder_time = ?, timezone = ?, updated_at = ?
      WHERE id = 1
      ''',
      params: <Object?>[
        settings.enabled ? 1 : 0,
        settings.reminderTime,
        settings.timezone,
        DateTime.now().toUtc().toIso8601String(),
      ],
      table: TableNames.reminderSettings,
    );
  }

  @override
  Future<void> generateDailyReminderEvents({DateTime? now}) async {
    final DateTime current = now?.toUtc() ?? DateTime.now().toUtc();
    final String reminderDate = asIsoDate(current);

    final List<Map<String, Object?>> existing = await _database.query(
      '''
      SELECT id
      FROM reminder_deliveries
      WHERE reminder_date = ? AND reminder_type = 'daily'
      LIMIT 1
      ''',
      params: <Object?>[reminderDate],
    );
    if (existing.isNotEmpty) {
      return;
    }

    final List<Map<String, Object?>> cards = await _database.query('SELECT * FROM cards');
    final List<String> dueIn3 = <String>[];
    final List<String> dueTomorrow = <String>[];
    final List<String> dueToday = <String>[];

    for (final Map<String, Object?> card in cards) {
      final DateTime dueDate = getNextDueDate(
        dueDay: readInt(card, 'due_day'),
        today: current,
      );
      final int diff = dueDate.difference(DateTime.utc(current.year, current.month, current.day)).inDays;
      final String label = '${readString(card, 'bank_name')}/${readString(card, 'card_name')}';
      if (diff == 3) {
        dueIn3.add('$label (${asIsoDate(dueDate)})');
      } else if (diff == 1) {
        dueTomorrow.add('$label (${asIsoDate(dueDate)})');
      } else if (diff == 0) {
        dueToday.add('$label (${asIsoDate(dueDate)})');
      }
    }

    final List<Map<String, Object?>> pending = await _database.query(
      '''
      SELECT p.name AS person_name, SUM(t.final_amount - t.cashback_amount) AS pending_amount
      FROM transactions t
      JOIN people p ON p.id = t.person_id
      WHERE t.is_for_someone_else = 1
        AND date(t.txn_date) <= date(?, '-7 day')
      GROUP BY p.name
      HAVING pending_amount > 0
      ORDER BY pending_amount DESC
      ''',
      params: <Object?>[reminderDate],
    );

    if (dueIn3.isEmpty && dueTomorrow.isEmpty && dueToday.isEmpty && pending.isEmpty) {
      await _database.executeInsert(
        '''
        INSERT INTO reminder_deliveries (id, reminder_date, reminder_type, sent_at)
        VALUES (?, ?, 'daily', ?)
        ''',
        params: <Object?>[
          _uuid.v4(),
          reminderDate,
          current.toIso8601String(),
        ],
        table: TableNames.reminderDeliveries,
      );
      return;
    }

    final List<String> bodyLines = <String>['Daily reminder'];
    if (dueIn3.isNotEmpty) {
      bodyLines.add('Due in 3 days: ${dueIn3.join(', ')}');
    }
    if (dueTomorrow.isNotEmpty) {
      bodyLines.add('Due tomorrow: ${dueTomorrow.join(', ')}');
    }
    if (dueToday.isNotEmpty) {
      bodyLines.add('Due today: ${dueToday.join(', ')}');
    }
    if (pending.isNotEmpty) {
      final String summary = pending
          .map((Map<String, Object?> row) => '${readString(row, 'person_name')}: ₹${readDouble(row, 'pending_amount').toStringAsFixed(2)}')
          .join(', ');
      bodyLines.add('Pending reimbursements > 7d: $summary');
    }

    await _database.transaction(() async {
      final NotificationEvent event = NotificationEvent(
        id: _uuid.v4(),
        type: 'daily-reminder',
        title: 'BillCycle reminder',
        body: bodyLines.join('\n'),
        payload: jsonEncode(
          <String, Object?>{
            'date': reminderDate,
            'dueIn3': dueIn3,
            'dueTomorrow': dueTomorrow,
            'dueToday': dueToday,
          },
        ),
        createdAt: current,
      );

      await _database.executeInsert(
        '''
        INSERT INTO notification_events (id, type, title, body, payload, created_at, read_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        ''',
        params: <Object?>[
          event.id,
          event.type,
          event.title,
          event.body,
          event.payload,
          event.createdAt.toIso8601String(),
        ],
      );

      await _database.executeInsert(
        '''
        INSERT INTO reminder_deliveries (id, reminder_date, reminder_type, sent_at)
        VALUES (?, ?, 'daily', ?)
        ''',
        params: <Object?>[
          _uuid.v4(),
          reminderDate,
          current.toIso8601String(),
        ],
      );

      _database.notifyTables(
        <String>{
          TableNames.notificationEvents,
          TableNames.reminderDeliveries,
        },
      );
    });
  }

  @override
  Stream<List<NotificationEvent>> watchNotificationEvents() {
    return _database.watchTableQuery(TableNames.notificationEvents, () async {
      return _database.query(
        'SELECT * FROM notification_events ORDER BY created_at DESC',
      );
    }).map(
      (List<Map<String, Object?>> rows) => rows
          .map((Map<String, Object?> row) => NotificationEvent.fromMap(row))
          .toList(growable: false),
    );
  }

  @override
  Future<void> markNotificationRead(String id) async {
    await _database.executeUpdate(
      'UPDATE notification_events SET read_at = ? WHERE id = ?',
      params: <Object?>[
        DateTime.now().toUtc().toIso8601String(),
        id,
      ],
      table: TableNames.notificationEvents,
    );
  }
}
