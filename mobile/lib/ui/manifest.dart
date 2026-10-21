import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/controller.dart';
import '../core/offline.dart';
import '../core/tracking.dart';

const presenceLabels = {
  'waiting': 'Aguardando embarque',
  'onboard': 'A bordo',
  'alighted': 'Desembarcado',
};

class ManifestPage extends StatefulWidget {
  final OperationController controller;
  final String manifestId;
  const ManifestPage({
    super.key,
    required this.controller,
    required this.manifestId,
  });
  @override
  State<ManifestPage> createState() => _ManifestPageState();
}

class _ManifestPageState extends State<ManifestPage> {
  OperationController get controller => widget.controller;
  String get manifestId => widget.manifestId;
  String filter = 'all';
  bool listOpen = true;
  String? trackingNotice;

  Future<void> tracking() async {
    if (!await confirm(
      'Compartilhar localização do veículo?',
      'Este celular será o responsável por este veículo. O GPS será coletado a cada 5 minutos durante o trecho, inclusive com a tela bloqueada, com notificação visível. Permaneça no veículo. O administrador poderá acompanhar o percurso e enviar avisos de proximidade aos passageiros.',
      'Assumir rastreamento',
    )) {
      return;
    }
    try {
      final snapshot = await controller.store.snapshot(manifestId);
      try {
        await VehicleTracking.start(
          controller.api,
          controller.store,
          Json.from(snapshot),
        );
      } on ApiFailure catch (e) {
        if (e.status != 409 || !e.message.contains('Outro aparelho')) rethrow;
        if (!await confirm(
          'Transferir rastreamento?',
          'Outro celular está responsável. Ao assumir, o rastreamento anterior será encerrado.',
          'Transferir para este celular',
        )) {
          return;
        }
        await VehicleTracking.start(
          controller.api,
          controller.store,
          Json.from(snapshot),
          takeover: true,
        );
      }
      if (mounted) {
        setState(
          () => trackingNotice = 'Rastreamento iniciado neste celular. A coleta para ao encerrar o trecho ou interromper o compartilhamento.',
        );
      }
    } catch (e) {
      if (mounted) setState(() => trackingNotice = e.toString());
    }
  }

  Future<bool> confirm(String title, String description, String action) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(description),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(action),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> journey(String status) async {
    final start = status == 'in_progress';
    if (await confirm(
      start ? 'Iniciar viagem?' : 'Fechar viagem neste trecho?',
      start
          ? 'Registrar a saída deste veículo e trecho. É necessário estar conectado.'
          : 'Registrar a chegada deste veículo ao destino e tentar capturar sua localização. Autorize o GPS quando solicitado. Se estiver indisponível, a chegada será registrada sem coordenadas. Os passageiros devem estar desembarcados e os registros sincronizados. Outros veículos e a volta continuam independentes.',
      start ? 'Iniciar viagem' : 'Confirmar chegada',
    )) {
      if (await controller.changeJourney(manifestId, status) &&
          mounted &&
          !controller.prepared.any((s) => s['id'] == manifestId)) {
        Navigator.pop(context);
      }
    }
  }

