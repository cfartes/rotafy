import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_rotafy/core/crew.dart';

void main() {
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
