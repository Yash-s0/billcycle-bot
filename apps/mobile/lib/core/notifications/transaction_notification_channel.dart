import 'dart:async';

import 'package:flutter/services.dart';

class TransactionNotificationChannel {
  static const MethodChannel _method = MethodChannel('billcycle/notification_control');
  static const EventChannel _events = EventChannel('billcycle/notification_events');

  static Future<bool> isListenerEnabled() async {
    final bool? value = await _method.invokeMethod<bool>('isNotificationListenerEnabled');
    return value ?? false;
  }

  static Future<void> openListenerSettings() {
    return _method.invokeMethod<void>('openNotificationListenerSettings');
  }

  static Stream<Map<String, dynamic>> notificationStream() {
    return _events.receiveBroadcastStream().map((dynamic event) {
      final Map<Object?, Object?> raw = (event as Map<Object?, Object?>?) ?? <Object?, Object?>{};
      return raw.map((Object? key, Object? value) => MapEntry(key.toString(), value));
    });
  }
}
