import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

import 'api.dart';
import 'config.dart';

class BiometricLogin {
  final LocalAuthentication auth;
  final FlutterSecureStorage vault;
  BiometricLogin({LocalAuthentication? auth, FlutterSecureStorage? vault})
    : auth = auth ?? LocalAuthentication(),
      vault =
          vault ??
          const FlutterSecureStorage(
            aOptions: AndroidOptions.biometric(
              storageNamespace: 'rotafy_biometric_login',
              enforceBiometrics: true,
              requireBiometricsPerOperation: true,
              biometricType: AndroidBiometricType.strongBiometricOnly,
              resetOnError: false,
              biometricPromptTitle: 'Entrar no Nexus Rotafy',
              biometricPromptSubtitle:
                  'Confirme sua biometria para acessar sua conta',
              biometricPromptNegativeButton: 'Usar senha',
            ),
          );

  String get key => 'login:${AppConfig.apiUrl}';

  Future<bool> available() async {
    if (!Platform.isAndroid) return false;
    try {
      return await auth.canCheckBiometrics &&
          (await auth.getAvailableBiometrics()).isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> save(Json credentials) async {
    if (!await available()) {
      throw StateError('Cadastre uma biometria nas configurações do celular.');
    }
    await vault.write(key: key, value: jsonEncode(credentials));
  }

  Future<Json> read() async {
    if (!await available()) {
      throw StateError('Biometria indisponível. Entre com sua senha.');
    }
    try {
      final value = await vault.read(key: key);
      if (value == null) {
        throw StateError('Ative a biometria entrando com sua senha.');
      }
      return Json.from(jsonDecode(value));
    } catch (_) {
      throw StateError(
        'Biometria cancelada ou indisponível. Tente novamente ou entre com sua senha.',
      );
    }
  }

  Future<void> clear() => vault.delete(key: key);
}
