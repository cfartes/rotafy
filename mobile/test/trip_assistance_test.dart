import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_rotafy/core/trip_assistance.dart';
import 'package:nexus_rotafy/core/offline.dart';
import 'package:nexus_rotafy/core/api.dart';

void main() {
  final points = [
    {
      'name': 'Hotel',
      'boarding_passenger_ids': ['a', 'b'],
      'dropoff_passenger_ids': [],
    },
    {
      'name': 'Terminal',
      'boarding_passenger_ids': [],
      'dropoff_passenger_ids': ['a', 'b'],
    },
  ];
  List<Json> people(String a, String b) => [
    {'id': 'a', 'full_name': 'Mesmo nome', 'status': a, 'version': 0},
    {'id': 'b', 'full_name': 'Mesmo nome', 'status': b, 'version': 0},
  ];
  test('next stop uses IDs and route order, including pickup and dropoff at one point', () {
    var next = nextServicePoint(points, people('onboard', 'waiting'))!;
    expect(next['name'], 'Hotel');
    expect((next['pickup'] as List).single['id'], 'b');
    next = nextServicePoint(points, people('onboard', 'onboard'))!;
    expect(next['name'], 'Terminal');
    expect(next['delivery'], hasLength(2));
    final both = nextServicePoint([
      {
        'boarding_passenger_ids': ['a'],
        'dropoff_passenger_ids': ['b'],
      },
    ], people('waiting', 'onboard'))!;
    expect(both['pickup'], hasLength(1));
    expect(both['delivery'], hasLength(1));
  });
  test('offline boarding advances stop and completed or unknown passengers do not create work', () {
    final passengers = projectPassengers(
      {'passengers': people('waiting', 'alighted')},
      [
        {
          'status': 'pending',
          'payload': {
            'passenger_id': 'a',
            'expected_version': 0,
            'action': 'board',
          },
        },
      ],
    );
    expect(nextServicePoint(points, passengers)!['name'], 'Terminal');
    expect(nextServicePoint(points, people('alighted', 'alighted')), isNull);
    expect(
      nextServicePoint([
        {
          'boarding_passenger_ids': ['unknown'],
        },
      ], passengers),
      isNull,
    );
    expect(
      nextServicePoint([
        {'name': 'Old route'},
      ], passengers),
      isNull,
    );
    expect(nextServicePoint([], passengers), isNull);
  });
  final now = DateTime.utc(2026, 11, 13, 12);
  final endpoint = '/trips/t/vehicles/v/legs/l';
  int at(int secondsAgo) =>
      now.subtract(Duration(seconds: secondsAgo)).millisecondsSinceEpoch;
  Json health({int captured = 20, int sent = 30, int started = 600}) => {
    'active': true,
    'endpoint': endpoint,
    'started_at': at(started),
    'last_captured_at': at(captured),
    'last_sent_at': at(sent),
    'message': 'Recebido.',
  };
  test('tracking distinguishes stopped, unavailable and another leg', () {
    expect(trackingFeedback(null, endpoint, now).warning, isTrue);
    expect(
      trackingFeedback(
        {'active': false, 'last_sent_at': at(10)},
        endpoint,
        now,
      ).title,
      'Rastreamento parado',
    );
    expect(
      trackingFeedback(health()..['endpoint'] = 'another', endpoint, now).title,
      'Outro trecho em rastreamento',
    );
    expect(trackingFeedback(health(), endpoint, now).warning, isFalse);
  });
  test(
    'three minutes separates stale GPS from missing server acknowledgment',
    () {
      expect(
        trackingFeedback(health(captured: 180), endpoint, now).title,
        'GPS sem posição recente',
      );
      expect(
        trackingFeedback(health(sent: 180), endpoint, now).title,
        'Localização sem envio confirmado',
      );
      expect(
        trackingFeedback(
          health(sent: 179, captured: 179),
          endpoint,
          now,
        ).warning,
        isFalse,
      );
      expect(
        trackingFeedback(
          health(started: 10)
            ..['last_sent_at'] = 0
            ..['last_captured_at'] = 0,
          endpoint,
          now,
        ).title,
        'Aguardando localização',
      );
      expect(
        trackingFeedback(
          health()
            ..['last_sent_at'] = 0
            ..['last_captured_at'] = 0,
          endpoint,
          now,
        ).title,
        'GPS sem posição recente',
      );
      expect(
        trackingFeedback(
          health(captured: -10, sent: -10),
          endpoint,
          now,
        ).warning,
        isFalse,
      );
    },
  );
  test('missing timestamps do not invent a stale GPS alert; execution time is explicit', () {
    expect(
      trackingFeedback(
        {'active': true, 'message': 'Aguardando'},
        endpoint,
        now,
      ).warning,
      isFalse,
    );
    expect(executionTime('invalid'), 'Não informado');
    expect(executionTime(null), 'Não informado');
    expect(executionTime('2026-11-13T12:00:00'), '13/11/2026 às 12:00');
  });
}
