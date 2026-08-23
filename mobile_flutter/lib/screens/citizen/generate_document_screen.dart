import 'package:flutter/material.dart';

import '../../core/constants.dart';
import 'generate_document_form_screen.dart';

/// Phase 8 — pick which government document to request. The actual
/// generation (approval -> official template -> digital signature -> QR ->
/// PDF) happens on the Issuing Authority side; this starts the request.
class GenerateDocumentScreen extends StatelessWidget {
  const GenerateDocumentScreen({super.key});

  static const _types = GovDocumentType.values;

  static const _icons = {
    GovDocumentType.passport: Icons.badge_rounded,
    GovDocumentType.license: Icons.directions_car_rounded,
    GovDocumentType.birth: Icons.child_care_rounded,
    GovDocumentType.income: Icons.receipt_long_rounded,
    GovDocumentType.land: Icons.landscape_rounded,
  };

  static const _descriptions = {
    GovDocumentType.passport: 'International travel document issued by the Passport Office.',
    GovDocumentType.license: 'Driving licence issued by the Regional Transport Office (RTO).',
    GovDocumentType.birth: 'Birth certificate issued by the Registrar.',
    GovDocumentType.income: 'Income certificate issued by the Revenue Department.',
    GovDocumentType.land: 'Land ownership record issued by the Revenue Department.',
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Generate Government Document')),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _types.length,
        itemBuilder: (context, index) {
          final type = _types[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: ListTile(
              contentPadding: const EdgeInsets.all(14),
              leading: CircleAvatar(
                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                child: Icon(_icons[type]),
              ),
              title: Text(type.displayName, style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(_descriptions[type] ?? ''),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => Navigator.of(context)
                  .push(MaterialPageRoute(builder: (_) => GenerateDocumentFormScreen(docType: type))),
            ),
          );
        },
      ),
    );
  }
}
