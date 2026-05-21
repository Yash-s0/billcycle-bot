int readInt(Map<String, Object?> map, String key) {
  final Object? value = map[key];
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return int.parse(value.toString());
}

double readDouble(Map<String, Object?> map, String key) {
  final Object? value = map[key];
  if (value is double) {
    return value;
  }
  if (value is int) {
    return value.toDouble();
  }
  if (value is num) {
    return value.toDouble();
  }
  return double.parse(value.toString());
}

String readString(Map<String, Object?> map, String key) {
  final Object? value = map[key];
  if (value == null) {
    throw StateError('Missing key: $key');
  }
  return value.toString();
}
