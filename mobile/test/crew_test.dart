import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_rotafy/core/crew.dart';

void main() {
  test(
    'driver sees only Brazilian operational day and ongoing overnight leg',
    () {
      final now = DateTime.parse('2027-01-10T02:59:00Z');
      final leg = {'starts_at': '2027-01-10T08:00:00-03:00'};
      expect(driverDayVisible(leg, {}, now), isFalse);
      expect(
        driverDayVisible(leg, {}, now.add(const Duration(minutes: 1))),
        isTrue,
      );
      expect(
        driverDayVisible(leg, {
          'status': 'in_progress',
        }, now.add(const Duration(days: 3))),
        isTrue,
      );
    },
  );
  test('start gate unlocks at exactly thirty minutes and fails closed without date', () {
    final departure = DateTime.parse('2027-01-10T08:00:00-03:00');
    final leg = {'starts_at': departure.toIso8601String()};
    expect(
      canStartLeg(leg, departure.subtract(const Duration(minutes: 31))),
      isFalse,
    );
    expect(
      canStartLeg(leg, departure.subtract(const Duration(minutes: 30))),
      isTrue,
    );
    expect(canStartLeg({}, departure), isFalse);
  });
  test('both drivers and both guides can open their assigned vehicle', () {
    final allocation = {
      'driver_id': 'd1',
      'drivers': [
        {'id': 'd1'},
        {'id': 'd2'},
      ],
      'guides': [
        {'id': 'g1'},
        {'id': 'g2'},
      ],
    };
    for (final id in ['d1', 'd2', 'g1', 'g2']) {
      expect(assignedToVehicle(allocation, id), isTrue);
    }
    expect(assignedToVehicle(allocation, 'other'), isFalse);
  });
  test('legacy allocation with a single driver remains compatible', () {
    expect(assignedToVehicle({'driver_id': 'd1'}, 'd1'), isTrue);
    expect(assignedToVehicle({'driver_id': 'd1'}, 'd2'), isFalse);
  });
}
