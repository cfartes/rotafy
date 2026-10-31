import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/ui/manifest.dart';

import 'offline_test.dart' show fixture, FakeApi;
import 'location_test.dart' show FakeLocation;

void main() {
  sqfliteFfiInit();
  for (final scenario in ['started', 'other_phone', 'native_failure']) {
    final otherPhone = scenario == 'other_phone';
    final nativeFailure = scenario == 'native_failure';
    testWidgets(
      'automatic tracking confirms native start and sends initial GPS: $scenario',
      (tester) async {
        final previousLocation = GeolocatorPlatform.instance;
        GeolocatorPlatform.instance = FakeLocation();
        const channel = MethodChannel('rotafy/tracking');
        var nativeStarts = 0;
        var claims = 0;
        var positions = 0;
        var released = 0;
        var nativeStops = 0;
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, (call) async {
              if (call.method == 'start') {
                nativeStarts++;
                return !nativeFailure;
              }
              if (call.method == 'stop') nativeStops++;
              return null;
            });
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
          data['expires_at'] = DateTime.now()
              .add(const Duration(hours: 1))
              .toUtc()
              .toIso8601String();
          data['journey'] = {'status': 'scheduled'};
          data['leg'] = {
            'id': 'l',
            'starts_at': DateTime.now()
                .add(const Duration(minutes: 10))
                .toUtc()
                .toIso8601String(),
            'origin': 'Origin',
            'destination': 'Destination',
          };
          await store.activate(Json.from(data['operator']));
          id = await store.prepare('/trips/t/vehicles/v/legs/l', data);
          final api = FakeApi((method, path, body) async {
            if (path == '/auth/me') return data['operator'];
            if (path.endsWith('/route')) return {'legs': []};
            if (path.endsWith('/journey')) {
              return {
                'trip': {'id': 'trip', 'name': 'Trip', 'status': 'in_progress'},
                'journey': {'status': 'in_progress'},
              };
            }
            if (path == '/tracking/settings') return {'enabled': true};
            if (path == '/tracking/sessions/session/positions') {
              expect(nativeStarts, 1);
              expect(body!['positions'][0]['latitude'], -9.0123);
              expect(body['positions'][0]['accuracy_m'], 12.5);
              expect(body['positions'][0].containsKey('status'), false);
              positions++;
              return {'accepted': 1};
            }
            if (method == 'DELETE' && path == '/tracking/sessions/session') {
              released++;
              return {};
            }
            if (path == '/tracking/sessions') {
              claims++;
              if (otherPhone) {
                throw ApiFailure(409, 'Outro aparelho está responsável.');
              }
              return {'id': 'session'};
            }
            throw StateError('Unexpected endpoint $path');
          });
          controller = OperationController(api, store)
            ..user = Json.from(data['operator']);
          await controller.reload();
        });
        await tester.pumpWidget(
          MaterialApp(
            home: ManifestPage(controller: controller, manifestId: id),
          ),
        );
        await tester.tap(find.widgetWithText(FilledButton, 'Iniciar viagem'));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.widgetWithText(FilledButton, 'Iniciar viagem'),
          ),
        );
        for (var attempt = 0; attempt < 30; attempt++) {
          await tester.pump(const Duration(milliseconds: 30));
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 50)),
          );
          if (claims == 1 &&
              !controller.busy &&
              (otherPhone || positions == 1 || released == 1)) {
            break;
          }
        }
        await tester.pump();
        expect(claims, 1);
        expect(nativeStarts, otherPhone ? 0 : 1);
        expect(positions, otherPhone || nativeFailure ? 0 : 1);
        expect(released, nativeFailure ? 1 : 0);
        expect(nativeStops, nativeFailure ? 1 : 0);
        if (nativeFailure) {
          expect(
            find.textContaining('O Android não confirmou'),
            findsOneWidget,
          );
          expect(
            find.textContaining('Rastreamento iniciado neste celular'),
            findsNothing,
          );
        }
        expect(find.text('Compartilhar localização do veículo?'), findsNothing);
        await tester.pumpWidget(const SizedBox.shrink());
        controller.dispose();
        await tester.runAsync(() => db.close());
        GeolocatorPlatform.instance = previousLocation;
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null);
      },
    );
  }
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
        data['route'] = {
          'legs': [
            {
              'id': 'ida',
              'navigation_stages': [],
              'points': [
                {
                  'position': 0,
                  'name': 'Hotel Central',
                  'address': 'Rua das Flores, 100',
                  'complement': 'Recepção',
                  'passenger_names': ['Pessoa aguardando'],
                  'maps_url': 'https://www.google.com/maps/dir/?api=1',
                },
              ],
            },
          ],
        };
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
      await tester.scrollUntilVisible(find.text('1. Hotel Central'), -200);
      expect(find.textContaining('Rua das Flores, 100'), findsOneWidget);
      expect(
        find.textContaining('Passageiros: Pessoa aguardando'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
      await tester.runAsync(() => db.close());
    });
  }
}
