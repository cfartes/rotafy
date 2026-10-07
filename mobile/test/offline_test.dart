import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/offline.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/location.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const company = '11111111-1111-1111-1111-111111111111';
final now = DateTime.utc(2026, 10, 6, 12);
final token = 'bt.$company.${List.filled(43, 'A').join()}';
Json fixture() => {
  'operator': {'id': 'driver', 'company_id': company, 'role': 'driver'},
  'trip': {'id': 'trip', 'name': 'Aeroporto', 'status': 'scheduled'},
  'vehicle': {'id': 'vehicle', 'name': 'Executivo'},
  'leg': {'id': 'ida'},
  'can_write': true,
  'expires_at': now.add(const Duration(hours: 8)).toIso8601String(),
  'passengers': [
    {
      'id': 'p1',
      'full_name': 'Passageiro exemplo',
      'status': 'waiting',
      'version': 0,
    },
  ],
  'tickets': [
    {
      'passenger_id': 'p1',
      'token_hash': sha256.convert(utf8.encode(token)).toString(),
    },
  ],
};

class FakeApi extends RotafyApi {
  final Future<dynamic> Function(String, String, Json?) handler;
  FakeApi(this.handler) : super(const FlutterSecureStorage());
  @override
  Future<dynamic> request(String method, String path, [Json? data]) =>
      handler(method, path, data);
}

