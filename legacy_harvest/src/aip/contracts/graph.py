"""Layer 0 public contracts: load the Enterprise Knowledge Graph, then query it.

`GraphProvider` is the only way to load a graph — YAML fixture (development)
and Knowledge API (future) both return the same `EnterpriseContext`, so
higher layers never know which one is behind it.

`GraphQuery` is the only way to read a graph. It exposes pure graph
mechanics (lookup, traversal) and must never encode business meaning —
departments, ownership, capabilities, and similar interpretation belong to
Layer 1 and above.
"""

from typing import Protocol, runtime_checkable

from aip.contracts.models import (
    Entity,
    EnterpriseContext,
    EnterpriseKnowledgeGraph,
    Relationship,
)


@runtime_checkable
class GraphProvider(Protocol):
    def load_context(self, org_id: str) -> EnterpriseContext: ...


@runtime_checkable
class GraphQuery(Protocol):
    def get_entities(
        self,
        types: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> list[Entity]: ...

    def get_relationships(
        self, types: list[str] | None = None
    ) -> list[Relationship]: ...

    def find_by_type(self, entity_type: str) -> list[Entity]: ...

    def find_by_label(self, label: str) -> list[Entity]: ...

    def neighbors(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        direction: str = "both",
    ) -> list[Entity]: ...

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        relationship_types: list[str] | None = None,
    ) -> list[Relationship]: ...

    def connected_component(self, entity_id: str) -> EnterpriseKnowledgeGraph: ...

    def find_connected(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
    ) -> list[Entity]: ...

    def subgraph(
        self, entity_ids: list[str], depth: int = 1
    ) -> EnterpriseKnowledgeGraph: ...
