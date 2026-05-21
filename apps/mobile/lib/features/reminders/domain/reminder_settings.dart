class ReminderSettings {
  const ReminderSettings({
    required this.enabled,
    required this.reminderTime,
    required this.timezone,
  });

  final bool enabled;
  final String reminderTime;
  final String timezone;

  ReminderSettings copyWith({
    bool? enabled,
    String? reminderTime,
    String? timezone,
  }) {
    return ReminderSettings(
      enabled: enabled ?? this.enabled,
      reminderTime: reminderTime ?? this.reminderTime,
      timezone: timezone ?? this.timezone,
    );
  }
}
