import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/controller.dart';
import '../core/updates.dart';

class UpdateNotice extends StatefulWidget {
  final OperationController controller;
  final Widget child;
  const UpdateNotice({
    super.key,
    required this.controller,
    required this.child,
  });
  @override
  State<UpdateNotice> createState() => _UpdateNoticeState();
}

class _UpdateNoticeState extends State<UpdateNotice>
    with WidgetsBindingObserver {
  AndroidUpdate? update;
  bool checking = false;
  String? error;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    check();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) check();
  }

  Future<void> check() async {
    if (checking) return;
    checking = true;
    try {
      final installed = Json.from(
        jsonDecode(await rootBundle.loadString('assets/release.json')),
      );
      final available = await AndroidUpdate.check(
        widget.controller.api,
        installed,
      );
      if (mounted) setState(() => update = available);
    } catch (_) {
      /* A failed check never blocks offline work or clears records. */
    } finally {
      checking = false;
    }
  }

  Future<void> download() async {
    try {
      final opened = await launchUrl(
        Uri.parse(AppConfig.origin).resolve(update!.path),
        mode: LaunchMode.externalApplication,
      );
      if (!opened) throw StateError('download');
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              error = 'Não foi possível abrir o download. Confira sua conexão.',
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Expanded(child: widget.child),
      if (update != null)
        Material(
          color: const Color(0xffe1f2ef),
          child: SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Nova versão ${update!.version} disponível.',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const Text(
                    'Instale a atualização por cima do aplicativo atual, sem desinstalar.',
                  ),
                  if (widget.controller.records.isNotEmpty)
                    const Text(
                      'Há registros locais. Sincronize os pendentes antes de atualizar.',
                    ),
                  if (error != null) Text(error!),
                  FilledButton.icon(
                    onPressed: download,
                    icon: const Icon(Icons.system_update),
                    label: const Text('Atualizar aplicativo'),
                  ),
                ],
              ),
            ),
          ),
        ),
    ],
  );
}
