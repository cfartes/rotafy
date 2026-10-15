import 'api.dart';

bool assignedToVehicle(Json allocation, String userId) =>
    allocation['driver_id'] == userId ||
    ((allocation['drivers'] as List?) ?? []).any((p) => p['id'] == userId) ||
    ((allocation['guides'] as List?) ?? []).any((p) => p['id'] == userId);
