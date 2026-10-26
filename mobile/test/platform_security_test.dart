import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('release blocks cleartext, backups and exported tracking service', () {
    final manifest = File('android/app/src/main/AndroidManifest.xml')
        .readAsStringSync();
    expect(manifest, contains('android:usesCleartextTraffic="false"'));
    expect(manifest, contains('android:allowBackup="false"'));
    expect(
      manifest,
      contains('android:name=".TrackingService" android:exported="false"'),
    );
  });

  test('native GPS queue does not write locations to disk', () {
    final service = File(
      'android/app/src/main/kotlin/br/com/nexusdataanalytics/nexus_rotafy/TrackingService.kt',
    ).readAsStringSync();
    expect(service, isNot(contains('putString(')));
    expect(service, isNot(contains('writeText(')));
    expect(service, contains('pendingPositions.remove(session)'));
    expect(service, contains('pendingPositions.clear()'));
  });
}
