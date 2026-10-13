import 'package:flutter/foundation.dart';

class AppConfig {
  static const name = String.fromEnvironment(
    'APP_NAME',
    defaultValue: 'Nexus Rotafy',
  );
  static const company = String.fromEnvironment('COMPANY_SLUG');
  static const apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'https://rotafy.nexusdataanalytics.tech/api/v1',
  );
  static const origin = String.fromEnvironment(
    'WEB_ORIGIN',
    defaultValue: 'https://rotafy.nexusdataanalytics.tech',
  );
  static void validate() {
    final url = Uri.parse(apiUrl);
    if (!url.hasAuthority || (!kDebugMode && url.scheme != 'https')) {
      throw StateError('A configuração de produção exige API HTTPS.');
    }
  }
}
