import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'config.dart';

typedef Json = Map<String, dynamic>;

class ApiFailure implements Exception {
  final int status;
  final String message;
  final String? code;
  ApiFailure(this.status, this.message, [this.code]);
  @override
  String toString() => message;
}

abstract class Gateway {
  Future<dynamic> request(String method, String path, [Json? data]);
}

class RotafyApi implements Gateway {
  final Dio dio;
  final FlutterSecureStorage vault;
  Map<String, String> cookies = {};
  RotafyApi(this.vault)
    : dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.apiUrl,
          connectTimeout: const Duration(seconds: 12),
          receiveTimeout: const Duration(seconds: 20),
          followRedirects: false,
          validateStatus: (_) => true,
        ),
      );

  Future<void> restore() async {
    final raw = await vault.read(key: 'session:${AppConfig.apiUrl}');
    if (raw != null) cookies = Map<String, String>.from(jsonDecode(raw));
  }

  Future<void> saveSession() => vault.write(
    key: 'session:${AppConfig.apiUrl}',
    value: jsonEncode(cookies),
  );
  Future<void> clearSession() async {
    cookies.clear();
    await vault.delete(key: 'session:${AppConfig.apiUrl}');
  }

  @override
  Future<dynamic> request(String method, String path, [Json? data]) async {
    // Only fixed relative API paths; session credentials never follow redirects.
    if (!path.startsWith('/') ||
        path.startsWith('//') ||
        path.contains('://')) {
      throw ArgumentError('Caminho de API inválido.');
    }
    Response response;
    try {
      response = await dio.request(
        '${AppConfig.apiUrl}$path',
        data: data,
        options: Options(
          method: method,
          headers: {
            'Origin': AppConfig.origin,
            if (cookies.isNotEmpty)
              'Cookie': cookies.entries
                  .map((e) => '${e.key}=${e.value}')
                  .join('; '),
            if (cookies['rotafy_csrf'] != null)
              'X-CSRF-Token': cookies['rotafy_csrf'],
          },
        ),
      );
    } on DioException {
      throw ApiFailure(
        0,
        'Sem conexão. Seus registros locais estão preservados.',
      );
    }
    for (final value in response.headers['set-cookie'] ?? <String>[]) {
      final cookie = Cookie.fromSetCookieValue(value);
      if (cookie.name == 'rotafy_session' || cookie.name == 'rotafy_csrf') {
        if (cookie.value.isEmpty) {
          cookies.remove(cookie.name);
        } else {
          cookies[cookie.name] = cookie.value;
        }
      }
    }
    if ((response.statusCode ?? 500) >= 400) {
      final body = response.data;
      final detail = body is Map ? body['detail'] : null;
      throw ApiFailure(
        response.statusCode!,
        detail is String ? detail : 'Confira os dados e tente novamente.',
        response.headers.value('x-rotafy-error'),
      );
    }
    return response.data;
  }
}
