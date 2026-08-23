/// Knowledge graph node/edge, matching `/graph/export` D3.js-compatible JSON.
class GraphNode {
  final String id;
  final String label;
  final String type; // Citizen | Officer | Department | Document | Case | Institution
  final Map<String, dynamic> properties;

  GraphNode({required this.id, required this.label, required this.type, this.properties = const {}});

  factory GraphNode.fromJson(Map<String, dynamic> json) => GraphNode(
        id: (json['id'] ?? '').toString(),
        label: (json['label'] ?? json['name'] ?? json['id'] ?? '').toString(),
        type: (json['type'] ?? json['group'] ?? 'Entity').toString(),
        properties: (json['properties'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

class GraphEdge {
  final String source;
  final String target;
  final String relation; // owns | issued_by | verified_by | linked_case

  GraphEdge({required this.source, required this.target, required this.relation});

  factory GraphEdge.fromJson(Map<String, dynamic> json) => GraphEdge(
        source: (json['source'] ?? '').toString(),
        target: (json['target'] ?? '').toString(),
        relation: (json['relation'] ?? json['type'] ?? json['label'] ?? '').toString(),
      );
}

class GraphData {
  final List<GraphNode> nodes;
  final List<GraphEdge> edges;

  GraphData({required this.nodes, required this.edges});

  factory GraphData.fromJson(Map<String, dynamic> json) => GraphData(
        nodes: (json['nodes'] as List? ?? [])
            .map((e) => GraphNode.fromJson(e as Map<String, dynamic>))
            .toList(),
        edges: (json['edges'] as List? ?? json['links'] as List? ?? [])
            .map((e) => GraphEdge.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  factory GraphData.empty() => GraphData(nodes: [], edges: []);
}
