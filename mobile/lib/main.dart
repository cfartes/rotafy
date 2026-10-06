import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'core/api.dart';
import 'core/config.dart';
import 'core/controller.dart';
import 'core/store.dart';
import 'ui/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    AppConfig.validate();
    const vault = FlutterSecureStorage();
    final store = await LocalStore.open(vault);
    final controller = OperationController(RotafyApi(vault), store);
    await controller.initialize();
    runApp(RotafyApp(controller: controller));
  } catch (_) {
    runApp(
      const MaterialApp(
        home: Scaffold(
          body: SafeArea(
            child: Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Não foi possível abrir o armazenamento seguro. Reinicie o aplicativo. Não desinstale se houver registros pendentes.',
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
