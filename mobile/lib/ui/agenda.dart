import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/controller.dart';

List<Json> upcomingTrips(List<Json> trips, DateTime now) {
  final local = now.toLocal();
  final end = DateTime(local.year, local.month, local.day + 7);
  final expanded = trips.expand<Json>((trip) {
    final legs = trip['agenda_legs'] as List?;
    if (legs == null) return [trip];
    return legs
        .where((leg) => leg['completed'] != true)
        .map(
          (leg) => {
            ...trip,
            'leg_id': leg['id'],
            'starts_at': leg['starts_at'],
            'destination': leg['destination'],
            'name': trip['mode'] == 'multi_destination'
                ? '${trip['name']} · Deslocamento ${leg['position']}'
                : '${trip['name']} · ${leg['position'] == 1 ? 'Ida' : 'Volta'}',
          },
        );
  });
  final result = expanded.where((trip) {
    final starts = DateTime.tryParse(trip['starts_at'] as String? ?? '')
        ?.toLocal();
    return starts != null &&
        !starts.isBefore(local) &&
        starts.isBefore(end) &&
        ['scheduled', 'in_progress'].contains(trip['status']);
  }).toList();
  result.sort(
    (a, b) =>
        DateTime.parse(a['starts_at'])
            .compareTo(DateTime.parse(b['starts_at'])),
  );
  return result;
}

String agendaDate(DateTime date) =>
    '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';

String agendaTime(DateTime date) =>
    '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';

class AgendaList extends StatelessWidget {
  final List<Json> trips;
  final DateTime now;
  const AgendaList({super.key, required this.trips, required this.now});

  @override
  Widget build(BuildContext context) {
    final items = upcomingTrips(trips, now);
    final local = now.toLocal();
    final last = DateTime(local.year, local.month, local.day + 6);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Próximos 7 dias',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        Text('${agendaDate(local)} a ${agendaDate(last)} · horário do celular'),
        const SizedBox(height: 16),
        if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text('Nenhuma viagem prevista para os próximos 7 dias.'),
          ),
        for (final trip in items)
          Card(
            child: ListTile(
              leading: const Icon(Icons.event),
              title: Text(trip['name']),
              subtitle: Text(
                '${agendaDate(DateTime.parse(trip['starts_at']).toLocal())} · '
                '${agendaTime(DateTime.parse(trip['starts_at']).toLocal())}\n'
                'Destino: ${trip['destination']}',
              ),
              isThreeLine: true,
            ),
          ),
      ],
    );
  }
}

class AgendaPage extends StatefulWidget {
  final OperationController controller;
  const AgendaPage({super.key, required this.controller});
  @override
  State<AgendaPage> createState() => _AgendaPageState();
}

class _AgendaPageState extends State<AgendaPage> {
  List<Json> trips = [];
  bool loading = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.controller.trips();
      if (mounted) setState(() => trips = result);
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Não foi possível atualizar a agenda. Confira sua conexão e tente novamente.',
        );
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Agenda'),
      actions: [
        IconButton(
          tooltip: 'Atualizar agenda',
          onPressed: loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(
      child: Column(
        children: [
          if (loading) const LinearProgressIndicator(),
          if (error != null)
            Padding(padding: const EdgeInsets.all(16), child: Text(error!)),
          Expanded(
            child: AnimatedBuilder(
              animation: widget.controller,
              builder: (context, _) => AgendaList(
                trips: trips
                    .where(
                      (t) => !widget.controller.closedTrips.contains(t['id']),
                    )
                    .toList(),
                now: DateTime.now(),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
