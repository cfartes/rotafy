import 'api.dart';

bool assignedToVehicle(Json allocation, String userId) =>
    allocation['driver_id'] == userId ||
    ((allocation['drivers'] as List?) ?? []).any((p) => p['id'] == userId) ||
    ((allocation['guides'] as List?) ?? []).any((p) => p['id'] == userId);

bool driverDayVisible(Json leg, Json journey, DateTime now) {
  if (journey['status'] == 'in_progress') return true;
  final starts = DateTime.tryParse(leg['starts_at'] as String? ?? '');
  if (starts == null) return false;
  final day = now.toUtc().subtract(const Duration(hours: 3));
  final departure = starts.toUtc().subtract(const Duration(hours: 3));
  return day.year == departure.year &&
      day.month == departure.month &&
      day.day == departure.day;
}

bool canStartLeg(Json leg, DateTime now) {
  final departure = DateTime.tryParse(leg['starts_at'] as String? ?? '');
  return departure != null &&
      !now.toUtc().isBefore(
        departure.toUtc().subtract(const Duration(minutes: 30)),
      );
}
