import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/notifications/transaction_notification_channel.dart';
import '../../../core/sync/sync_models.dart';
import '../../../core/validation/validators.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../reminders/application/reminders_providers.dart';
import '../../reminders/domain/reminder_settings.dart';
import '../application/settings_providers.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool syncConfigured = ref.watch(syncBaseUrlProvider).trim().isNotEmpty;
    final AsyncValue<ReminderSettings> reminderSettings = ref.watch(reminderSettingsProvider);
    final AsyncValue<SyncStatus> syncStatus = ref.watch(syncStatusProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: AsyncValueView<ReminderSettings>(
                value: reminderSettings,
                data: (ReminderSettings settings) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text('Reminder settings', style: Theme.of(context).textTheme.titleMedium),
                      SwitchListTile(
                        value: settings.enabled,
                        onChanged: (bool value) async {
                          await ref.read(remindersRepositoryProvider).updateSettings(
                                settings.copyWith(enabled: value),
                              );
                          ref.invalidate(reminderSettingsProvider);
                        },
                        title: const Text('Enable daily reminders'),
                      ),
                      const SizedBox(height: 8),
                      Text('Timezone: ${settings.timezone}'),
                      const SizedBox(height: 8),
                      TextFormField(
                        initialValue: settings.reminderTime,
                        decoration: const InputDecoration(labelText: 'Reminder time (HH:MM)'),
                        onFieldSubmitted: (String value) async {
                          if (!Validators.isValidTime(value)) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Invalid time format')),
                            );
                            return;
                          }
                          await ref.read(remindersRepositoryProvider).updateSettings(
                                settings.copyWith(reminderTime: value),
                              );
                          ref.invalidate(reminderSettingsProvider);
                        },
                      ),
                      const SizedBox(height: 10),
                      FilledButton.tonal(
                        onPressed: () async {
                          await ref.read(remindersRepositoryProvider).generateDailyReminderEvents();
                        },
                        child: const Text('Generate today reminder events'),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (syncConfigured)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: AsyncValueView<SyncStatus>(
                  value: syncStatus,
                  data: (SyncStatus status) {
                    final sync = ref.read(syncRepositoryProvider);
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text('Sync', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Text('Device: ${status.deviceId}'),
                        Text('Pending operations: ${status.pendingCount}'),
                        Text('Server cursor: ${status.serverCursor ?? '-'}'),
                        Text('Last sync: ${status.lastSyncAt?.toLocal().toString() ?? '-'}'),
                        const SizedBox(height: 8),
                        Row(
                          children: <Widget>[
                            Expanded(
                              child: FilledButton(
                                onPressed: () async {
                                  final SyncRunResult result = await sync.runSync(force: true);
                                  if (!context.mounted) {
                                    return;
                                  }
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(
                                        result.success
                                            ? 'Sync complete: pushed ${result.pushedCount}, pulled ${result.pulledCount}'
                                            : 'Sync failed: ${result.error}',
                                      ),
                                    ),
                                  );
                                  ref.invalidate(syncStatusProvider);
                                },
                                child: const Text('Run sync now'),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: OutlinedButton(
                                onPressed: () async {
                                  await sync.setSyncEnabled(!status.enabled);
                                  ref.invalidate(syncStatusProvider);
                                },
                                child: Text(status.enabled ? 'Disable sync' : 'Enable sync'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    );
                  },
                ),
              ),
            )
          else
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text('Sync'),
                    SizedBox(height: 8),
                    Text(
                      'Local-only mode is active. Configure SYNC_BASE_URL to enable cloud sync.',
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('Transaction message capture', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  const Text(
                    'Reads transaction notifications on Android and auto-adds matched card spends locally.',
                  ),
                  const SizedBox(height: 12),
                  FutureBuilder<bool>(
                    future: TransactionNotificationChannel.isListenerEnabled(),
                    builder: (BuildContext context, AsyncSnapshot<bool> snapshot) {
                      final bool enabled = snapshot.data ?? false;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text('Notification access: ${enabled ? 'Enabled' : 'Disabled'}'),
                          const SizedBox(height: 8),
                          FilledButton.tonal(
                            onPressed: () async {
                              await TransactionNotificationChannel.openListenerSettings();
                            },
                            child: const Text('Open notification access settings'),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Tip: add card last 4 digits in card name or notes (e.g. HDFC Regalia 1234) for best auto-matching.',
                          ),
                        ],
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('Privacy'),
                  SizedBox(height: 8),
                  Text('• Full card numbers are never stored'),
                  Text('• CVV, OTP, PIN and passwords are never collected'),
                  Text('• App is local-first and works offline'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
