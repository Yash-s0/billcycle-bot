import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/ui_primitives.dart';
import '../../reminders/application/reminders_providers.dart';
import '../domain/notification_event.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<NotificationEvent>> events = ref.watch(notificationEventsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: AsyncValueView<List<NotificationEvent>>(
        value: events,
        onRetry: () => ref.invalidate(notificationEventsProvider),
        isEmpty: (List<NotificationEvent> value) => value.isEmpty,
        emptyBuilder: (_) => const EmptyState(
          title: 'No notifications yet',
          subtitle: 'Reminder and sync events will appear here.',
        ),
        data: (List<NotificationEvent> value) {
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: value.length,
            itemBuilder: (BuildContext context, int index) {
              final NotificationEvent item = value[index];
              return Card(
                child: ListTile(
                  title: Text(
                    item.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          item.body,
                          maxLines: 4,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          formatDate(item.createdAt),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  isThreeLine: true,
                  trailing: item.isRead
                      ? const UiStatusPill(label: 'Read')
                      : const UiStatusPill(label: 'New'),
                  onTap: () async {
                    if (!item.isRead) {
                      await ref.read(remindersRepositoryProvider).markNotificationRead(item.id);
                    }
                  },
                ),
              );
            },
          );
        },
      ),
    );
  }
}
