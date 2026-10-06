import 'dart:convert';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';
import 'package:crypto/crypto.dart' as hash;
import 'package:uuid/uuid.dart';

import 'api.dart';
import 'config.dart';
import 'offline.dart';

class LocalStore {
  final Database db;
  final SecretKey key;
  final cipher = AesGcm.with256bits();
  LocalStore(this.db, this.key);

  static Future<LocalStore> open(FlutterSecureStorage vault) async {
    final namespace = hash.sha256
        .convert(utf8.encode(AppConfig.apiUrl))
        .toString()
        .substring(0, 16);
    final keyName = 'database-key:$namespace';
    var encoded = await vault.read(key: keyName);
    if (encoded == null) {
      encoded = base64Encode(
        await (await AesGcm.with256bits().newSecretKey()).extractBytes(),
      );
      await vault.write(key: keyName, value: encoded);
    }
    final db = await openDatabase(
      path.join(await getDatabasesPath(), 'rotafy-$namespace.db'),
      version: 1,
      onCreate: createSchema,
    );
    return LocalStore(db, SecretKey(base64Decode(encoded)));
  }

  static Future<void> createSchema(Database db, int version) async {
    await db.execute(
      'CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    );
    await db.execute(
      'CREATE TABLE snapshots (id TEXT PRIMARY KEY, owner TEXT NOT NULL, endpoint TEXT NOT NULL, payload TEXT NOT NULL)',
    );
    await db.execute(
      'CREATE TABLE queue (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, owner TEXT NOT NULL, manifest TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, message TEXT)',
    );
  }

  Future<String> encode(dynamic value) async {
    final box = await cipher.encrypt(
      utf8.encode(jsonEncode(value)),
      secretKey: key,
    );
    return jsonEncode({
      'nonce': base64Encode(box.nonce),
      'cipher': base64Encode(box.cipherText),
      'mac': base64Encode(box.mac.bytes),
    });
  }

  Future<dynamic> decode(String value) async {
    final box = jsonDecode(value);
    final plain = await cipher.decrypt(
      SecretBox(
        base64Decode(box['cipher']),
        nonce: base64Decode(box['nonce']),
        mac: Mac(base64Decode(box['mac'])),
      ),
      secretKey: key,
    );
    return jsonDecode(utf8.decode(plain));
  }

  Future<dynamic> meta(String name) async {
    final rows = await db.query('meta', where: 'key=?', whereArgs: [name]);
    return rows.isEmpty ? null : decode(rows.first['value'] as String);
  }

  Future<void> setMeta(String name, dynamic value) async => db.insert('meta', {
    'key': name,
    'value': await encode(value),
  }, conflictAlgorithm: ConflictAlgorithm.replace);
  String owner(Json user) => '${user['company_id']}:${user['id']}';
  Future<int> pendingCount() async =>
      Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM queue')) ??
      0;

  Future<void> activate(Json user) async {
    final previous = await meta('user');
    if (previous != null && owner(previous) != owner(user)) {
      if (await pendingCount() > 0) {
        throw StateError(
          'Há registros de outro usuário. Entre com o acesso original para sincronizar.',
        );
      }
      await clear();
    }
    await setMeta('user', user);
  }

  Future<void> clear() async {
    await db.transaction((tx) async {
      if ((Sqflite.firstIntValue(
                await tx.rawQuery('SELECT COUNT(*) FROM queue'),
              ) ??
              0) >
          0) {
        throw StateError(
          'Sincronize ou revise os registros pendentes antes de sair.',
        );
      }
      await tx.delete('snapshots');
      await tx.delete('meta');
    });
  }

  Future<List<Json>> snapshots() async {
    final user = await meta('user');
    if (user == null) return [];
    final rows = await db.query(
      'snapshots',
      where: 'owner=?',
      whereArgs: [owner(user)],
    );
    return Future.wait(
      rows.map((r) async {
        final result = Json.from(r);
        result['data'] = await decode(result.remove('payload') as String);
        return result;
      }),
    );
  }

  Future<Json> snapshot(String id) async {
    final user = await meta('user');
    final rows = await db.query(
      'snapshots',
      where: 'id=? AND owner=?',
      whereArgs: [id, user == null ? '' : owner(user)],
    );
    if (rows.isEmpty) {
      throw StateError('Manifesto não pertence ao acesso ativo.');
    }
    final result = Json.from(rows.first);
    result['data'] = await decode(result.remove('payload') as String);
    return result;
  }

  Future<List<Json>> queue([String? manifest]) async {
    final user = await meta('user');
    final rows = await db.query(
      'queue',
      where: 'owner=?${manifest == null ? '' : ' AND manifest=?'}',
      whereArgs: [user == null ? '' : owner(user), ?manifest],
      orderBy: 'seq',
    );
    return Future.wait(
      rows.map((r) async {
        final result = Json.from(r);
        result['payload'] = await decode(r['payload'] as String);
        return result;
      }),
    );
  }

  Future<String> prepare(String endpoint, Json data) async {
    final user = await meta('user');
    if (user == null || owner(user) != owner(Json.from(data['operator']))) {
      throw StateError('Manifesto de outro acesso.');
    }
    final id = '${owner(user)}:$endpoint';
    if ((await queue(id)).isNotEmpty) {
      throw StateError(
        'Resolva a fila deste trecho antes de prepará-lo novamente.',
      );
    }
    await db.insert('snapshots', {
      'id': id,
      'owner': owner(user),
      'endpoint': endpoint,
      'payload': await encode(data),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
    return id;
  }

  Future<void> enqueue(
    String id,
    String passengerId,
    String action, {
    String? token,
    DateTime? capturedAt,
  }) async {
    final s = await snapshot(id);
    final data = Json.from(s['data']);
    final now = capturedAt ?? DateTime.now().toUtc();
    if (!DateTime.parse(data['expires_at']).isAfter(now) ||
        data['can_write'] != true) {
      throw StateError(
        'Manifesto vencido ou somente consulta. Prepare novamente com conexão.',
      );
    }
    final records = await queue(id);
    if (records.any(
      (r) =>
          r['payload']['passenger_id'] == passengerId &&
          r['status'] != 'pending',
    )) {
      throw StateError(
        'Revise o conflito deste passageiro antes de continuar.',
      );
    }
    final people = projectPassengers(
      data,
      records,
    ).where((p) => p['id'] == passengerId);
    if (people.isEmpty ||
        nextPresence(people.first['status'], action) == null) {
      throw StateError('Ação incompatível com a situação do passageiro.');
    }
    if (token != null &&
        matchTicket(
              data,
              token,
              Uri.parse(AppConfig.origin),
              now,
            )['passenger_id'] !=
            passengerId) {
      throw StateError('Bilhete de outro passageiro.');
    }
    final device = await meta('device') ?? const Uuid().v4();
    await setMeta('device', device);
    final operation = const Uuid().v4();
    final payload = {
      'operation_key': operation,
      'passenger_id': passengerId,
      'expected_version': people.first['version'],
      'action': action,
      'device_id': device,
      'captured_at': now.toIso8601String(),
      'offline': true,
      'expected_actor_id': data['operator']['id'],
      'token': ?token,
    };
    await db.insert('queue', {
      'id': operation,
      'owner': s['owner'],
      'manifest': id,
      'payload': await encode(payload),
      'status': 'pending',
    });
  }

  Future<void> acknowledge(Json record, Json response) async {
    final snapshot = await this.snapshot(record['manifest']);
    final data = Json.from(snapshot['data']);
    final passenger = (data['passengers'] as List).firstWhere(
      (p) => p['id'] == record['payload']['passenger_id'],
    );
    if ((passenger['version'] as int) <= (response['version'] as int)) {
      passenger['version'] = response['version'];
      passenger['status'] = response['status'];
    }
    final encoded = await encode(data);
    await db.transaction((tx) async {
      await tx.update(
        'snapshots',
        {'payload': encoded},
        where: 'id=?',
        whereArgs: [record['manifest']],
      );
      await tx.delete('queue', where: 'id=?', whereArgs: [record['id']]);
    });
  }

  Future<void> mark(Json record, String status, String message) async =>
      db.update(
        'queue',
        {'status': status, 'message': message},
        where: 'id=?',
        whereArgs: [record['id']],
      );
  Future<void> acceptServer(
    String manifest,
    String passengerId,
    Json refreshed,
  ) async {
    final snapshot = await this.snapshot(manifest);
    if (owner(Json.from(refreshed['operator'])) != snapshot['owner']) {
      throw StateError('Outro operador.');
    }
    final records = (await queue(manifest))
        .where((r) => r['payload']['passenger_id'] == passengerId);
    if (records.isEmpty || records.first['status'] == 'pending') {
      throw StateError(
        'Aguarde o resultado da sincronização antes de revisar.',
      );
    }
    final encoded = await encode(refreshed);
    await db.transaction((tx) async {
      for (final record in records) {
        await tx.delete('queue', where: 'id=?', whereArgs: [record['id']]);
      }
      await tx.update(
        'snapshots',
        {'payload': encoded},
        where: 'id=?',
        whereArgs: [manifest],
      );
    });
  }
}
