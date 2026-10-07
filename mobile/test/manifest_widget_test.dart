import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/ui/manifest.dart';

import 'offline_test.dart' show fixture, FakeApi;

void main() {
  sqfliteFfiInit();
  for (final role in ['driver', 'guide']) {
    testWidgets('$role has filters, collapse and bulk controls', (
      tester,
    ) async {
      late Database db;
      late OperationController controller;
      late String id;
      await tester.runAsync(() async {
        db = await databaseFactoryFfi.openDatabase(
          inMemoryDatabasePath,
          options: OpenDatabaseOptions(
            version: 1,
            onCreate: LocalStore.createSchema,
          ),
        );
        final store = LocalStore(db, SecretKey(List.filled(32, 7)));
        final data = fixture();
        data['operator']['role'] = role;
        data['journey'] = {'status': 'in_progress'};
        data['leg'] = {
          'id': 'ida',
          'origin': 'Origem',
          'destination': 'Destino',
        };
        data['expires_at'] = DateTime.now()
            .add(const Duration(hours: 1))
            .toUtc()
            .toIso8601String();
        data['passengers'] = [
          {
            'id': 'p1',
            'full_name': 'Pessoa a bordo',
            'status': 'onboard',
            'version': 1,
          },
          {
            'id': 'p2',
            'full_name': 'Pessoa aguardando',
            'status': 'waiting',
            'version': 0,
          },
          {
            'id': 'p3',
            'full_name': 'Pessoa desembarcada',
            'status': 'alighted',
            'version': 2,
          },
        ];
        await store.activate(Json.from(data['operator']));
        id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
        controller = OperationController(
          FakeApi((method, path, body) async => throw ApiFailure(0, 'Offline')),
          store,
        )..user = Json.from(data['operator']);
        await controller.reload();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: ManifestPage(controller: controller, manifestId: id),
        ),
      );
      expect(find.text('Trecho: Em viagem'), findsOneWidget);
      final arrival = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Fechar viagem · chegada no destino'),
      );
      expect(arrival.onPressed, isNull);
      await tester.tap(find.text('Desembarcar todos · 1 a bordo'));
      await tester.pumpAndSettle();
      expect(find.text('Desembarcar todos?'), findsOneWidget);
      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      expect(controller.records, isEmpty);
      await tester.scrollUntilVisible(find.text('Não embarcados'), 200);
      await tester.tap(find.text('Não embarcados'));
      await tester.pump();
      expect(find.text('Pessoa aguardando'), findsOneWidget);
      expect(find.text('Pessoa a bordo'), findsNothing);
      await tester.tap(find.text('Embarcados'));
      await tester.pump();
      expect(find.text('Pessoa a bordo'), findsOneWidget);
      expect(find.text('Pessoa aguardando'), findsNothing);
      await tester.tap(find.byTooltip('Recolher passageiros'));
      await tester.pump();
      expect(find.text('Pessoa a bordo'), findsNothing);
      await tester.tap(find.byTooltip('Expandir passageiros'));
      await tester.pump();
      expect(find.text('Pessoa a bordo'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
      await tester.runAsync(() => db.close());
    });
  }
}
