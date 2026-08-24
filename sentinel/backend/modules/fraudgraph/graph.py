"""Network construction and ring detection.

The graph is built exactly once from typed, normalized entities. Clusters
are connected components of the undirected projection; hubs are ranked by
betweenness centrality. Pure functions - no I/O - so they are trivially
unit-testable.
"""

import networkx as nx

from backend.modules.fraudgraph.schemas import EdgeOut, NodeOut


def build_graph(nodes: list[NodeOut], edges: list[EdgeOut]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(node.key, **node.model_dump())
    for edge in edges:
        if (
            graph.has_node(edge.source)
            and graph.has_node(edge.target)
            and edge.source != edge.target
        ):
            graph.add_edge(edge.source, edge.target, relation=edge.relation)
    return graph


def detect_clusters(graph: nx.DiGraph) -> list[set[str]]:
    undirected = graph.to_undirected()
    return [c for c in nx.connected_components(undirected) if len(c) >= 2]


def rank_hubs(graph: nx.DiGraph, cluster: set[str]) -> tuple[str | None, float]:
    sub = graph.subgraph(cluster).to_undirected()
    if sub.number_of_nodes() == 0:
        return None, 0.0
    if sub.number_of_nodes() < 3:
        hub = max(sub.nodes, key=lambda n: sub.degree(n))
        return hub, float(sub.degree(hub))
    centrality = nx.betweenness_centrality(sub)
    hub = max(centrality, key=centrality.get)
    return hub, round(centrality[hub], 4)


def degree_map(graph: nx.DiGraph) -> dict[str, int]:
    return dict(graph.degree())
