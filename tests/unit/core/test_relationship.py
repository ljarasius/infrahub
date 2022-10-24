import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.relationship import Relationship
from infrahub.core.query.relationship import RelationshipGetPeerQuery, RelationshipCreateQuery, RelationshipDeleteQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes


def test_relationship_init(default_branch, person_tag_schema):

    person_schema = registry.get_schema("Person")
    rel_schema = person_schema.get_relationship("tags")

    t1 = Node("Tag").new(name="blue").save()
    p1 = Node(person_schema).new(firstname="John", lastname="Doe").save()

    rel = Relationship(schema=rel_schema, branch=default_branch, node=p1)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert rel.node == p1

    rel = Relationship(schema=rel_schema, branch=default_branch, node_id=p1.id)

    assert rel.schema == rel_schema
    assert rel.name == rel_schema.name
    assert rel.branch == default_branch
    assert rel.node_id == p1.id
    assert type(rel.node) == Node
    assert rel.node.id == p1.id
