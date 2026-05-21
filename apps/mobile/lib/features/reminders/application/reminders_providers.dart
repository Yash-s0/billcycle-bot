import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../notifications/domain/notification_event.dart';
import '../domain/reminder_settings.dart';

final reminderSettingsProvider = FutureProvider<ReminderSettings>((Ref ref) {
  return ref.watch(remindersRepositoryProvider).getSettings();
});

final notificationEventsProvider = StreamProvider<List<NotificationEvent>>((Ref ref) {
  return ref.watch(remindersRepositoryProvider).watchNotificationEvents();
});
