import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/biometrics.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';

import 'offline_test.dart' show fixture, FakeApi, now;

class FakeBiometrics extends BiometricLogin {
  Json? credentials;
  bool supported = true;
  bool cancelled = false;
  int reads = 0;
  @override
  Future<bool> available() async => supported;
  @override
  Future<void> save(Json value) async {
    if (!supported || cancelled) throw StateError('Biometria indisponível');
    credentials = Json.from(value);
  }

  @override
  Future<Json> read() async {
    reads++;
    if (cancelled || credentials == null) {
      throw StateError('Biometria cancelada');
    }
    return Json.from(credentials!);
  }

  @override
  Future<void> clear() async {
    credentials = null;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  late LocalStore store;
  late FakeBiometrics biometrics;
  late OperationController controller;
  int requests = 0;
  ApiFailure? failure;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    final db = await databaseFactoryFfi.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: LocalStore.createSchema,
      ),
    );
    store = LocalStore(db, SecretKey(List.filled(32, 7)));
    biometrics = FakeBiometrics();
    requests = 0;
    failure = null;
    controller = OperationController(
      FakeApi((method, path, body) async {
        requests++;
        if (failure != null) throw failure!;
        return fixture()['operator'];
      }),
      store,
      biometrics: biometrics,
    );
  });
  tearDown(() async {
    controller.dispose();
    await store.db.close();
  });

  Future<void> enroll() async {
    expect(
      await controller.login(
        'empresa',
        'driver@example.com',
        'test-password',
        enableBiometrics: true,
      ),
      true,
    );
  }

  test(
    'opt in saves access only after valid password login and locks restart',
    () async {
      await enroll();
      expect(biometrics.credentials?['owner'], store.owner(controller.user!));
      expect(await store.meta('password'), isNull);
      await controller.initialize();
      expect(controller.user, isNull);
      expect(controller.biometricEnabled, true);
      expect(biometrics.reads, 0);
      expect(await controller.loginWithBiometrics(), true);
      expect(biometrics.reads, 1);
      expect(controller.user?['role'], 'driver');
    },
  );

  test('failed password login never enrolls biometric access', () async {
    failure = ApiFailure(401, 'Acesso inválido');
    expect(
      await controller.login(
        'empresa',
        'driver@example.com',
        'wrong',
        enableBiometrics: true,
      ),
      false,
    );
    expect(biometrics.credentials, isNull);
    expect(controller.user, isNull);
  });

  test(
    'cancelled biometric prompt never contacts backend or unlocks app',
    () async {
      await enroll();
      await controller.initialize();
      biometrics.cancelled = true;
      final before = requests;
      expect(await controller.loginWithBiometrics(), false);
      expect(requests, before);
      expect(controller.user, isNull);
    },
  );

  test('unsupported enrollment keeps normal login working', () async {
    biometrics.supported = false;
    await enroll();
    expect(controller.user, isNotNull);
    expect(controller.biometricEnabled, false);
    expect(controller.biometricNotice, contains('não foi ativada'));
  });

  test(
    'password change clears biometric access and preserves pending queue',
    () async {
      await enroll();
      final id = await store.prepare('/trip/vehicle/leg', fixture());
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      await controller.initialize();
      failure = ApiFailure(401, 'Senha alterada');
      expect(await controller.loginWithBiometrics(), false);
      expect(controller.user, isNull);
      expect(controller.biometricEnabled, false);
      expect(biometrics.credentials, isNull);
      expect(await store.pendingCount(), 1);
    },
  );

  test(
    'biometric unlock offline preserves the original operator and queue',
    () async {
      await enroll();
      final id = await store.prepare('/trip/vehicle/leg', fixture());
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      await controller.initialize();
      failure = ApiFailure(0, 'Offline');
      expect(await controller.loginWithBiometrics(), true);
      expect(controller.user?['id'], fixture()['operator']['id']);
      expect(await store.pendingCount(), 1);
      expect(controller.biometricNotice, contains('Sem conexão'));
    },
  );

  test('biometric access cannot switch tenant or operator', () async {
    await enroll();
    await controller.initialize();
    biometrics.credentials!['owner'] = 'other:user';
    final before = requests;
    expect(await controller.loginWithBiometrics(), false);
    expect(requests, before);
    expect(controller.user, isNull);
  });

  test(
    'manual login remains available and disabling clears saved access',
    () async {
      await enroll();
      expect(await controller.disableBiometrics(), true);
      expect(controller.biometricEnabled, false);
      expect(biometrics.credentials, isNull);
      expect(controller.user, isNotNull);
      await controller.initialize();
      expect(controller.user, isNotNull);
    },
  );

  test('logout clears biometric access as well as the session', () async {
    await enroll();
    expect(await controller.logout(), true);
    expect(controller.user, isNull);
    expect(biometrics.credentials, isNull);
    expect(await store.meta('biometric-owner'), isNull);
  });
}
