import 'api.dart';

/// Uses passenger IDs, never names or GPS guesses, to advance the itinerary.
Json? nextServicePoint(List points, List<Json> passengers) {
  for (final raw in points) {
    final point = Json.from(raw);
    final boarding = (point['boarding_passenger_ids'] as List? ?? []).toSet();
    final dropoff = (point['dropoff_passenger_ids'] as List? ?? []).toSet();
    final pickup = passengers
        .where((p) => p['status'] == 'waiting' && boarding.contains(p['id']))
        .toList();
    final delivery = passengers
        .where((p) => p['status'] == 'onboard' && dropoff.contains(p['id']))
        .toList();
    if (pickup.isNotEmpty || delivery.isNotEmpty) {
      return {...point, 'pickup': pickup, 'delivery': delivery};
    }
  }
  return null;
}

({String title, String message, bool warning}) trackingFeedback(
  Json? health,
  String endpoint,
  DateTime now,
) {
  if (health == null) {
    return (
      title: 'Estado não confirmado',
      message: 'Não foi possível consultar o serviço de localização neste celular. Confira a notificação do Android.',
      warning: true,
    );
  }
  if (health['active'] != true) {
    return (
      title: 'Rastreamento parado',
      message: 'Este celular não está compartilhando localização. Outro aparelho pode estar responsável pelo veículo.',
      warning: true,
    );
  }
  if (health['endpoint'] != null && health['endpoint'] != endpoint) {
    return (
      title: 'Outro trecho em rastreamento',
      message: 'O serviço deste celular pertence a outro trecho. Assuma o rastreamento para transferir a responsabilidade.',
      warning: true,
    );
  }
  final started = (health['started_at'] as num? ?? 0).toInt();
  final sent = (health['last_sent_at'] as num? ?? 0).toInt();
  final captured = (health['last_captured_at'] as num? ?? 0).toInt();
  bool stale(int timestamp) =>
      timestamp > 0 &&
      now.millisecondsSinceEpoch - timestamp >=
          const Duration(minutes: 3).inMilliseconds;
  if (stale(captured > 0 ? captured : started)) {
    return (
      title: 'GPS sem posição recente',
      message: 'Há pelo menos 3 minutos sem uma posição recente. Confira a localização e o sinal de GPS do aparelho.',
      warning: true,
    );
  }
  if (stale(sent > 0 ? sent : started)) {
    return (
      title: 'Localização sem envio confirmado',
      message: 'Há pelo menos 3 minutos sem confirmação de envio ao servidor. Confira a conexão. As tentativas continuam enquanto o serviço estiver ativo.',
      warning: true,
    );
  }
  return (
    title: sent > 0
        ? 'Envio de localização confirmado'
        : 'Aguardando localização',
    message:
        health['message'] as String? ??
        'O serviço está ativo. Aguardando confirmação do próximo envio.',
    warning: false,
  );
}

String executionTime(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return 'Não informado';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(date.day)}/${two(date.month)}/${date.year} às ${two(date.hour)}:${two(date.minute)}';
}
