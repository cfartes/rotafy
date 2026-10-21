import 'api.dart';

class AndroidUpdate {
  final String version;
  final int build;
  final String path;
  const AndroidUpdate(this.version, this.build, this.path);

  static Future<AndroidUpdate?> check(Gateway api, Json installed) async {
    final response = await api.request(
      'GET',
      '/public/mobile-version?package_id=${Uri.encodeQueryComponent(installed['package_id'] as String)}',
    );
    final value = response['android'];
    if (value is! Map ||
        value['package_id'] != installed['package_id'] ||
        value['build'] is! int ||
        value['build'] <= installed['build']) {
      return null;
    }
    final path = value['download_url'];
    final uri = path is String ? Uri.tryParse(path) : null;
    if (uri == null ||
        uri.hasAuthority ||
        uri.hasScheme ||
        uri.path != '/api/v1/public/mobile/download') {
      return null;
    }
    return AndroidUpdate(
      value['version'] as String,
      value['build'] as int,
      path as String,
    );
  }
}
