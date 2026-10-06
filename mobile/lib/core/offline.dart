import 'dart:convert';

import 'package:crypto/crypto.dart';

import 'api.dart';

String? nextPresence(String status, String action) => {
  'waiting:board': 'onboard',
  'onboard:disembark': 'alighted',
}['$status:$action'];

List<Json> projectPassengers(Json snapshot, List<Json> queue) {
  return (snapshot['passengers'] as List).map((raw) {
    final p = Json.from(raw);
    for (final record in queue.where(
      (q) => q['payload']['passenger_id'] == p['id'],
    )) {
      final command = record['payload'];
      if (record['status'] != 'pending' ||
          command['expected_version'] != p['version']) {
        break;
      }
      final next = nextPresence(p['status'], command['action']);
      if (next == null) break;
      p.addAll({
        'status': next,
        'version': (p['version'] as int) + 1,
        'pending': true,
      });
    }
    return p;
  }).toList();
}

Json matchTicket(Json snapshot, String raw, Uri webOrigin, DateTime now) {
  if (!DateTime.parse(snapshot['expires_at']).isAfter(now)) {
    throw StateError('Manifesto vencido. Conecte-se para preparar novamente.');
  }
  var token = raw.trim();
  final url = Uri.tryParse(token);
  if (url != null && url.hasAuthority) {
    if (url.origin != webOrigin.origin || url.path != '/bilhete') {
      throw StateError('Link de bilhete inválido.');
    }
    token = Uri.splitQueryString(url.fragment)['token'] ?? '';
  }
  final company = RegExp.escape(snapshot['operator']['company_id']);
  if (!RegExp('^bt\\.$company\\.[A-Za-z0-9_-]{43}\$').hasMatch(token)) {
    throw StateError('Bilhete inválido ou de outra empresa.');
  }
  final hash = sha256.convert(utf8.encode(token)).toString();
  final tickets = (snapshot['tickets'] as List).where(
    (t) => t['token_hash'] == hash,
  );
  if (tickets.isEmpty) {
    throw StateError(
      'Bilhete não pertence a este veículo e trecho preparados.',
    );
  }
  return {'passenger_id': tickets.first['passenger_id'], 'token': token};
}
