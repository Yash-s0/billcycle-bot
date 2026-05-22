import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/notifications/transaction_notification_channel.dart';
import '../../../core/sync/sync_models.dart';
import '../../../core/validation/validators.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/ui_primitives.dart';
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
          UiSectionCard(
            title: 'Reminder settings',
            child: AsyncValueView<ReminderSettings>(
              value: reminderSettings,
              data: (ReminderSettings settings) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.35),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: <Widget>[
                          const Expanded(
                            child: Text(
                              'Enable daily reminders',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                          ),
                          Switch(
                            value: settings.enabled,
                            onChanged: (bool value) async {
                              await ref.read(remindersRepositoryProvider).updateSettings(settings.copyWith(enabled: value));
                              ref.invalidate(reminderSettingsProvider);
                            },
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    UiStatusPill(label: 'Timezone: ${settings.timezone}'),
                    const SizedBox(height: 10),
                    TextFormField(
                      initialValue: settings.reminderTime,
                      decoration: const InputDecoration(
                        labelText: 'Reminder time',
                        helperText: '24-hour format, e.g. 09:00',
                      ),
                      onFieldSubmitted: (String value) async {
                        if (!Validators.isValidTime(value)) {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Invalid time format')));
                          return;
                        }
                        await ref.read(remindersRepositoryProvider).updateSettings(settings.copyWith(reminderTime: value));
                        ref.invalidate(reminderSettingsProvider);
                      },
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                      onPressed: () async {
                        await ref.read(remindersRepositoryProvider).generateDailyReminderEvents();
                      },
                      icon: const Icon(Icons.notifications_active_outlined),
                      label: const Text('Generate today reminder events'),
                    ),
                    ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          if (syncConfigured)
            UiSectionCard(
              title: 'Sync',
              child: AsyncValueView<SyncStatus>(
                value: syncStatus,
                data: (SyncStatus status) {
                  final sync = ref.read(syncRepositoryProvider);
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      UiKeyValueRow(label: 'Device', value: status.deviceId),
                      UiKeyValueRow(label: 'Pending operations', value: '${status.pendingCount}'),
                      UiKeyValueRow(label: 'Server cursor', value: status.serverCursor ?? '-'),
                      UiKeyValueRow(label: 'Last sync', value: status.lastSyncAt?.toLocal().toString() ?? '-'),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          FilledButton(
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
                          OutlinedButton(
                            onPressed: () async {
                              await sync.setSyncEnabled(!status.enabled);
                              ref.invalidate(syncStatusProvider);
                            },
                            child: Text(status.enabled ? 'Disable sync' : 'Enable sync'),
                          ),
                        ],
                      ),
                    ],
                  );
                },
              ),
            )
          else
            const UiSectionCard(
              title: 'Sync',
              child: Text('Local-only mode is active. Configure SYNC_BASE_URL to enable cloud sync.'),
            ),
          const SizedBox(height: 8),
          UiSectionCard(
            title: 'Transaction message capture',
            subtitle: 'Reads transaction notifications on Android and auto-adds matched card spends locally.',
            child: FutureBuilder<bool>(
              future: TransactionNotificationChannel.isListenerEnabled(),
              builder: (BuildContext context, AsyncSnapshot<bool> snapshot) {
                final bool enabled = snapshot.data ?? false;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    UiStatusPill(label: 'Notification access: ${enabled ? 'Enabled' : 'Disabled'}'),
                    const SizedBox(height: 10),
                    FilledButton.tonal(
                      onPressed: () async {
                        await TransactionNotificationChannel.openListenerSettings();
                      },
                      child: const Text('Open notification access settings'),
                    ),
                    const SizedBox(height: 8),
                    const Text('Tip: add card last 4 digits in card name or notes (e.g. HDFC Regalia 1234) for best auto-matching.'),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          const UiSectionCard(
            title: 'Privacy',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('• Full card numbers are never stored'),
                Text('• CVV, OTP, PIN and passwords are never collected'),
                Text('• App is local-first and works offline'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
