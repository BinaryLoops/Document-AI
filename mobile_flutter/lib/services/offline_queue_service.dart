import 'dart:convert';

import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// A queued request that couldn't be sent because the device was offline.
class QueuedRequest {
  final int? id;
  final String method; // GET/POST/PUT/DELETE
  final String path; // e.g. /documents/upload
  final Map<String, dynamic>? fields; // form fields / json body
  final String? filePath; // local file to attach (multipart), if any
  final String? fileFieldName;
  final DateTime createdAt;

  QueuedRequest({
    this.id,
    required this.method,
    required this.path,
    this.fields,
    this.filePath,
    this.fileFieldName,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toMap() => {
        'id': id,
        'method': method,
        'path': path,
        'fields': fields == null ? null : jsonEncode(fields),
        'file_path': filePath,
        'file_field_name': fileFieldName,
        'created_at': createdAt.toIso8601String(),
      };

  factory QueuedRequest.fromMap(Map<String, dynamic> map) => QueuedRequest(
        id: map['id'] as int?,
        method: map['method'] as String,
        path: map['path'] as String,
        fields: map['fields'] == null
            ? null
            : jsonDecode(map['fields'] as String) as Map<String, dynamic>,
        filePath: map['file_path'] as String?,
        fileFieldName: map['file_field_name'] as String?,
        createdAt: DateTime.parse(map['created_at'] as String),
      );
}

/// Persists API requests made while offline (e.g. a document scan/upload)
/// so they can be replayed automatically once connectivity returns.
class OfflineQueueService {
  OfflineQueueService._internal();
  static final OfflineQueueService instance = OfflineQueueService._internal();

  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final dir = await getApplicationDocumentsDirectory();
    final path = p.join(dir.path, 'offline_queue.db');
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            fields TEXT,
            file_path TEXT,
            file_field_name TEXT,
            created_at TEXT NOT NULL
          )
        ''');
      },
    );
    return _db!;
  }

  Future<int> enqueue(QueuedRequest request) async {
    final db = await _database;
    return db.insert('queue', request.toMap()..remove('id'));
  }

  Future<List<QueuedRequest>> pending() async {
    final db = await _database;
    final rows = await db.query('queue', orderBy: 'created_at ASC');
    return rows.map(QueuedRequest.fromMap).toList();
  }

  Future<void> remove(int id) async {
    final db = await _database;
    await db.delete('queue', where: 'id = ?', whereArgs: [id]);
  }

  Future<int> count() async {
    final db = await _database;
    final result = await db.rawQuery('SELECT COUNT(*) as c FROM queue');
    return Sqflite.firstIntValue(result) ?? 0;
  }
}