  Future<void> disembark(int count) async {
    if (await confirm(
      'Desembarcar todos?',
      'Registrar o desembarque de $count passageiros a bordo deste veículo e trecho. Quem não embarcou permanece aguardando.',
      'Desembarcar todos',
    )) {
      if (await controller.disembarkAll(manifestId) && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Desembarques registrados no celular. Sincronize para confirmar no sistema.',
            ),
          ),
        );
      }
    }
  }

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
      final visible = passengers
          .where((person) => filter == 'all' || person['status'] == filter)
          .toList();
      final onboard = passengers
          .where((person) => person['status'] == 'onboard')
          .length;
      final waiting = passengers
          .where((person) => person['status'] == 'waiting')
          .length;
      final journeyStatus = data['journey']?['status'] ?? 'scheduled';
      final canOperate = data['can_write'] == true && !controller.busy;
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
              Text(
                'Trecho: ${journeyStatus == 'scheduled'
                    ? 'Não iniciado'
                    : journeyStatus == 'in_progress'
                    ? 'Em viagem'
                    : 'Chegada registrada'}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (journeyStatus == 'scheduled')
                FilledButton.icon(
                  onPressed: canOperate && records.isEmpty
                      ? () => journey('in_progress')
                      : null,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Iniciar viagem'),
                ),
              if (journeyStatus == 'in_progress')
                OutlinedButton.icon(
                  onPressed: canOperate ? tracking : null,
                  icon: const Icon(Icons.my_location),
                  label: const Text('Assumir rastreamento deste veículo'),
                ),
              if (journeyStatus == 'in_progress')
                TextButton(
                  onPressed: () async {
                    await VehicleTracking.stop();
                    if (mounted) {
                      setState(
                        () => trackingNotice =
                            'Compartilhamento interrompido neste celular.',
                      );
                    }
                  },
                  child: const Text('Interromper rastreamento neste celular'),
                ),
              if (trackingNotice != null) Text(trackingNotice!),
              if (journeyStatus == 'in_progress')
                FilledButton.icon(
                  onPressed: canOperate && records.isEmpty && onboard == 0
                      ? () => journey('completed')
                      : null,
                  icon: const Icon(Icons.flag),
                  label: const Text('Fechar viagem · chegada no destino'),
                ),
              if (journeyStatus != 'completed' &&
                  (records.isNotEmpty || onboard > 0))
                const Text(
                  'Desembarque os passageiros a bordo e sincronize os registros antes de fechar a chegada.',
                ),
              OutlinedButton.icon(
                onPressed: canWrite && onboard > 0
                    ? () => disembark(onboard)
                    : null,
                icon: const Icon(Icons.groups),
                label: Text('Desembarcar todos · $onboard a bordo'),
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
              if (route.isNotEmpty)
                ...((route.first['points'] as List?) ?? []).map(
                  (point) => Card(
                    child: ListTile(
                      title: Text('${point['position'] + 1}. ${point['name']}'),
                      subtitle: Text(
                        [
                          point['address'] ?? '',
                          point['complement'] ?? '',
                          if ((point['passenger_names'] as List? ?? [])
                              .isNotEmpty)
                            'Passageiros: ${(point['passenger_names'] as List).join(', ')}',
                          if ((point['pending_passenger_names'] as List? ?? [])
                              .isNotEmpty)
                            'Reservas temporárias: ${(point['pending_passenger_names'] as List).join(', ')}',
                        ].where((line) => line.isNotEmpty).join('\n'),
                      ),
                      trailing: IconButton(
                        icon: const Icon(Icons.directions),
                        tooltip: 'Navegar até este ponto',
                        onPressed: () => openMaps(context, point['maps_url']),
                      ),
                    ),
                  ),
                ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${passengers.length} passageiros'),
                subtitle: Text('$waiting não embarcados · $onboard a bordo'),
                trailing: IconButton(
                  tooltip: listOpen
                      ? 'Recolher passageiros'
                      : 'Expandir passageiros',
                  onPressed: () => setState(() {
                    listOpen = !listOpen;
                  }),
                  icon: Icon(listOpen ? Icons.expand_less : Icons.expand_more),
                ),
              ),
              if (listOpen) ...[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final option in [
                      ('all', 'Todos'),
                      ('waiting', 'Não embarcados'),
                      ('onboard', 'Embarcados'),
                    ])
                      ChoiceChip(
                        label: Text(option.$2),
                        selected: filter == option.$1,
                        onSelected: (_) => setState(() {
                          filter = option.$1;
                        }),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                if (visible.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Nenhum passageiro neste filtro.'),
                  ),
                ...visible.map(
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
              ],
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