class FixedArrivalLocation extends ArrivalLocationService {
  final Json result;
  int captures = 0;
  FixedArrivalLocation(this.result);
  @override
  Future<Json> capture() async {
    captures++;
    return result;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  late LocalStore store;
  setUp(() async {
    final db = await databaseFactoryFfi.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: LocalStore.createSchema,
      ),
    );
    store = LocalStore(db, SecretKey(List.filled(32, 7)));
    await store.activate(Json.from(fixture()['operator']));
  });
  tearDown(() => store.db.close());

  for (final gps in [
    {
      'status': 'captured',
      'latitude': -9.01,
      'longitude': -35.22,
      'accuracy_m': 10.0,
      'captured_at': '2026-10-07T15:00:00Z',
    },
    {'status': 'unavailable', 'reason': 'permission_denied'},
  ]) {
    test(
      'arrival sends ${gps['status']} location; start does not capture',
      () async {
        final data = fixture();
        final id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
        final location = FixedArrivalLocation(gps);
        final bodies = <Json>[];
        final controller = OperationController(
          FakeApi((method, path, body) async {
            if (path == '/auth/me') return data['operator'];
            bodies.add(body!);
            return {
              ...data,
              'journey': {'status': body['status']},
            };
          }),
          store,
          location: location,
        )..user = Json.from(data['operator']);
        expect(await controller.changeJourney(id, 'in_progress'), true);
        expect(location.captures, 0);
        expect(bodies.first.containsKey('arrival_location'), false);
        expect(await controller.changeJourney(id, 'completed'), true);
        expect(bodies.last['arrival_location'], gps);
        expect(location.captures, 1);
        expect(controller.prepared, isEmpty);
        controller.dispose();
      },
    );
  }

  test(
    'completed trips hide all cached legs and stay hidden after restart',
    () async {
      final data = fixture();
      await store.prepare('/trips/t/vehicles/v/legs/ida', data);
      await store.prepare('/trips/t/vehicles/v/legs/volta', data);
      final controller = OperationController(
        FakeApi(
          (m, p, b) async => [
            {'id': 'trip', 'status': 'completed'},
            {'id': 'other', 'status': 'scheduled'},
          ],
        ),
        store,
      );
      expect((await controller.trips()).single['id'], 'other');
      expect(controller.prepared, isEmpty);
      final restarted = OperationController(controller.api, store);
      await restarted.reload();
      expect(restarted.prepared, isEmpty);
      expect(restarted.closedTrips, contains('trip'));
      controller.dispose();
      restarted.dispose();
    },
  );

  test(
    'closed leg hides only itself and closed trip keeps pending review',
    () async {
      final data = fixture();
      data['journey'] = {'status': 'completed'};
      await store.prepare('/trips/t/vehicles/v/legs/ida', data);
      final active = fixture();
      final id = await store.prepare('/trips/t/vehicles/v/legs/volta', active);
      final controller = OperationController(
        FakeApi((m, p, b) async => []),
        store,
      );
      await controller.reload();
      expect(controller.prepared.single['id'], id);
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      await store.closeTrip('trip');
      await controller.reload();
      expect(controller.prepared.single['id'], id);
      expect(controller.prepared.single['data']['can_write'], false);
      expect(controller.records, hasLength(1));
      controller.dispose();
    },
  );

  test('bulk disembark preserves waiting and alighted passengers and is repeat safe', () async {
    final data = fixture();
    data['passengers'] = [
      {'id': 'p1', 'full_name': 'A bordo', 'status': 'onboard', 'version': 1},
      {
        'id': 'p2',
        'full_name': 'Não embarcou',
        'status': 'waiting',
        'version': 0,
      },
      {'id': 'p3', 'full_name': 'Já saiu', 'status': 'alighted', 'version': 2},
    ];
    final id = await store.prepare('/trip/vehicle/leg', data);
    expect(await store.disembarkAll(id, capturedAt: now), 1);
    final command = (await store.queue()).single;
    expect(command['payload']['passenger_id'], 'p1');
    expect(command['payload']['expected_version'], 1);
    expect(
      projectPassengers(data, await store.queue()).map((p) => p['status']),
      ['alighted', 'waiting', 'alighted'],
    );
    expect(await store.disembarkAll(id, capturedAt: now), 0);
    expect((await store.queue()).length, 1);
  });

  test(
    'bulk conflict blocks whole batch before inserting any additional command',
    () async {
      final data = fixture();
      data['passengers'] = [
        {
          'id': 'p1',
          'full_name': 'Primeiro',
          'status': 'onboard',
          'version': 1,
        },
        {'id': 'p2', 'full_name': 'Segundo', 'status': 'onboard', 'version': 1},
      ];
      final id = await store.prepare('/trip/vehicle/leg', data);
      await store.enqueue(id, 'p1', 'disembark', capturedAt: now);
      await store.mark(
        (await store.queue()).single,
        'conflict',
        'Outro aparelho',
      );
      await expectLater(
        store.disembarkAll(id, capturedAt: now),
        throwsStateError,
      );
      expect((await store.queue()).length, 1);
    },
  );

  test(
    'journey change refuses pending commands before contacting the API',
    () async {
      final data = fixture();
      final id = await store.prepare('/trip/vehicle/leg', data);
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      var calls = 0;
      final controller = OperationController(
        FakeApi((method, path, body) async {
          calls++;
          return {};
        }),
        store,
      )..user = Json.from(data['operator']);
      expect(await controller.changeJourney(id, 'completed'), false);
      expect(calls, 0);
      expect((await store.queue()).length, 1);
      controller.dispose();
    },
  );

  test('disk queue survives closing and reopening the database', () async {
    final directory = await Directory.systemTemp.createTemp(
      'rotafy-mobile-test-',
    );
    final filename = '${directory.path}/offline.db';
    Database? disk;
    try {
      disk = await databaseFactoryFfi.openDatabase(
        filename,
        options: OpenDatabaseOptions(
          version: 1,
          onCreate: LocalStore.createSchema,
        ),
      );
      final original = LocalStore(disk, store.key);
      await original.activate(Json.from(fixture()['operator']));
      final id = await original.prepare('/trip/vehicle/leg', fixture());
      await original.enqueue(id, 'p1', 'board', token: token, capturedAt: now);
      final operation = (await original.queue()).single['payload'];
      await disk.close();
      disk = await databaseFactoryFfi.openDatabase(filename);
      final reopened = LocalStore(disk, store.key);
      expect((await reopened.queue()).single['payload'], operation);
      expect(
        (await reopened.snapshot(id))['data']['passengers'][0]['status'],
        'waiting',
      );
      expect(await reopened.meta('user'), fixture()['operator']);
    } finally {
      if (disk != null && disk.isOpen) await disk.close();
      await directory.delete(recursive: true);
    }
  });

  test(
    'partial synchronization failure refreshes the visible durable queue',
    () async {
      final data = fixture();
      data['expires_at'] = DateTime.now()
          .add(const Duration(hours: 1))
          .toUtc()
          .toIso8601String();
      final id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
      await store.enqueue(id, 'p1', 'board');
      await store.enqueue(id, 'p1', 'disembark');
      var posts = 0;
      final api = FakeApi((method, path, body) async {
        if (path == '/auth/me') return data['operator'];
        if (path.endsWith('/boarding')) {
          if (++posts == 1) return {'status': 'onboard', 'version': 1};
          throw ApiFailure(0, 'Conexão interrompida');
        }
        throw StateError('Unexpected request');
      });
      final controller = OperationController(api, store)
        ..user = Json.from(data['operator']);
      await controller.reload();
      expect(controller.records.length, 2);
      expect(await controller.synchronize(), false);
      expect(controller.error, 'Conexão interrompida');
      expect(controller.records.length, 1);
      expect(controller.records.single['payload']['action'], 'disembark');
      expect(
        controller.prepared.single['data']['passengers'][0]['status'],
        'onboard',
      );
      controller.dispose();
    },
  );

  test('QR validates company, origin, manifest and expiry', () {
    final data = fixture();
    final origin = Uri.parse('https://frotafy.nexusdataanalytics.com.br');
    expect(matchTicket(data, token, origin, now)['passenger_id'], 'p1');
    expect(
      matchTicket(data, '$origin/bilhete#token=$token', origin, now)['token'],
      token,
    );
    expect(
      () => matchTicket(
        data,
        'https://outro.example/bilhete#token=$token',
        origin,
        now,
      ),
      throwsStateError,
    );
    expect(
      () =>
          matchTicket(data, token.replaceFirst(company, 'outra'), origin, now),
      throwsStateError,
    );
    expect(
      () => matchTicket({...data, 'tickets': []}, token, origin, now),
      throwsStateError,
    );
    expect(
      () => matchTicket(data, token, origin, now.add(const Duration(hours: 9))),
      throwsStateError,
    );
  });
  test(
    'queue projects board and disembark without confirming server state',
    () async {
      final id = await store.prepare('/trip/vehicle/leg', fixture());
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      await store.enqueue(id, 'p1', 'disembark', capturedAt: now);
      final q = await store.queue(id);
      expect(q.map((r) => r['payload']['expected_version']), [0, 1]);
      expect(projectPassengers(fixture(), q).single['status'], 'alighted');
      expect(
        (await store.snapshot(id))['data']['passengers'][0]['status'],
        'waiting',
      );
      await expectLater(
        store.enqueue(id, 'p1', 'board', capturedAt: now),
        throwsStateError,
      );
    },
  );
  test(
    'encrypted queue survives reopen and blocks logout and other operator',
    () async {
      final id = await store.prepare('/trip/vehicle/leg', fixture());
      await store.enqueue(id, 'p1', 'board', token: token, capturedAt: now);
      final raw = await store.db.query('queue');
      expect(raw.toString().contains(token), false);
      expect(
        (await store.db.query('snapshots'))
            .toString()
            .contains('Passageiro exemplo'),
        false,
      );
      final reopened = LocalStore(store.db, store.key);
      expect((await reopened.queue()).single['payload']['token'], token);
      await expectLater(store.clear(), throwsStateError);
      await expectLater(
        store.activate({'id': 'guide', 'company_id': company}),
        throwsStateError,
      );
      await expectLater(
        store.prepare('/trip/vehicle/leg', fixture()),
        throwsStateError,
      );
    },
  );
  test(
    'acknowledgement atomically updates base and preserves remaining command',
    () async {
      final id = await store.prepare('/trip/vehicle/leg', fixture());
      await store.enqueue(id, 'p1', 'board', capturedAt: now);
      await store.enqueue(id, 'p1', 'disembark', capturedAt: now);
      final first = (await store.queue(id)).first;
      await store.acknowledge(first, {'status': 'onboard', 'version': 1});
      expect((await store.queue(id)).length, 1);
      final data = Json.from((await store.snapshot(id))['data']);
      expect(data['passengers'][0]['status'], 'onboard');
      expect(
        projectPassengers(data, await store.queue(id)).single['status'],
        'alighted',
      );
    },
  );
  test('conflict blocks dependent records and deliberate review clears their chain', () async {
    final id = await store.prepare('/trip/vehicle/leg', fixture());
    await store.enqueue(id, 'p1', 'board', capturedAt: now);
    await store.enqueue(id, 'p1', 'disembark', capturedAt: now);
    await store.mark(
      (await store.queue(id)).first,
      'conflict',
      'Outro operador alterou.',
    );
    expect(
      projectPassengers(fixture(), await store.queue(id)).single['status'],
      'waiting',
    );
    await expectLater(
      store.enqueue(id, 'p1', 'board', capturedAt: now),
      throwsStateError,
    );
    await store.acceptServer(id, 'p1', fixture());
    expect(await store.pendingCount(), 0);
  });
  test('expired or read-only preparation never accepts local write', () async {
    final id = await store.prepare('/trip/vehicle/leg', fixture());
    await expectLater(
      store.enqueue(
        id,
        'p1',
        'board',
        capturedAt: now.add(const Duration(hours: 9)),
      ),
      throwsStateError,
    );
    await store.prepare('/trip/vehicle/leg', {
      ...fixture(),
      'can_write': false,
    });
    await expectLater(
      store.enqueue(id, 'p1', 'board', capturedAt: now),
      throwsStateError,
    );
  });

  test(
    'lost response preserves operation key and retry acknowledges once',
    () async {
      final data = fixture();
      data['expires_at'] = DateTime.now()
          .add(const Duration(hours: 1))
          .toUtc()
          .toIso8601String();
      final id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
      await store.enqueue(id, 'p1', 'board');
      final sent = <Json>[];
      final api = FakeApi((method, path, body) async {
        if (path == '/auth/me') return fixture()['operator'];
        if (path.endsWith('/boarding')) {
          sent.add(Json.from(body!));
          if (sent.length == 1) throw ApiFailure(0, 'Resposta perdida');
          return {'status': 'onboard', 'version': 1, 'replayed': true};
        }
        if (path.endsWith('/route')) return {'legs': []};
        return {
          ...data,
          'passengers': [
            {
              'id': 'p1',
              'full_name': 'Passageiro exemplo',
              'status': 'onboard',
              'version': 1,
            },
          ],
        };
      });
      final controller = OperationController(api, store)
        ..user = Json.from(data['operator']);
      expect(await controller.synchronize(), false);
      expect(await store.pendingCount(), 1);
      expect(await controller.synchronize(), true);
      expect(sent[0], sent[1]);
      expect(await store.pendingCount(), 0);
      expect(
        (await store.snapshot(id))['data']['passengers'][0]['status'],
        'onboard',
      );
      controller.dispose();
    },
  );

  test(
    'server conflict never sends dependent disembark before review',
    () async {
      final data = fixture();
      data['expires_at'] = DateTime.now()
          .add(const Duration(hours: 1))
          .toUtc()
          .toIso8601String();
      final id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
      await store.enqueue(id, 'p1', 'board');
      await store.enqueue(id, 'p1', 'disembark');
      var posts = 0;
      final api = FakeApi((method, path, body) async {
        if (path == '/auth/me') return data['operator'];
        if (path.endsWith('/boarding')) {
          posts++;
          throw ApiFailure(409, 'Outro operador', 'version_conflict');
        }
        return data;
      });
      final controller = OperationController(api, store)
        ..user = Json.from(data['operator']);
      expect(await controller.synchronize(), true);
      expect(posts, 1);
      expect((await store.queue(id)).map((r) => r['status']), [
        'conflict',
        'pending',
      ]);
      expect(await controller.synchronize(), true);
      expect(posts, 1);
      controller.dispose();
    },
  );

  test('closed trip rejection can be explicitly discarded without losing other scope', () async {
    final data = fixture();
    data['expires_at'] = DateTime.now()
        .add(const Duration(hours: 1))
        .toUtc()
        .toIso8601String();
    final id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
    await store.enqueue(id, 'p1', 'board');
    final record = (await store.queue(id)).first;
    await store.mark(record, 'rejected', 'Viagem encerrada');
    final api = FakeApi(
      (method, path, body) async =>
          throw ApiFailure(409, 'Viagem encerrada', 'trip_closed'),
    );
    final controller = OperationController(api, store)
      ..user = Json.from(data['operator']);
    expect(
      await controller.acceptServer({...record, 'status': 'rejected'}),
      true,
    );
    expect(await store.pendingCount(), 0);
    expect((await store.snapshot(id))['data']['can_write'], false);
    controller.dispose();
  });
}
