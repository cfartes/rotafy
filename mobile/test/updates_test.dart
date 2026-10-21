import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/updates.dart';

class FakeApi implements Gateway {
  final Json payload;
  FakeApi(this.payload);
  @override
  Future<dynamic> request(String method, String path, [Json? data]) async =>
      payload;
}

void main() {
  final installed = <String, dynamic>{'package_id': 'example.app', 'build': 12};
  Json release(
    int build, [
    String path = '/api/v1/public/mobile/download?build=13',
  ]) => {
    'android': {
      'package_id': 'example.app',
      'build': build,
      'version': '1.8.0',
      'download_url': path,
    },
  };
  test('shows only newer builds of the same application', () async {
    expect(await AndroidUpdate.check(FakeApi(release(12)), installed), isNull);
    expect(await AndroidUpdate.check(FakeApi(release(11)), installed), isNull);
    expect(
      (await AndroidUpdate.check(FakeApi(release(13)), installed))?.build,
      13,
    );
    expect(
      await AndroidUpdate.check(FakeApi({'android': null}), installed),
      isNull,
    );
    final other = release(13);
    other['android']['package_id'] = 'other.app';
    expect(await AndroidUpdate.check(FakeApi(other), installed), isNull);
  });
  test('rejects external update links', () async {
    expect(
      await AndroidUpdate.check(
        FakeApi(release(13, 'https://other.example/app.apk')),
        installed,
      ),
      isNull,
    );
    expect(
      await AndroidUpdate.check(
        FakeApi(release(13, '//other.example/app.apk')),
        installed,
      ),
      isNull,
    );
  });
}
