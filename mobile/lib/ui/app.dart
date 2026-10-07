import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/controller.dart';
import 'manifest.dart';

class RotafyApp extends StatelessWidget {
  final OperationController controller;
  const RotafyApp({super.key, required this.controller});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: AppConfig.name,
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff087f78)),
      useMaterial3: true,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      scaffoldBackgroundColor: const Color(0xfff4f7fa),
    ),
    home: AnimatedBuilder(
      animation: controller,
      builder: (context, _) => controller.user == null
          ? Scaffold(
              appBar: AppBar(title: const Text(AppConfig.name)),
              body: SafeArea(
                child: SingleChildScrollView(
                  child: LoginForm(controller: controller),
                ),
              ),
            )
          : HomePage(
              key: ValueKey(controller.store.owner(controller.user!)),
              controller: controller,
            ),
    ),
  );
}

class LoginForm extends StatefulWidget {
  final OperationController controller;
  final VoidCallback? onSuccess;
  const LoginForm({super.key, required this.controller, this.onSuccess});
  @override
  State<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<LoginForm> {
  final form = GlobalKey<FormState>();
  final company = TextEditingController(text: AppConfig.company);
  final email = TextEditingController();
  final password = TextEditingController();
  bool loading = false;
  String? error;
  @override
  void dispose() {
    company.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      loading = true;
      error = null;
    });
    final ok = await widget.controller.login(
      company.text.trim(),
      email.text,
      password.text,
    );
    if (!mounted) return;
    setState(() {
      loading = false;
      error = widget.controller.error;
    });
    if (ok) widget.onSuccess?.call();
  }

  String? requiredValue(String? value) =>
      value == null || value.trim().isEmpty ? 'Preencha este campo.' : null;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: Form(
      key: form,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.directions_bus_rounded, size: 60),
          const SizedBox(height: 16),
          Text(
            'Pronto para a viagem',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const Text(
            'Acesso de motorista e guia. Prepare os trechos enquanto houver internet.',
          ),
          const SizedBox(height: 24),
          TextFormField(
            controller: company,
            readOnly: AppConfig.company.isNotEmpty,
            decoration: const InputDecoration(labelText: 'Empresa'),
            validator: requiredValue,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: email,
            keyboardType: TextInputType.emailAddress,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'E-mail'),
            validator: requiredValue,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: password,
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            decoration: const InputDecoration(labelText: 'Senha'),
            validator: requiredValue,
            onFieldSubmitted: (_) {
              if (!loading) unawaited(submit());
            },
          ),
          const SizedBox(height: 16),
          if (error != null)
            Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          FilledButton(
            onPressed: loading ? null : submit,
            child: Text(loading ? 'Entrando…' : 'Entrar'),
          ),
        ],
      ),
    ),
  );
}

