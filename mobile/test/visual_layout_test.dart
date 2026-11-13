import 'dart:io';
import 'dart:ui' as ui;

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/ui/agenda.dart';
import 'package:nexus_rotafy/ui/app.dart';
import 'package:nexus_rotafy/ui/manifest.dart';

import 'offline_test.dart' show fixture, FakeApi;

void main() {
  sqfliteFfiInit();
  setUpAll(() async {
    final fonts = File(Platform.resolvedExecutable).parent.parent.parent;
    final loader = FontLoader('Roboto')
      ..addFont(
        File('${fonts.path}/material_fonts/roboto-regular.ttf')
            .readAsBytes()
            .then((bytes) => ByteData.sublistView(bytes)),
      );
    await loader.load();
    await (FontLoader('MaterialIcons')..addFont(
          File('${fonts.path}/material_fonts/materialicons-regular.otf')
              .readAsBytes()
              .then((bytes) => ByteData.sublistView(bytes)),
        ))
        .load();
  });
  for (final width in [320.0, 390.0]) {
    testWidgets(
      'manifest preserves scanning and guards with large text at $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        late LocalStore store;
        late OperationController controller;
        late String id;
        await tester.runAsync(() async {
          final db = await databaseFactoryFfi.openDatabase(
            inMemoryDatabasePath,
            options: OpenDatabaseOptions(
              version: 1,
              onCreate: LocalStore.createSchema,
            ),
          );
          store = LocalStore(db, SecretKey(List.filled(32, 7)));
          final data = fixture();
          data['trip']['name'] = 'Passeio de demonstração com nome extenso para leitura no celular';
          data['leg'] = {
            'id': 'ida',
            'origin': 'Blumenau',
            'destination': 'Balneário Camboriú',
            'starts_at': DateTime.now().toUtc().toIso8601String(),
          };
          data['journey'] = {'status': 'in_progress'};
          data['expires_at'] = DateTime.now()
              .add(const Duration(hours: 8))
              .toUtc()
              .toIso8601String();
          await store.activate(Json.from(data['operator']));
          id = await store.prepare('/trips/t/vehicles/v/legs/ida', data);
          controller = OperationController(
            FakeApi((_, _, _) async => []),
            store,
          )..user = Json.from(data['operator']);
          await controller.reload();
          await controller.enqueue(id, 'p1', 'board');
        });
        final boundary = GlobalKey();
        await tester.pumpWidget(
          MaterialApp(
            theme: operationTheme(),
            home: MediaQuery(
              data: MediaQueryData(
                size: Size(width, 844),
                textScaler: const TextScaler.linear(1.4),
              ),
              child: RepaintBoundary(
                key: boundary,
                child: ManifestPage(controller: controller, manifestId: id),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final scan = find.widgetWithText(FilledButton, 'Ler QR do passageiro');
        expect(tester.getRect(scan).bottom, lessThanOrEqualTo(844));
        expect(tester.getRect(scan).height, greaterThanOrEqualTo(48));
        expect(tester.widget<FilledButton>(scan).onPressed, isNotNull);
        expect(find.text('1 a bordo'), findsOneWidget);
        final close = find.widgetWithText(
          OutlinedButton,
          'Fechar viagem · chegada no destino',
        );
        await tester.scrollUntilVisible(close, 200);
        expect(tester.widget<OutlinedButton>(close).onPressed, isNull);
        await tester.drag(find.byType(ListView).first, const Offset(0, -500));
        await tester.pumpAndSettle();
        expect(tester.getRect(scan).bottom, lessThanOrEqualTo(844));
        expect(tester.takeException(), isNull);
        if (width == 390) {
          await tester.drag(find.byType(ListView).first, const Offset(0, 3000));
          await tester.pumpAndSettle();
          await tester.runAsync(() async {
            final image =
                await (boundary.currentContext!.findRenderObject()
                        as RenderRepaintBoundary)
                    .toImage();
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            final file = File('../artifacts/mobile/manifest-visual.png');
            await file.parent.create(recursive: true);
            await file.writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }
        await tester.pumpWidget(const SizedBox.shrink());
        controller.dispose();
        await tester.runAsync(() => store.db.close());
      },
    );
  }
  testWidgets('agenda wraps long names and large text on a narrow phone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final now = DateTime(2026, 11, 13, 8);
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(
            size: Size(320, 844),
            textScaler: TextScaler.linear(1.8),
          ),
          child: Scaffold(
            body: AgendaList(
              now: now,
              trips: [
                {
                  'id': 't',
                  'name': 'Viagem de demonstração com nome muito extenso para validar acessibilidade',
                  'starts_at': now.toIso8601String(),
                  'status': 'scheduled',
                  'destination': 'Balneário Camboriú',
                },
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Destino: Balneário Camboriú'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
