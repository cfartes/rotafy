import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/controller.dart';
import '../core/offline.dart';

const presenceLabels = {
  'waiting': 'Aguardando embarque',
  'onboard': 'A bordo',
  'alighted': 'Desembarcado',
};

class ManifestPage extends StatelessWidget {
  final OperationController controller;
  final String manifestId;
  const ManifestPage({
    super.key,
    required this.controller,
    required this.manifestId,
  });
  Future<void> scan(BuildContext context, Json data) async {
    final raw = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const ScannerPage()),
    );
    if (raw == null || !context.mounted) return;
    try {
      final ticket = matchTicket(
        data,
        raw,
        Uri.parse(AppConfig.origin),
        DateTime.now().toUtc(),
      );
      final people = projectPassengers(
        data,
        controller.records.where((r) => r['manifest'] == manifestId).toList(),
      );
      final passenger = people.firstWhere(
        (p) => p['id'] == ticket['passenger_id'],
      );
      if (passenger['status'] != 'waiting') {
        throw StateError(
          'Este passageiro já possui um embarque registrado neste trecho.',
        );
      }
      final confirm = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirmar embarque'),
          content: Text(
            '${passenger['full_name']}\n${passenger['boarding']} → ${passenger['dropoff']}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Registrar embarque'),
            ),
          ],
        ),
      );
      if (confirm == true &&
          await controller.enqueue(
            manifestId,
            passenger['id'],
            'board',
            token: ticket['token'],
          )) {
        unawaited(HapticFeedback.mediumImpact());
        unawaited(SystemSound.play(SystemSoundType.click));
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Embarque registrado no celular. Aguardando sincronização.',
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString().replaceFirst('Bad state: ', ''))),
        );
      }
    }
  }

  Future<void> openMaps(BuildContext context, String raw) async {
    final uri = Uri.parse(raw);
    if (uri.scheme != 'https' || uri.host != 'www.google.com') return;
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Não foi possível abrir o Google Maps.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) {
      final snapshots = controller.prepared.where((s) => s['id'] == manifestId);
      if (snapshots.isEmpty) {
        return Scaffold(
          appBar: AppBar(title: const Text('Manifesto indisponível')),
        );
      }
      final data = Json.from(snapshots.first['data']);
      final records = controller.records
          .where((r) => r['manifest'] == manifestId)
          .toList();
      final passengers = projectPassengers(data, records);
      final expired = !DateTime.parse(data['expires_at'])
          .isAfter(DateTime.now().toUtc());
      final canWrite =
          !expired && data['can_write'] == true && !controller.busy;
      final legs = data['route']?['legs'] as List? ?? [];
      final route = legs.where((l) => l['id'] == data['leg']['id']);
      return Scaffold(
        appBar: AppBar(title: Text(data['vehicle']['name'])),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                data['trip']['name'],
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text('${data['leg']['origin']} → ${data['leg']['destination']}'),
              Text(
                'Preparado até ${DateTime.parse(data['expires_at']).toLocal()}',
              ),
              if (expired)
                const Text(
                  'Preparação vencida. Conecte-se e prepare o trecho novamente. A fila foi preservada.',
                ),
              const Text(
                'Cancelamentos, revogações e alterações de outros aparelhos são conferidos ao sincronizar.',
              ),
              if (controller.busy) const LinearProgressIndicator(),
              if (controller.error != null)
                Text(
                  controller.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              FilledButton.icon(
                onPressed: canWrite ? () => scan(context, data) : null,
                icon: const Icon(Icons.qr_code_scanner),
                label: const Text('Ler QR do passageiro'),
              ),
              OutlinedButton.icon(
                onPressed: controller.busy ? null : controller.synchronize,
                icon: const Icon(Icons.sync),
                label: Text('Sincronizar · ${records.length} registros'),
              ),
              if (route.isNotEmpty)
                ...(route.first['navigation_stages'] as List)
                    .asMap()
                    .entries
                    .map(
                      (entry) => OutlinedButton.icon(
                        onPressed: () =>
                            openMaps(context, entry.value['maps_url']),
                        icon: const Icon(Icons.map),
                        label: Text(
                          'Abrir rota no Google Maps · etapa ${entry.key + 1}',
                        ),
                      ),
                    ),
              const SizedBox(height: 16),
              Text(
                '${passengers.length} passageiros',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              ...passengers.map(
                (p) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          p['full_name'],
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text('${p['boarding']} → ${p['dropoff']}'),
                        Text(
                          '${presenceLabels[p['status']]}${p['pending'] == true ? ' · aguardando envio' : ''}',
                        ),
                        if (p['status'] != 'alighted')
                          OutlinedButton(
                            onPressed:
                                canWrite &&
                                    !records.any(
                                      (r) =>
                                          r['payload']['passenger_id'] ==
                                              p['id'] &&
                                          r['status'] != 'pending',
                                    )
                                ? () => controller.enqueue(
                                    manifestId,
                                    p['id'],
                                    p['status'] == 'waiting'
                                        ? 'board'
                                        : 'disembark',
                                  )
                                : null,
                            child: Text(
                              p['status'] == 'waiting'
                                  ? 'Embarcar pela lista'
                                  : 'Registrar desembarque',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              if (records.isNotEmpty)
                Text(
                  'Envio e revisão',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ...records.map(
                (record) => Card(
                  child: ListTile(
                    title: Text(
                      passengers
                              .where(
                                (p) =>
                                    p['id'] ==
                                    record['payload']['passenger_id'],
                              )
                              .map((p) => p['full_name'])
                              .firstOrNull ??
                          'Passageiro',
                    ),
                    subtitle: Text(
                      record['status'] == 'pending'
                          ? 'Aguardando envio'
                          : record['message'] ?? 'Revise este registro',
                    ),
                    trailing: record['status'] == 'pending'
                        ? null
                        : TextButton(
                            onPressed: controller.busy
                                ? null
                                : () async {
                                    final confirm = await showDialog<bool>(
                                      context: context,
                                      builder: (context) => AlertDialog(
                                        title: const Text(
                                          'Manter informação do servidor?',
                                        ),
                                        content: const Text(
                                          'Os registros locais deste passageiro neste trecho serão descartados. Confira a presença antes de registrar novamente.',
                                        ),
                                        actions: [
                                          TextButton(
                                            onPressed: () =>
                                                Navigator.pop(context, false),
                                            child: const Text('Cancelar'),
                                          ),
                                          FilledButton(
                                            onPressed: () =>
                                                Navigator.pop(context, true),
                                            child: const Text(
                                              'Manter servidor',
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                    if (confirm == true) {
                                      await controller.acceptServer(record);
                                    }
                                  },
                            child: const Text('Revisar'),
                          ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

class ScannerPage extends StatefulWidget {
  const ScannerPage({super.key});
  @override
  State<ScannerPage> createState() => _ScannerPageState();
}

class _ScannerPageState extends State<ScannerPage> with WidgetsBindingObserver {
  final camera = MobileScannerController(
    formats: [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  bool captured = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!camera.value.hasCameraPermission) return;
    if (state == AppLifecycleState.resumed && !captured) {
      unawaited(camera.start());
    } else if (state == AppLifecycleState.inactive) {
      unawaited(camera.stop());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(camera.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Ler bilhete'),
      actions: [
        IconButton(
          tooltip: 'Lanterna',
          onPressed: camera.toggleTorch,
          icon: const Icon(Icons.flashlight_on),
        ),
      ],
    ),
    body: Column(
      children: [
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Aponte a câmera para o QR code. Você confirmará o passageiro antes de registrar.',
          ),
        ),
        Expanded(
          child: MobileScanner(
            controller: camera,
            errorBuilder: (context, error) => const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Câmera indisponível. Autorize o acesso nas configurações ou use a lista de passageiros.',
                ),
              ),
            ),
            onDetect: (result) {
              final raw = result.barcodes.firstOrNull?.rawValue;
              if (raw != null && !captured) {
                captured = true;
                unawaited(camera.stop());
                Navigator.pop(context, raw);
              }
            },
          ),
        ),
      ],
    ),
  );
}
