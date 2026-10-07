import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:nexus_rotafy/core/location.dart';

class FakeLocation extends GeolocatorPlatform {
  bool enabled = true;
  LocationPermission permission = LocationPermission.whileInUse;
  LocationPermission requested = LocationPermission.denied;
  Object? error;
  DateTime timestamp = DateTime.now().toUtc();
  int captures = 0;
  LocationSettings? settings;
  @override
  Future<bool> isLocationServiceEnabled() async => enabled;
  @override
  Future<LocationPermission> checkPermission() async => permission;
  @override
  Future<LocationPermission> requestPermission() async => requested;
  @override
  Future<Position> getCurrentPosition({
    LocationSettings? locationSettings,
  }) async {
    captures++;
    settings = locationSettings;
    if (error != null) throw error!;
    return Position(
      latitude: -9.0123,
      longitude: -35.2222,
      timestamp: timestamp,
      accuracy: 12.5,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
  }
}

void main() {
  test(
    'fresh position includes coordinates, precision and capture timestamp',
    () async {
      final platform = FakeLocation();
      final data = await ArrivalLocationService(platform: platform).capture();
      expect(data['status'], 'captured');
      expect(data['latitude'], -9.0123);
      expect(data['longitude'], -35.2222);
      expect(data['accuracy_m'], 12.5);
      expect(data['captured_at'], platform.timestamp.toIso8601String());
      expect(platform.settings?.timeLimit, const Duration(seconds: 15));
    },
  );

  for (final reason in [
    'permission_denied',
    'permission_denied_forever',
    'service_disabled',
  ]) {
    test('$reason does not attempt position capture', () async {
      final platform = FakeLocation();
      if (reason == 'service_disabled') platform.enabled = false;
      if (reason == 'permission_denied') {
        platform.permission = LocationPermission.denied;
      }
      if (reason == 'permission_denied_forever') {
        platform.permission = LocationPermission.deniedForever;
      }
      final data = await ArrivalLocationService(platform: platform).capture();
      expect(data, {'status': 'unavailable', 'reason': reason});
      expect(platform.captures, 0);
    });
  }

  test('permission granted after prompt allows current fix', () async {
    final platform = FakeLocation()
      ..permission = LocationPermission.denied
      ..requested = LocationPermission.whileInUse;
    expect(
      (await ArrivalLocationService(platform: platform).capture())['status'],
      'captured',
    );
  });

  test(
    'timeout and unexpected failure allow arrival without coordinates',
    () async {
      final platform = FakeLocation()..error = TimeoutException('GPS');
      expect(
        (await ArrivalLocationService(platform: platform).capture())['reason'],
        'timeout',
      );
      platform.error = StateError('No position');
      expect(
        (await ArrivalLocationService(platform: platform).capture())['reason'],
        'position_unavailable',
      );
    },
  );

  test('old location is not sent as current arrival position', () async {
    final platform = FakeLocation()
      ..timestamp = DateTime.now().toUtc().subtract(const Duration(minutes: 3));
    final data = await ArrivalLocationService(platform: platform).capture();
    expect(data, {'status': 'unavailable', 'reason': 'stale_position'});
  });
}
