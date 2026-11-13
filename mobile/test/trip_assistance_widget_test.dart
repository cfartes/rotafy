import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/ui/manifest.dart';
import 'package:nexus_rotafy/ui/app.dart';

import 'offline_test.dart' show fixture, FakeApi;

Future<({OperationController controller, LocalStore store, String id})> session(
  Json data,
) async {
  final db = await databaseFactoryFfi.openDatabase(
    inMemoryDatabasePath,
    options: OpenDatabaseOptions(version: 1, onCreate: LocalStore.createSchema),
  );
  final store = LocalStore(db, SecretKey(List.filled(32, 7)));
  await store.activate(Json.from(data['operator']));
  final id = await store.prepare('/trips/t/vehicles/v/legs/ida', data);
  final controller = OperationController(
    FakeApi(
      (_, _, _) async => throw StateError('Nenhuma chamada de rede esperada.'),
    ),
    store,
  )..user = Json.from(data['operator']);
  await controller.reload();
  return (controller: controller, store: store, id: id);
}

Json data() => fixture()
  ..['expires_at'] = DateTime.now()
      .add(const Duration(hours: 8))
      .toUtc()
      .toIso8601String()
  ..['journey'] = {'status': 'in_progress', 'started_at': '2026-11-13T10:00:00'}
  ..['leg'] = {
    'id': 'ida',
    'origin': 'Origem',
    'destination': 'Destino',
    'starts_at': DateTime.now()
        .subtract(const Duration(minutes: 5))
        .toIso8601String(),
    'ends_at': '2026-11-13T15:00:00',
  };

void main() {
  sqfliteFfiInit();
  setUpAll(() async {
    final fonts = File(Platform.resolvedExecutable).parent.parent.parent;
    // Widget tests do not include the device's fallback font for arrows.
    final symbols = File('${Platform.environment['WINDIR']}/Fonts/arial.ttf');
    if (Platform.isWindows && await symbols.exists()) {
      await (FontLoader('TestSymbols')..addFont(
            symbols.readAsBytes().then((bytes) => ByteData.sublistView(bytes)),
          ))
          .load();
    }
    for (final font in [
      ('Roboto', 'roboto-regular.ttf'),
      ('MaterialIcons', 'materialicons-regular.otf'),
    ]) {
      await (FontLoader(font.$1)..addFont(
            File('${fonts.path}/material_fonts/${font.$2}')
                .readAsBytes()
                .then((bytes) => ByteData.sublistView(bytes)),
          ))
          .load();
    }
  });
  testWidgets(
    'next stop follows local operations; queues and stale upload have distinct feedback',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final boundary = GlobalKey();
      final snapshot = data();
      snapshot['passengers'] = [
        {'id': 'p1', 'full_name': 'Maria', 'status': 'waiting', 'version': 0},
        {'id': 'p2', 'full_name': 'João', 'status': 'waiting', 'version': 0},
      ];
      snapshot['route'] = {
        'legs': [
          {
            'id': 'ida',
            'navigation_stages': [],
            'points': [
              {
                'position': 0,
                'name': 'Hotel',
                'address': 'Rua Um, 100',
                'boarding_passenger_ids': ['p1', 'p2'],
                'dropoff_passenger_ids': [],
                'maps_url': 'https://www.google.com/maps/dir/?api=1',
              },
              {
                'position': 1,
                'name': 'Terminal',
                'boarding_passenger_ids': [],
                'dropoff_passenger_ids': ['p1', 'p2'],
              },
            ],
          },
        ],
      };
      final state = (await tester.runAsync(() => session(snapshot)))!;
      const channel = MethodChannel('rotafy/tracking');
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            channel,
            (_) async => {
              'active': true,
              'endpoint': '/trips/t/vehicles/v/legs/ida',
              'started_at': DateTime.now()
                  .subtract(const Duration(minutes: 10))
                  .millisecondsSinceEpoch,
              'last_captured_at': DateTime.now().millisecondsSinceEpoch,
              'last_sent_at': DateTime.now()
                  .subtract(const Duration(minutes: 4))
                  .millisecondsSinceEpoch,
            },
          );
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: operationTheme().copyWith(
            textTheme: operationTheme().textTheme.apply(
              fontFamilyFallback: ['TestSymbols'],
            ),
          ),
          home: RepaintBoundary(
            key: boundary,
            child: ManifestPage(
              controller: state.controller,
              manifestId: state.id,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Embarcar: 2 · Desembarcar: 0'), findsOneWidget);
      await tester.runAsync(() async {
        final image =
            await (boundary.currentContext!.findRenderObject()
                    as RenderRepaintBoundary)
                .toImage();
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await File('../docs/screenshots/apk-proxima-parada.png')
            .writeAsBytes(bytes!.buffer.asUint8List());
        image.dispose();
      });
      await tester.scrollUntilVisible(
        find.text('Localização sem envio confirmado'),
        200,
      );
      expect(find.text('Localização sem envio confirmado'), findsOneWidget);
      await tester.runAsync(() async {
        await state.controller.enqueue(state.id, 'p1', 'board');
        await state.controller.enqueue(state.id, 'p2', 'board');
      });
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Embarcar: 0 · Desembarcar: 2'),
        -200,
      );
      expect(find.text('Embarcar: 0 · Desembarcar: 2'), findsOneWidget);
      await tester.runAsync(() async {
        final first = (await state.store.queue(state.id)).first;
        await state.store.mark(
          first,
          'conflict',
          'Confira a versão do passageiro.',
        );
        await state.controller.reload();
      });
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Precisam de revisão · 1'),
        300,
      );
      expect(find.text('Precisam de revisão · 1'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Aguardando envio · 1'), 150);
      expect(find.text('Aguardando envio · 1'), findsOneWidget);
      expect(state.controller.records, hasLength(2));
      await tester.pumpWidget(const SizedBox.shrink());
      state.controller.dispose();
      await tester.runAsync(() => state.store.db.close());
    },
  );
  testWidgets(
    'arrival preview shows execution totals and cancel never closes the journey',
    (tester) async {
      final snapshot = data();
      snapshot['passengers'][0]['status'] = 'alighted';
      final state = (await tester.runAsync(() => session(snapshot)))!;
      await tester.pumpWidget(
        MaterialApp(
          home: ManifestPage(
            controller: state.controller,
            manifestId: state.id,
          ),
        ),
      );
      await tester.pumpAndSettle();
      final close = find.text('Fechar viagem · chegada no destino');
      await tester.scrollUntilVisible(close, 200);
      await tester.tap(close);
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Saída registrada: 13/11/2026 às 10:00'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Chegada prevista: 13/11/2026 às 15:00'),
        findsOneWidget,
      );
      expect(find.textContaining('Desembarcados: 1'), findsOneWidget);
      expect(
        find.textContaining('Registros aguardando envio: 0'),
        findsOneWidget,
      );
      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      expect(
        state.controller.prepared.single['data']['journey']['status'],
        'in_progress',
      );
      await tester.pumpWidget(const SizedBox.shrink());
      state.controller.dispose();
      await tester.runAsync(() => state.store.db.close());
    },
  );
}
