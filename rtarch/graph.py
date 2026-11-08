"""Build the service interaction graph from RTARCH events."""

from collections import defaultdict
from typing import Dict, List, Set, Tuple

import networkx as nx

from .models import Phase, RTArchEvent


def build_graph(events: List[RTArchEvent]) -> nx.DiGraph:
    """Build a directed graph.

    Nodes are service names; an edge ``A -> B`` means *A sent at least one
    message to B*.  Edge annotations carry the observed message types.

    Only ``SEND`` and ``RECV`` events define edges.  ``REPLY`` events describe
    the response travelling back along an existing edge; including them would
    add reversed duplicates and turn the service graph into a cyclic graph.
    """
    graph = nx.DiGraph()
    edge_msg_types: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for event in events:
        if event.phase is Phase.REPLY:
            continue

        graph.add_node(event.src_name)
        graph.add_node(event.dst_name)
        edge_msg_types[(event.src_name, event.dst_name)].add(event.msg_type)
        graph.add_edge(event.src_name, event.dst_name)

    for edge, msg_types in edge_msg_types.items():
        ordered = ",".join(sorted(msg_types))
        graph[edge[0]][edge[1]]["msg_types"] = sorted(msg_types)
        graph[edge[0]][edge[1]]["msg_type"] = ordered

    return graph