class HomePage extends StatefulWidget {
  final OperationController controller;
  const HomePage({super.key, required this.controller});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  Timer? timer;
  List<Json> trips = [];
  String? error;
  bool loading = false;
  bool foreground = true;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    timer = Timer.periodic(const Duration(seconds: 15), (_) {
      final c = widget.controller;
      if (foreground &&
          !c.busy &&
          c.records.any((r) => r['status'] == 'pending')) {
        unawaited(c.synchronize());
      }
    });
    unawaited(loadTrips());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground &&
        widget.controller.records.isNotEmpty &&
        !widget.controller.busy) {
      unawaited(widget.controller.synchronize());
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> loadTrips() async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final data = await widget.controller.trips();
      if (mounted) setState(() => trips = data);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    return Scaffold(
      appBar: AppBar(
        title: const Text(AppConfig.name),
        actions: [
          IconButton(
            tooltip: 'Renovar acesso',
            icon: const Icon(Icons.lock_reset),
            onPressed: c.busy
                ? null
                : () => showDialog(
                    context: context,
                    builder: (context) => Dialog(
                      child: SingleChildScrollView(
                        child: LoginForm(
                          controller: c,
                          onSuccess: () => Navigator.pop(context),
                        ),
                      ),
                    ),
                  ),
          ),
          IconButton(
            tooltip: 'Sair',
            onPressed: c.busy ? null : c.logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              c.user!['full_name'],
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(c.user!['role'] == 'driver' ? 'Motorista' : 'Guia'),
            if (c.busy) const LinearProgressIndicator(),
            if (c.error != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(c.error!),
                ),
              ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      '${c.records.length} registros aguardando envio ou revisão',
                    ),
                    FilledButton.icon(
                      onPressed: c.busy ? null : c.synchronize,
                      icon: const Icon(Icons.sync),
                      label: const Text('Sincronizar agora'),
                    ),
                    const Text(
                      'Os registros só ficam confirmados após resposta do servidor. A sincronização automática funciona enquanto o app está aberto.',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Trechos preparados',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (c.prepared.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  'Nenhum trecho preparado. Carregue suas viagens com conexão.',
                ),
              ),
            ...c.prepared.map(
              (s) => Card(
                child: ListTile(
                  leading: const Icon(Icons.offline_pin),
                  title: Text(s['data']['trip']['name']),
                  subtitle: Text(
                    c.closedSnapshot(s)
                        ? 'Viagem encerrada · registros pendentes de revisão'
                        : '${s['data']['vehicle']['name']} · ${s['data']['leg']['origin']} → ${s['data']['leg']['destination']}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          ManifestPage(controller: c, manifestId: s['id']),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Minhas viagens',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  tooltip: 'Atualizar viagens',
                  onPressed: loading ? null : loadTrips,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            if (loading) const LinearProgressIndicator(),
            if (error != null) Text(error!),
            ...trips
                .where((trip) => !c.closedTrips.contains(trip['id']))
                .map((trip) => TripCard(controller: c, trip: trip)),
          ],
        ),
      ),
    );
  }
}

class TripCard extends StatefulWidget {
  final OperationController controller;
  final Json trip;
  const TripCard({super.key, required this.controller, required this.trip});
  @override
  State<TripCard> createState() => _TripCardState();
}

class _TripCardState extends State<TripCard> {
  Json? detail;
  String? error;
  Future<void> load() async {
    try {
      final data = await widget.controller.trip(widget.trip['id']);
      if (mounted) {
        setState(() {
          detail = data;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      title: Text(widget.trip['name']),
      subtitle: Text(widget.trip['destination']),
      onExpansionChanged: (expanded) {
        if (expanded) unawaited(load());
      },
      children: [
        if (error != null)
          Padding(padding: const EdgeInsets.all(16), child: Text(error!)),
        if (detail == null && error == null)
          const Padding(
            padding: EdgeInsets.all(16),
            child: CircularProgressIndicator(),
          ),
        if (detail != null)
          ...(detail!['vehicles'] as List)
              .where(
                (v) =>
                    v['driver_id'] == widget.controller.user!['id'] ||
                    (v['guides'] as List).any(
                      (g) => g['id'] == widget.controller.user!['id'],
                    ),
              )
              .expand(
                (v) => (detail!['legs'] as List).map(
                  (leg) => ListTile(
                    title: Text(
                      '${v['name']} · ${leg['position'] == 1 ? 'Ida' : 'Volta'}',
                    ),
                    subtitle: Text('${leg['origin']} → ${leg['destination']}'),
                    trailing: FilledButton(
                      onPressed: widget.controller.busy
                          ? null
                          : () async {
                              if (await widget.controller.prepare(
                                    detail!,
                                    Json.from(v),
                                    Json.from(leg),
                                  ) &&
                                  context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'Trecho preparado para uso offline.',
                                    ),
                                  ),
                                );
                              }
                            },
                      child: const Text('Preparar'),
                    ),
                  ),
                ),
              ),
      ],
    ),
  );
}
