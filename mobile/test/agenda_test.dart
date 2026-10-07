import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_rotafy/core/api.dart';
import 'package:nexus_rotafy/ui/agenda.dart';

void main() {
  final now = DateTime(2026, 10, 7, 10);
  Json trip(String id, DateTime starts, {String status = 'scheduled'}) => {
    'id': id,
    'name': id,
    'starts_at': starts.toUtc().toIso8601String(),
    'status': status,
    'destination': 'Maragogi',
  };

  test(
    'agenda sorts next seven calendar days and excludes past and closed trips',
    () {
      final items = [
        trip('late', DateTime(2026, 10, 13, 23, 59)),
        trip('today', now),
        trip('past', now.subtract(const Duration(minutes: 1))),
        trip('outside', DateTime(2026, 10, 14)),
        trip('closed', now, status: 'completed'),
        trip('cancelled', now, status: 'cancelled'),
        trip('tomorrow', DateTime(2026, 10, 8, 8)),
        {'id': 'invalid', 'starts_at': 'invalid', 'status': 'scheduled'},
      ];
      expect(upcomingTrips(items, now).map((t) => t['id']), [
        'today',
        'tomorrow',
        'late',
      ]);
    },
  );

  testWidgets('agenda shows date, departure time and destination', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AgendaList(
            trips: [trip('Transfer aeroporto', DateTime(2026, 10, 8, 14, 30))],
            now: now,
          ),
        ),
      ),
    );
    expect(find.text('Transfer aeroporto'), findsOneWidget);
    expect(find.textContaining('08/10/2026'), findsOneWidget);
    expect(find.textContaining('14:30'), findsOneWidget);
    expect(find.textContaining('Destino: Maragogi'), findsOneWidget);
  });

  test('package already started still shows upcoming assigned stages', () {
    final package =
        trip(
            'Circuito SC',
            now.subtract(const Duration(days: 2)),
            status: 'in_progress',
          )
          ..['mode'] = 'multi_destination'
          ..['agenda_legs'] = [
            {
              'id': 'old',
              'position': 1,
              'starts_at': now
                  .subtract(const Duration(days: 2))
                  .toIso8601String(),
              'destination': 'Destino anterior',
              'completed': true,
            },
            {
              'id': 'next',
              'position': 3,
              'starts_at': now.add(const Duration(days: 1)).toIso8601String(),
              'destination': 'Urubici',
              'completed': false,
            },
            {
              'id': 'done',
              'position': 4,
              'starts_at': now.add(const Duration(days: 2)).toIso8601String(),
              'destination': 'Concluído',
              'completed': true,
            },
          ];
    final result = upcomingTrips([package], now);
    expect(result, hasLength(1));
    expect(result.single['leg_id'], 'next');
    expect(result.single['destination'], 'Urubici');
    expect(result.single['name'], 'Circuito SC · Deslocamento 3');
  });

  testWidgets('empty agenda explains seven day period', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AgendaList(trips: [], now: now),
        ),
      ),
    );
    expect(
      find.text('Nenhuma viagem prevista para os próximos 7 dias.'),
      findsOneWidget,
    );
    expect(find.textContaining('07/10/2026 a 13/10/2026'), findsOneWidget);
  });
}
