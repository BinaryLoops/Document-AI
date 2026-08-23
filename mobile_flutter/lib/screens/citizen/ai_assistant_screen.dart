import 'package:flutter/material.dart';

import '../../services/api_service.dart';

class _ChatMessage {
  final String text;
  final bool isUser;
  final List<dynamic> evidence;
  final double? confidence;

  _ChatMessage({required this.text, required this.isUser, this.evidence = const [], this.confidence});
}

/// Evidence-backed AI assistant (Phase 6) — every answer cites the source
/// chunk/document it was derived from, powered by the backend's Grounded RAG
/// engine (`POST /query`).
class AiAssistantScreen extends StatefulWidget {
  const AiAssistantScreen({super.key});

  @override
  State<AiAssistantScreen> createState() => _AiAssistantScreenState();
}

class _AiAssistantScreenState extends State<AiAssistantScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _sending = false;

  static const _suggestions = [
    'What is this document?',
    'Who issued it?',
    'Is it verified?',
    'What are the key dates mentioned?',
  ];

  Future<void> _send([String? preset]) async {
    final text = preset ?? _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _messages.add(_ChatMessage(text: text, isUser: true));
      _sending = true;
      _controller.clear();
    });
    _scrollToBottom();
    try {
      final result = await ApiService.instance.ragQuery(text);
      final answer = result['response']?.toString() ?? result['answer']?.toString() ?? 'No answer found.';
      final evidence = (result['evidence'] as List?) ?? (result['sources'] as List?) ?? [];
      final confidence = (result['confidence'] as num?)?.toDouble();
      setState(() {
        _messages.add(_ChatMessage(text: answer, isUser: false, evidence: evidence, confidence: confidence));
      });
    } catch (e) {
      setState(() {
        _messages.add(_ChatMessage(
            text: 'Sorry, I could not process that: ${e.toString().replaceFirst('ApiException: ', '')}',
            isUser: false));
      });
    } finally {
      setState(() => _sending = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(_scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('AI Assistant')),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _buildEmpty(context)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(14),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) => _buildBubble(context, _messages[index]),
                  ),
          ),
          if (_sending) const LinearProgressIndicator(minHeight: 2),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: const InputDecoration(hintText: 'Ask about your documents...'),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    style: IconButton.styleFrom(backgroundColor: scheme.primary),
                    onPressed: _sending ? null : () => _send(),
                    icon: const Icon(Icons.send_rounded, color: Colors.white),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmpty(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.smart_toy_rounded, size: 56, color: Theme.of(context).colorScheme.primary),
          const SizedBox(height: 12),
          const Text('Ask anything about your documents', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('Every answer includes evidence from the source document.',
              textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
          const SizedBox(height: 20),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: _suggestions
                .map((s) => ActionChip(label: Text(s), onPressed: () => _send(s)))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildBubble(BuildContext context, _ChatMessage message) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: message.isUser ? scheme.primary : scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message.text, style: TextStyle(color: message.isUser ? Colors.white : scheme.onSurface)),
            if (!message.isUser && message.evidence.isNotEmpty) ...[
              const Divider(height: 16),
              const Text('Evidence', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              ...message.evidence.take(2).map((e) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      '"${(e is Map ? (e['evidence_snippet'] ?? e['text'] ?? e['snippet']) : e).toString()}"',
                      style: const TextStyle(fontSize: 11.5, fontStyle: FontStyle.italic),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  )),
            ],
            if (!message.isUser && message.confidence != null) ...[
              const SizedBox(height: 4),
              Text('Confidence: ${(message.confidence! * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600)),
            ],
          ],
        ),
      ),
    );
  }
}
