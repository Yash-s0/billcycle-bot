import 'dart:convert';

import 'package:http/http.dart' as http;

import 'sync_models.dart';

class SyncClient {
  SyncClient({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  bool get isEnabled => baseUrl.trim().isNotEmpty;

  Future<PushResult> push({
    required String deviceId,
    required List<PendingOperation> operations,
    required String? lastKnownCursor,
  }) async {
    final Uri uri = Uri.parse('$baseUrl/sync/push');
    final Map<String, Object?> payload = <String, Object?>{
      'deviceId': deviceId,
      'lastKnownCursor': lastKnownCursor,
      'operations': operations
          .map(
            (PendingOperation op) => <String, Object?>{
              'id': op.id,
              'entityType': op.entityType,
              'entityId': op.entityId,
              'operationType': op.operationType,
              'payload': op.payload,
              'createdAt': op.createdAt.toUtc().toIso8601String(),
              'attempts': op.attempts,
            },
          )
          .toList(growable: false),
    };

    final http.Response response = await _client.post(
      uri,
      headers: const <String, String>{'content-type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode != 200) {
      throw Exception('Push failed: ${response.statusCode} ${response.body}');
    }

    final Map<String, dynamic> json = jsonDecode(response.body) as Map<String, dynamic>;
    return PushResult(
      ackedOperationIds: (json['ackedOperationIds'] as List<dynamic>? ?? <dynamic>[])
          .cast<String>(),
      serverCursor: json['serverCursor'] as String?,
      conflicts: (json['conflicts'] as List<dynamic>? ?? <dynamic>[])
          .map((dynamic conflict) => Map<String, Object?>.from(conflict as Map<String, dynamic>))
          .toList(growable: false),
    );
  }

  Future<PullResult> pull({
    required String deviceId,
    required String? cursor,
  }) async {
    final Uri uri = Uri.parse('$baseUrl/sync/pull');
    final http.Response response = await _client.post(
      uri,
      headers: const <String, String>{'content-type': 'application/json'},
      body: jsonEncode(
        <String, Object?>{
          'deviceId': deviceId,
          'cursor': cursor,
        },
      ),
    );

    if (response.statusCode != 200) {
      throw Exception('Pull failed: ${response.statusCode} ${response.body}');
    }

    final Map<String, dynamic> json = jsonDecode(response.body) as Map<String, dynamic>;
    return PullResult(
      changes: (json['changes'] as List<dynamic>? ?? <dynamic>[])
          .map((dynamic item) => Map<String, Object?>.from(item as Map<String, dynamic>))
          .toList(growable: false),
      serverCursor: json['serverCursor'] as String?,
    );
  }
}
