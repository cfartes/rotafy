import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'store.dart';
import 'location.dart';
import 'biometrics.dart';
import 'config.dart';

class OperationController extends ChangeNotifier {
  final RotafyApi api;
  final LocalStore store;
  final ArrivalLocationService location;
  final BiometricLogin biometrics;
  bool biometricEnabled = false;
  String? biometricNotice;
  Json? user;
  List<Json> prepared = [];
  List<Json> records = [];
  bool busy = false;
  String? error;
  OperationController(
    this.api,
    this.store, {
    ArrivalLocationService? location,
    BiometricLogin? biometrics,
  }) : location = location ?? ArrivalLocationService(),
       biometrics = biometrics ?? BiometricLogin();

  Future<void> initialize() async {
    await api.restore();
    final saved = await store.meta('user');
    biometricEnabled =
        saved != null &&
        await store.meta('biometric-owner') == store.owner(Json.from(saved));
    user = biometricEnabled ? null : saved;
    await reload();
  }

  Future<void> reload() async {
    records = await store.queue();
    final snapshots = await store.snapshots();
    closedTrips.addAll(
      snapshots
          .where((s) => s['data']['trip']['status'] == 'completed')
          .map((s) => s['data']['trip']['id'] as String),
    );
    prepared = snapshots
        .where(
          (s) =>
              !closedSnapshot(s) ||
              records.any((r) => r['manifest'] == s['id']),
        )
        .toList();
    notifyListeners();
  }

  bool closedSnapshot(Json snapshot) =>
      ['completed', 'cancelled'].contains(snapshot['data']['trip']['status']) ||
      snapshot['data']['journey']?['status'] == 'completed';

  final Set<String> closedTrips = {};

