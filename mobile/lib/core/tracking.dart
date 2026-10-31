import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import 'api.dart';
import 'config.dart';
import 'location.dart';
import 'store.dart';

class VehicleTracking {
  static const channel = MethodChannel('rotafy/tracking');
  static Future<String?> active() async {
    try {
      return await channel.invokeMethod<String>('status');
    } on MissingPluginException {
      return null;
    }
  }

  static Future<void> start(
    RotafyApi api,
    LocalStore store,
    Json snapshot, {
    bool takeover = false,
  }) async {
    final config = await api.request('GET', '/tracking/settings');
    if (config['enabled'] != true) {
      throw StateError('O administrador não habilitou o rastreamento.');
    }
    final position = await ArrivalLocationService().capture();
    if (position['status'] != 'captured') {
      throw StateError('Ative o GPS e permita a localização para rastrear.');
    }
    final device = await store.meta('device') ?? const Uuid().v4();
    await store.setMeta('device', device);
    // The manifest endpoint includes trip, allocation and leg identifiers.
    final endpoint = snapshot['endpoint'] as String;
    final match = RegExp(r'^/trips/([^/]+)/vehicles/([^/]+)/legs/([^/]+)')
        .firstMatch(endpoint);
    if (match == null) {
      throw StateError('Não foi possível identificar o deslocamento.');
    }
    final session = await api.request('POST', '/tracking/sessions', {
      'trip_id': match.group(1),
      'allocation_id': match.group(2),
      'leg_id': match.group(3),
      'device_id': device,
      'takeover': takeover,
    });
    try {
      final previous = await active();
      if (previous != null && previous != session['id']) {
        await api.request('DELETE', '/tracking/sessions/$previous');
      }
      final started = await channel.invokeMethod<bool>('start', {
        'session': session['id'],
        'base': AppConfig.apiUrl,
        'origin': AppConfig.origin,
        'cookie': api.cookies.entries
            .map((e) => '${e.key}=${e.value}')
            .join('; '),
        'csrf': api.cookies['rotafy_csrf'] ?? '',
      });
      if (started != true) {
        throw StateError(
          'O Android não confirmou o início do rastreamento. Tente assumir o rastreamento novamente.',
        );
      }
      await api.request(
        'POST',
        '/tracking/sessions/${session['id']}/positions',
        {
          'positions': [
            {
              'id': const Uuid().v4(),
              for (final entry in position.entries)
                if (entry.key != 'status') entry.key: entry.value,
            },
          ],
        },
      );
    } catch (_) {
      try {
        await stop();
      } finally {
        await api.request('DELETE', '/tracking/sessions/${session['id']}');
      }
      rethrow;
    }
  }

  static Future<void> stop() async {
    try {
      await channel.invokeMethod('stop');
    } on MissingPluginException {
      /* Test hosts have no native service. */
    }
  }
}
