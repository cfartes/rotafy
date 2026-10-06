import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'store.dart';

class OperationController extends ChangeNotifier {
  final RotafyApi api;
  final LocalStore store;
  Json? user;
  List<Json> prepared = [];
  List<Json> records = [];
  bool busy = false;
  String? error;
  OperationController(this.api, this.store);

  Future<void> initialize() async {
    await api.restore();
    user = await store.meta('user');
    await reload();
  }

  Future<void> reload() async {
    prepared = await store.snapshots();
    records = await store.queue();
    notifyListeners();
  }

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
    String password,
  ) => run(() async {
    final oldCookies = Map<String, String>.from(api.cookies);
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
      await store.activate(result);
      await api.saveSession();
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
  });
  Future<bool> logout() => run(() async {
    if (await store.pendingCount() > 0) {
      throw StateError('Sincronize ou revise os registros antes de sair.');
    }
    try {
      await api.request('POST', '/auth/logout', {});
    } on ApiFailure catch (e) {
      if (e.status != 401) rethrow;
    }
    await store.clear();
    await api.clearSession();
    user = null;
  });

  Future<List<Json>> trips() async {
    final result = await api.request('GET', '/trips');
    return (result as List)
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
      data = Json.from(snapshot['data']);
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
