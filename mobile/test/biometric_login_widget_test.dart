import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:nexus_rotafy/core/controller.dart';
import 'package:nexus_rotafy/core/store.dart';
import 'package:nexus_rotafy/ui/app.dart';

import 'biometrics_test.dart' show FakeBiometrics;
import 'offline_test.dart' show FakeApi;

class RecordingLogin extends OperationController {
  bool? selected;
  int biometricCalls = 0;
  RecordingLogin(super.api, super.store, {super.biometrics});
  @override
  Future<bool> login(
    String company,
    String email,
    String password, {
    bool enableBiometrics = false,
  }) async {
    selected = enableBiometrics;
    return false;
  }

  @override
  Future<bool> loginWithBiometrics() async {
    biometricCalls++;
    return false;
  }
}

void main() {
  sqfliteFfiInit();
  Future<RecordingLogin> controller(WidgetTester tester) async {
    return (await tester.runAsync(() async {
      final db = await databaseFactoryFfi.openDatabase(
        inMemoryDatabasePath,
        options: OpenDatabaseOptions(
          version: 1,
          onCreate: LocalStore.createSchema,
        ),
      );
      return RecordingLogin(
        FakeApi((m, p, b) async => {}),
        LocalStore(db, SecretKey(List.filled(32, 7))),
        biometrics: FakeBiometrics(),
      );
    }))!;
  }

  testWidgets(
    'biometric saving is optional and opt in is passed to password login',
    (tester) async {
      final c = await controller(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(child: LoginForm(controller: c)),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        false,
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Empresa'),
        'empresa',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'E-mail'),
        'driver@example.com',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Senha'),
        'test-password',
      );
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await tester.ensureVisible(find.text('Entrar'));
      await tester.tap(find.text('Entrar'));
      await tester.pumpAndSettle();
      expect(c.selected, true);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.runAsync(() => c.store.db.close());
      c.dispose();
    },
  );

  testWidgets('password visibility preserves text without logging in', (
    tester,
  ) async {
    final c = await controller(tester);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(child: LoginForm(controller: c)),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final password = find.byType(TextFormField).last;
    await tester.enterText(password, 'Senha teste 123!');
    expect(
      tester.widget<TextFormField>(password).controller!.text,
      'Senha teste 123!',
    );
    expect(
      tester.widget<EditableText>(find.byType(EditableText).last).obscureText,
      isTrue,
    );
    await tester.tap(find.byTooltip('Mostrar senha'));
    await tester.pump();
    expect(
      tester.widget<EditableText>(find.byType(EditableText).last).obscureText,
      isFalse,
    );
    await tester.tap(find.byTooltip('Ocultar senha'));
    await tester.pump();
    expect(
      tester.widget<EditableText>(find.byType(EditableText).last).obscureText,
      isTrue,
    );
    expect(
      tester.widget<TextFormField>(password).controller!.text,
      'Senha teste 123!',
    );
    expect(c.selected, isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.runAsync(() => c.store.db.close());
    c.dispose();
  });

  testWidgets(
    'saved biometric login is available without filling password fields',
    (tester) async {
      final c = await controller(tester)
        ..biometricEnabled = true;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(child: LoginForm(controller: c)),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Entrar com biometria'));
      await tester.pumpAndSettle();
      expect(c.biometricCalls, 1);
      expect(c.selected, isNull);
      expect(find.text('Preencha este campo.'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.runAsync(() => c.store.db.close());
      c.dispose();
    },
  );
}
