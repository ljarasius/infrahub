import pytest

from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch import SchemaBranch


@pytest.mark.parametrize(
    "schema_root,expected_error",
    [
        pytest.param(
            SchemaRoot(
                generics=[
                    GenericSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2, jinja2_template="n/a"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' computed attributes are only allowed on nodes not generics",
            id="jinja2_on_generic",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' is a computed jinja2 attribute but not marked as read_only",
            id="missing_read_only",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' is a computed jinja2 attribute but no logic is defined",
            id="logic_missing",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2,
                                    jinja2_template="{{ name__value }} {% include 'index.html' %}",
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' is assigned by a jinja2 template, but has an invalid template",
            id="template_invalid_format",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2,
                                    jinja2_template="{{ name__value }}-{{ fullname__value }}",
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' the 'fullname__value' variable is not found within the schema path",
            id="macro_invalid_path",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                        ],
                    ),
                    NodeSchema(
                        name="Dog",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2,
                                    jinja2_template="{{ owner__fullname__value }}'s {{ name__value }}",
                                ),
                            ),
                        ],
                        relationships=[
                            RelationshipSchema(
                                name="owner", peer="TestingPerson", cardinality=RelationshipCardinality.ONE
                            )
                        ],
                    ),
                ],
            ),
            "TestingDog: Attribute 'computed' the 'owner__fullname__value' variable is not found within the schema path",
            id="invalid_related_path",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2,
                                    jinja2_template="{{ name__value }}-{{ computed__value }}",
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' the 'computed__value' variable is a reference to itself",
            id="self_reference",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Number",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' is a computed jinja2 attribute currently only 'Text' kinds are supported.",
            id="wrong_kind",
        ),
        pytest.param(
            SchemaRoot(
                nodes=[
                    NodeSchema(
                        name="Person",
                        namespace="Testing",
                        attributes=[
                            AttributeSchema(
                                name="name",
                                kind="Text",
                            ),
                            AttributeSchema(
                                name="computed",
                                kind="Text",
                                read_only=True,
                                computed_attribute=ComputedAttribute(
                                    kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="my_transform"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            "TestingPerson: Attribute 'computed' is a computed transform, it can't be mandatory",
            id="required_transform",
        ),
    ],
)
async def test_schema_protected_generics(schema_root: SchemaRoot, expected_error: str):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_root)

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_computed_attributes()
