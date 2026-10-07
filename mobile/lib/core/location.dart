import 'dart:async';

import 'package:geolocator/geolocator.dart';

import 'api.dart';

class ArrivalLocationService {
  final GeolocatorPlatform platform;
  ArrivalLocationService({GeolocatorPlatform? platform})
    : platform = platform ?? GeolocatorPlatform.instance;

  Future<Json> capture() async {
    Json unavailable(String reason) => {
      'status': 'unavailable',
      'reason': reason,
    };
    try {
      if (!await platform.isLocationServiceEnabled()) {
        return unavailable('service_disabled');
      }
      var permission = await platform.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await platform.requestPermission();
      }
      if (permission == LocationPermission.deniedForever) {
        return unavailable('permission_denied_forever');
      }
      if (permission != LocationPermission.always &&
          permission != LocationPermission.whileInUse) {
        return unavailable('permission_denied');
      }
      final position = await platform
          .getCurrentPosition(
            locationSettings: const LocationSettings(
              accuracy: LocationAccuracy.high,
              timeLimit: Duration(seconds: 15),
            ),
          )
          .timeout(const Duration(seconds: 16));
      final age = DateTime.now().toUtc().difference(position.timestamp.toUtc());
      if (age > const Duration(minutes: 2) ||
          age < const Duration(minutes: -1)) {
        return unavailable('stale_position');
      }
      if (!position.latitude.isFinite ||
          !position.longitude.isFinite ||
          !position.accuracy.isFinite ||
          position.accuracy < 0 ||
          position.latitude.abs() > 90 ||
          position.longitude.abs() > 180) {
        return unavailable('position_unavailable');
      }
      return {
        'status': 'captured',
        'latitude': position.latitude,
        'longitude': position.longitude,
        'accuracy_m': position.accuracy,
        'captured_at': position.timestamp.toUtc().toIso8601String(),
      };
    } on TimeoutException {
      return unavailable('timeout');
    } catch (_) {
      return unavailable('position_unavailable');
    }
  }
}