  Future<bool> run(Future<void> Function() work) async {
    if (busy) return false;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await work();
      await reload();
      return true;
    } catch (e) {
      error = e is ApiFailure
          ? e.message
          : e.toString().replaceFirst('Bad state: ', '');
      // Earlier commands may already have been acknowledged before a failure.
      // Keep the screen consistent with the durable queue even when offline.
      try {
        await reload();
      } catch (_) {
        // Preserve the original failure if local storage is unavailable too.
      }
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<bool> login(
    String company,
    String email,
    String password, {
    bool enableBiometrics = false,
  }) => run(
    () => passwordLogin(
      company,
      email,
      password,
      enableBiometrics: enableBiometrics,
    ),
  );

  Future<void> passwordLogin(
    String company,
    String email,
    String password, {
    bool enableBiometrics = false,
    String? expectedOwner,
  }) async {
    final oldCookies = Map<String, String>.from(api.cookies);
    final oldBiometricOwner = await store.meta('biometric-owner');
    biometricNotice = null;
    try {
      final result = Json.from(
        await api.request('POST', '/auth/login', {
          'company': company,
          'email': email.trim(),
          'password': password,
        }),
      );
      if (!['guide', 'driver'].contains(result['role'])) {
        throw StateError('Este aplicativo é destinado a motoristas e guias.');
      }
      if (expectedOwner != null && store.owner(result) != expectedOwner) {
        throw StateError(
          'O acesso salvo não corresponde a esta conta. Entre com sua senha.',
        );
      }
      await store.activate(result);
      closedTrips.clear();
      await api.saveSession();
      if (expectedOwner == null) {
        if (enableBiometrics) {
          try {
            await biometrics.save({
              'company': company,
              'email': email.trim(),
              'password': password,
              'owner': store.owner(result),
            });
            await store.setMeta('biometric-owner', store.owner(result));
            biometricEnabled = true;
          } catch (_) {
            await store.setMeta('biometric-owner', null);
            biometricEnabled = false;
            biometricNotice = 'Login realizado. A biometria não foi ativada; verifique se há uma biometria forte cadastrada no celular e tente novamente no próximo login.';
          }
        } else {
          if (oldBiometricOwner != null) await biometrics.clear();
          await store.setMeta('biometric-owner', null);
          biometricEnabled = false;
        }
      }
      user = result;
    } catch (_) {
      // Keep the original operator session if another identity has queued work.
      if (api.cookies['rotafy_session'] != oldCookies['rotafy_session']) {
        try {
          await api.request('POST', '/auth/logout', {});
        } catch (_) {}
      }
      api.cookies = oldCookies;
      rethrow;
    }
  }

  Future<bool> loginWithBiometrics() => run(() async {
    if (!biometricEnabled) {
      throw StateError('Ative a biometria entrando com sua senha.');
    }
    final credentials = await biometrics.read();
    final owner = await store.meta('biometric-owner');
    if (owner == null ||
        credentials['owner'] != owner ||
        (AppConfig.company.isNotEmpty &&
            credentials['company'] != AppConfig.company)) {
      throw StateError(
        'O acesso biométrico pertence a outra conta. Entre com sua senha.',
      );
    }
    try {
      await passwordLogin(
        credentials['company'],
        credentials['email'],
        credentials['password'],
        expectedOwner: owner,
      );
    } on ApiFailure catch (e) {
      if (e.status == 0) {
        final saved = await store.meta('user');
        if (saved == null ||
            store.owner(Json.from(saved)) != owner ||
            !['driver', 'guide'].contains(saved['role'])) {
          rethrow;
        }
        user = Json.from(saved);
        biometricNotice = 'Sem conexão. Acesso aos dados locais liberado; sincronize quando houver internet.';
      } else {
        if (e.status == 401 || e.status == 403) {
          await disableBiometricsWork();
        }
        rethrow;
      }
    }
  });

  Future<void> disableBiometricsWork() async {
    await biometrics.clear();
    await store.setMeta('biometric-owner', null);
    biometricEnabled = false;
    biometricNotice = null;
  }

  Future<bool> disableBiometrics() => run(disableBiometricsWork);
  Future<bool> logout() => run(() async {
    if (await store.pendingCount() > 0) {
      throw StateError('Sincronize ou revise os registros antes de sair.');
    }
    try {
      await api.request('POST', '/auth/logout', {});
    } on ApiFailure catch (e) {
      if (e.status != 401) rethrow;
    }
    if (biometricEnabled) await biometrics.clear();
    await store.clear();
    biometricEnabled = false;
    biometricNotice = null;
    closedTrips.clear();
    await api.clearSession();
    user = null;
  });

  Future<List<Json>> trips() async {
    final result = await api.request('GET', '/trips');
    for (final trip in result as List) {
      if (trip['status'] == 'completed') {
        closedTrips.add(trip['id']);
        await store.closeTrip(trip['id']);
      }
    }
    await reload();
    return result
        .map((t) => Json.from(t))
        .where((t) => ['scheduled', 'in_progress'].contains(t['status']))
        .toList();
  }

  Future<Json> trip(String id) async =>
      Json.from(await api.request('GET', '/trips/$id'));
  Future<bool> prepare(Json trip, Json vehicle, Json leg) => run(() async {
    final endpoint =
        '/trips/${trip['id']}/vehicles/${vehicle['id']}/legs/${leg['id']}';
    final data = Json.from(
      await api.request('GET', '$endpoint/offline-manifest'),
    );
    final route = await api.request(
      'GET',
      '/trips/${trip['id']}/vehicles/${vehicle['id']}/route',
    );
    data['route'] = route;
    await store.prepare(endpoint, data);
  });
  Future<bool> enqueue(
    String manifest,
    String passenger,
    String action, {
    String? token,
  }) => run(() => store.enqueue(manifest, passenger, action, token: token));
  Future<bool> disembarkAll(String manifest) => run(() async {
    await store.disembarkAll(manifest);
  });

  Future<bool> changeJourney(String manifest, String status) => run(() async {
    final snapshot = await store.snapshot(manifest);
    if ((await store.queue(manifest)).isNotEmpty) {
      throw StateError(
        'Sincronize ou revise os registros deste trecho antes de iniciar ou fechar.',
      );
    }
    final current = Json.from(await api.request('GET', '/auth/me'));
    if (user == null || store.owner(current) != store.owner(user!)) {
      throw StateError('Entre com o usuário que preparou este trecho.');
    }
    final response = Json.from(
      await api.request('PATCH', '${snapshot['endpoint']}/journey', {
        'status': status,
        if (status == 'completed') 'arrival_location': await location.capture(),
      }),
    );
    await store.prepare(snapshot['endpoint'], {
      ...Json.from(snapshot['data']),
      ...response,
    });
    if (response['trip']['status'] == 'completed') {
      closedTrips.add(response['trip']['id']);
      await store.closeTrip(response['trip']['id']);
    }
  });
  Future<bool> synchronize() => run(() async {
    final current = Json.from(await api.request('GET', '/auth/me'));
    if (user == null || store.owner(current) != store.owner(user!)) {
      throw StateError('Entre com o usuário que preparou os manifestos.');
    }
    final blocked = <String>{};
    for (final record in await store.queue()) {
      final scope =
          '${record['manifest']}:${record['payload']['passenger_id']}';
      if (record['status'] != 'pending') {
        blocked.add(scope);
        continue;
      }
      if (blocked.contains(scope)) continue;
      final snapshot = await store.snapshot(record['manifest']);
      try {
        final response = Json.from(
          await api.request(
            'POST',
            '${snapshot['endpoint']}/boarding',
            Json.from(record['payload']),
          ),
        );
        await store.acknowledge(record, response);
      } on ApiFailure catch (e) {
        if (e.code == 'trip_closed') {
          closedTrips.add(snapshot['data']['trip']['id']);
          await store.closeTrip(snapshot['data']['trip']['id']);
        }
        if (e.status == 0 ||
            e.status == 401 ||
            e.status == 403 ||
            e.status >= 500) {
          rethrow;
        }
        await store.mark(
          record,
          e.status == 409 && e.code != 'trip_closed' ? 'conflict' : 'rejected',
          e.message,
        );
        blocked.add(scope);
      }
    }
    for (final snapshot in await store.snapshots()) {
      if ((await store.queue(snapshot['id'])).isNotEmpty) continue;
      try {
        final data = Json.from(
          await api.request('GET', '${snapshot['endpoint']}/offline-manifest'),
        );
        data['route'] = await api.request(
          'GET',
          '${(snapshot['endpoint'] as String).split('/legs/').first}/route',
        );
        await store.prepare(snapshot['endpoint'], data);
      } on ApiFailure catch (e) {
        if (e.code == 'trip_closed') {
          closedTrips.add(snapshot['data']['trip']['id']);
          await store.closeTrip(snapshot['data']['trip']['id']);
          continue;
        }
        if ([404, 409].contains(e.status)) {
          final data = Json.from(snapshot['data']);
          data['can_write'] = false;
          data['expires_at'] = DateTime.now().toUtc().toIso8601String();
          await store.prepare(snapshot['endpoint'], data);
        } else {
          rethrow;
        }
      }
    }
  });
  Future<bool> acceptServer(Json record) => run(() async {
    final snapshot = await store.snapshot(record['manifest']);
    Json data;
    try {
      data = Json.from(
        await api.request('GET', '${snapshot['endpoint']}/offline-manifest'),
      );
    } on ApiFailure catch (e) {
      if (e.status != 404 && e.code != 'trip_closed') rethrow;
      if (e.code == 'trip_closed') {
        closedTrips.add(snapshot['data']['trip']['id']);
        await store.closeTrip(snapshot['data']['trip']['id']);
      }
      data = Json.from((await store.snapshot(record['manifest']))['data']);
      data['can_write'] = false;
      data['expires_at'] = DateTime.now().toUtc().toIso8601String();
    }
    data['route'] = snapshot['data']['route'];
    await store.acceptServer(
      record['manifest'],
      record['payload']['passenger_id'],
      data,
    );
  });
}
