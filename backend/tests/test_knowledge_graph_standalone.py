from knowledge_graph.extractor import KnowledgeGraphExtractor

kg_extractor = KnowledgeGraphExtractor()
print(kg_extractor.process_text("Apple was founded by Steve Jobs.", {}))
