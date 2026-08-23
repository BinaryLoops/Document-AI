import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';

/// Thin wrapper around connectivity_plus exposing a simple online/offline
/// stream + snapshot used to drive UI banners and the offline request queue.
class ConnectivityService extends ChangeNotifier {
  ConnectivityService._internal() {
    _sub = Connectivity().onConnectivityChanged.listen(_update);
    Connectivity().checkConnectivity().then(_update);
  }
  static final ConnectivityService instance = ConnectivityService._internal();

  bool _isOnline = true;
  bool get isOnline => _isOnline;

  late final StreamSubscription<List<ConnectivityResult>> _sub;
  final StreamController<bool> _controller = StreamController<bool>.broadcast();
  Stream<bool> get onStatusChange => _controller.stream;

  void _update(List<ConnectivityResult> results) {
    final online = results.any((r) => r != ConnectivityResult.none);
    if (online != _isOnline) {
      _isOnline = online;
      _controller.add(online);
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _sub.cancel();
    _controller.close();
    super.dispose();
  }
}
