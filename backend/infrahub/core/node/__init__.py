from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union, overload

from infrahub_sdk.utils import is_valid_uuid
from infrahub_sdk.uuidt import UUIDT

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, ComputedAttributeKind, InfrahubKind, RelationshipCardinality
from infrahub.core.constants.schema import SchemaElementPathType
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.query.node import NodeCheckIDQuery, NodeCreateAllQuery, NodeDeleteQuery, NodeGetListQuery
from infrahub.core.schema import AttributeSchema, NodeSchema, ProfileSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError, NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.support.macro import MacroDefinition
from infrahub.types import ATTRIBUTE_TYPES

from ...graphql.constants import KIND_GRAPHQL_FIELD_NAME
from ..relationship import RelationshipManager
from ..utils import update_relationships_to
from .base import BaseNode, BaseNodeMeta, BaseNodeOptions

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..attribute import BaseAttribute

SchemaProtocol = TypeVar("SchemaProtocol")

# ---------------------------------------------------------------------------------------
# Type of Nodes
#  - Core node, wo/ branch : Branch, MergeRequest, Comment
#  - Core node, w/ branch : Repository, GQLQuery, Permission, Account, Groups, Schema
#  - Location Node : Location,
#  - Select Node : Status, Role, Manufacturer etc ..
#  -
# ---------------------------------------------------------------------------------------

# pylint: disable=redefined-builtin,too-many-branches


class Node(BaseNode, metaclass=BaseNodeMeta):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls, _meta=None, default_filter=None, **options
    ) -> None:
        if not _meta:
            _meta = BaseNodeOptions(cls)

        _meta.default_filter = default_filter
        super().__init_subclass_with_meta__(_meta=_meta, **options)

    def get_schema(self) -> Union[NodeSchema, ProfileSchema]:
        return self._schema

    def get_kind(self) -> str:
        """Return the main Kind of the Object."""
        return self._schema.kind

    def get_id(self) -> str:
        """Return the ID of the node"""
        if self.id:
            return self.id

        raise InitializationError("The node has not been saved yet and doesn't have an id")

    def get_updated_at(self) -> Timestamp | None:
        return self._updated_at

    async def get_hfid(self, db: InfrahubDatabase, include_kind: bool = False) -> Optional[list[str]]:
        """Return the Human friendly id of the node."""
        if not self._schema.human_friendly_id:
            return None

        hfid = [await self.get_path_value(db=db, path=item) for item in self._schema.human_friendly_id]
        if include_kind:
            return [self.get_kind()] + hfid
        return hfid

    async def get_hfid_as_string(self, db: InfrahubDatabase, include_kind: bool = False) -> Optional[str]:
        """Return the Human friendly id of the node in string format separated with a dunder (__) ."""
        hfid = await self.get_hfid(db=db, include_kind=include_kind)
        if not hfid:
            return None
        return "__".join(hfid)

    async def get_path_value(self, db: InfrahubDatabase, path: str) -> str:
        schema_path = self._schema.parse_schema_path(
            path=path, schema=registry.schema.get_schema_branch(name=self._branch.name)
        )

        if not schema_path.has_property:
            raise ValueError(f"Unable to retrieve the value of a path without property {path!r} on {self.get_kind()!r}")

        if (
            schema_path.is_type_relationship
            and schema_path.relationship_schema.cardinality == RelationshipCardinality.MANY
        ):
            raise ValueError(
                f"Unable to retrieve the value of a path on a relationship of cardinality many {path!r} on {self.get_kind()!r}"
            )

        if schema_path.is_type_attribute:
            attr = getattr(self, schema_path.attribute_schema.name)
            return getattr(attr, schema_path.attribute_property_name)

        if schema_path.is_type_relationship:
            relm: RelationshipManager = getattr(self, schema_path.relationship_schema.name)
            await relm.resolve(db=db)
            node = await relm.get_peer(db=db)
            attr = getattr(node, schema_path.attribute_schema.name)
            return getattr(attr, schema_path.attribute_property_name)

    def get_labels(self) -> list[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""
        labels: list[str] = []
        if isinstance(self._schema, NodeSchema):
            labels = [self.get_kind()] + self._schema.inherit_from
            if (
                self._schema.namespace not in ["Schema", "Internal"]
                and InfrahubKind.GENERICGROUP not in self._schema.inherit_from
            ):
                labels.append(InfrahubKind.NODE)
            return labels

        if isinstance(self._schema, ProfileSchema):
            labels = [self.get_kind()] + self._schema.inherit_from
            return labels

        return [self.get_kind()]

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Returns:
            Branch:
        """
        if self._schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self._branch

    def __repr__(self) -> str:
        if not self._existing:
            return f"{self.get_kind()}(ID: {str(self.id)})[NEW]"

        return f"{self.get_kind()}(ID: {str(self.id)})"

    def __init__(self, schema: Union[NodeSchema, ProfileSchema], branch: Branch, at: Timestamp):
        self._schema: Union[NodeSchema, ProfileSchema] = schema
        self._branch: Branch = branch
        self._at: Timestamp = at
        self._existing: bool = False

        self._updated_at: Optional[Timestamp] = None
        self.id: str = None
        self.db_id: str = None

        self._source: Optional[Node] = None
        self._owner: Optional[Node] = None
        self._is_protected: bool = None
        self._computed_jinja2_attributes: list[str] = []

        # Lists of attributes and relationships names
        self._attributes: list[str] = []
        self._relationships: list[str] = []

    @overload
    @classmethod
    async def init(
        cls,
        schema: Union[NodeSchema, ProfileSchema, str],
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = ...,
        at: Optional[Union[Timestamp, str]] = ...,
    ) -> Self: ...

    @overload
    @classmethod
    async def init(
        cls,
        schema: type[SchemaProtocol],
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = ...,
        at: Optional[Union[Timestamp, str]] = ...,
    ) -> SchemaProtocol: ...

    @classmethod
    async def init(
        cls,
        schema: Union[NodeSchema, ProfileSchema, str, type[SchemaProtocol]],
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> Self | SchemaProtocol:
        attrs: dict[str, Any] = {}

        branch = await registry.get_branch(branch=branch, db=db)

        if isinstance(schema, (NodeSchema, ProfileSchema)):
            attrs["schema"] = schema
        elif isinstance(schema, str):
            # TODO need to raise a proper exception for this, right now it will raise a generic ValueError
            attrs["schema"] = db.schema.get(name=schema, branch=branch)
        elif hasattr(schema, "_is_runtime_protocol") and getattr(schema, "_is_runtime_protocol"):
            attrs["schema"] = db.schema.get(name=schema.__name__, branch=branch)
        else:
            raise ValueError(f"Invalid schema provided {type(schema)}, expected NodeSchema or ProfileSchema")

        attrs["branch"] = branch
        attrs["at"] = Timestamp(at)

        return cls(**attrs)

    async def process_pool(self, db: InfrahubDatabase, attribute: BaseAttribute, errors: list) -> None:
        """Evaluate if a resource has been requested from a pool and apply the resource

        This method only works on number pools, currently Integer is the only type that has the from_pool
        within the create code.
        """

        if not attribute.from_pool:
            return

        try:
            number_pool = await registry.manager.get_one_by_id_or_default_filter(
                db=db, id=attribute.from_pool["id"], kind=CoreNumberPool
            )
        except NodeNotFoundError:
            errors.append(
                ValidationError(
                    {f"{attribute.name}.from_pool": f"The pool requested {attribute.from_pool} was not found."}
                )
            )
            return

        if number_pool.node.value == self._schema.kind and number_pool.node_attribute.value == attribute.name:
            try:
                next_free = await number_pool.get_resource(db=db, branch=self._branch, node=self)
            except PoolExhaustedError:
                errors.append(
                    ValidationError({f"{attribute.name}.from_pool": f"The pool {number_pool.node.value} is exhausted."})
                )
                return

            attribute.value = next_free
            attribute.source = number_pool.id
        else:
            errors.append(
                ValidationError(
                    {
                        f"{attribute.name}.from_pool": f"The {number_pool.name.value} pool can't be used for '{attribute.name}'."
                    }
                )
            )

    async def _process_fields(self, fields: dict, db: InfrahubDatabase) -> None:
        errors = []

        if "_source" in fields.keys():
            self._source = fields["_source"]
        if "_owner" in fields.keys():
            self._owner = fields["_owner"]

        # -------------------------------------------
        # Validate Input
        # -------------------------------------------
        if "updated_at" in fields and "updated_at" not in self._schema.valid_input_names:
            # FIXME: Allow users to use "updated_at" named attributes until we have proper metadata handling
            fields.pop("updated_at")
        for field_name in fields.keys():
            if field_name not in self._schema.valid_input_names:
                errors.append(ValidationError({field_name: f"{field_name} is not a valid input for {self.get_kind()}"}))

        # If the object is new, we need to ensure that all mandatory attributes and relationships have been provided
        if not self._existing:
            for mandatory_attr in self._schema.mandatory_attribute_names:
                if mandatory_attr not in fields.keys():
                    if self._schema.is_node_schema:
                        mandatory_attribute = self._schema.get_attribute(name=mandatory_attr)
                        if (
                            mandatory_attribute.computed_attribute
                            and mandatory_attribute.computed_attribute.kind == ComputedAttributeKind.JINJA2
                        ):
                            self._computed_jinja2_attributes.append(mandatory_attr)
                            continue

                    errors.append(
                        ValidationError({mandatory_attr: f"{mandatory_attr} is mandatory for {self.get_kind()}"})
                    )

            for mandatory_rel in self._schema.mandatory_relationship_names:
                if mandatory_rel not in fields.keys():
                    errors.append(
                        ValidationError({mandatory_rel: f"{mandatory_rel} is mandatory for {self.get_kind()}"})
                    )

        if errors:
            raise ValidationError(errors)

        # -------------------------------------------
        # Generate Attribute and Relationship and assign them
        # -------------------------------------------
        for rel_schema in self._schema.relationships:
            self._relationships.append(rel_schema.name)

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_relationship_default"
            if hasattr(self, f"generate_{rel_schema.name}"):
                generator_method_name = f"generate_{rel_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    rel_schema.name,
                    await generator_method(
                        db=db, name=rel_schema.name, schema=rel_schema, data=fields.get(rel_schema.name, None)
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        for attr_schema in self._schema.attributes:
            self._attributes.append(attr_schema.name)
            if not self._existing and attr_schema.name in self._computed_jinja2_attributes:
                continue

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_attribute_default"
            if hasattr(self, f"generate_{attr_schema.name}"):
                generator_method_name = f"generate_{attr_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    attr_schema.name,
                    await generator_method(
                        db=db, name=attr_schema.name, schema=attr_schema, data=fields.get(attr_schema.name, None)
                    ),
                )
                if not self._existing:
                    attribute: BaseAttribute = getattr(self, attr_schema.name)
                    await self.process_pool(db=db, attribute=attribute, errors=errors)

                    attribute.validate(value=attribute.value, name=attribute.name, schema=attribute.schema)
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

        # Check if any post processor have been defined
        # A processor can be used for example to assigne a default value
        for name in self._attributes + self._relationships:
            if hasattr(self, f"process_{name}"):
                await getattr(self, f"process_{name}")(db=db)

    async def _process_macros(self, db: InfrahubDatabase) -> None:
        schema_branch = registry.schema.get_schema_branch(name=self._branch.name)
        allowed_path_types = (
            SchemaElementPathType.ATTR_WITH_PROP | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
        )
        errors = []
        for macro in self._computed_jinja2_attributes:
            variables = {}
            attr_schema = self._schema.get_attribute(name=macro)
            if not attr_schema.computed_attribute:
                errors.append(
                    ValidationError({macro: f"{macro} is missing computational_logic for macro ({attr_schema.kind})"})
                )
                continue
            if not attr_schema.computed_attribute.jinja2_template:
                errors.append(
                    ValidationError({macro: f"{macro} is missing computational_logic for macro ({attr_schema.kind})"})
                )
                continue
            macro_definition = MacroDefinition(macro=attr_schema.computed_attribute.jinja2_template)

            for variable in macro_definition.variables:
                attribute_path = schema_branch.validate_schema_path(
                    node_schema=self._schema, path=variable, allowed_path_types=allowed_path_types
                )
                if attribute_path.is_type_relationship:
                    relationship_attribute: RelationshipManager = getattr(
                        self, attribute_path.active_relationship_schema.name
                    )
                    peer = await relationship_attribute.get_peer(db=db, raise_on_error=True)

                    related_node = await registry.manager.get_one_by_id_or_default_filter(
                        db=db, id=peer.id, kind=attribute_path.active_relationship_schema.peer
                    )

                    attribute: BaseAttribute = getattr(
                        getattr(related_node, attribute_path.active_attribute_schema.name),
                        attribute_path.active_attribute_property_name,
                    )
                    variables[variable] = attribute

                elif attribute_path.is_type_attribute:
                    attribute = getattr(
                        getattr(self, attribute_path.active_attribute_schema.name),
                        attribute_path.active_attribute_property_name,
                    )
                    variables[variable] = attribute

            content = macro_definition.render(variables=variables)

            generator_method_name = "_generate_attribute_default"
            if hasattr(self, f"generate_{attr_schema.name}"):
                generator_method_name = f"generate_{attr_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    attr_schema.name,
                    await generator_method(db=db, name=attr_schema.name, schema=attr_schema, data=content),
                )
                attribute = getattr(self, attr_schema.name)

                attribute.validate(value=attribute.value, name=attribute.name, schema=attribute.schema)
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

    async def _generate_relationship_default(
        self,
        name: str,  # pylint: disable=unused-argument
        schema: RelationshipSchema,
        data: Any,
        db: InfrahubDatabase,
    ) -> RelationshipManager:
        rm = await RelationshipManager.init(
            db=db,
            data=data,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
        )

        return rm

    async def _generate_attribute_default(
        self,
        name: str,
        schema: AttributeSchema,
        data: Any,
        db: InfrahubDatabase,  # pylint: disable=unused-argument
    ) -> BaseAttribute:
        attr_class = ATTRIBUTE_TYPES[schema.kind].get_infrahub_class()
        attr = attr_class(
            data=data,
            name=name,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
            source=self._source,
            owner=self._owner,
        )
        return attr

    async def process_label(self, db: Optional[InfrahubDatabase] = None) -> None:  # pylint: disable=unused-argument
        # If there label and name are both defined for this node
        #  if label is not define, we'll automatically populate it with a human friendy vesion of name
        # pylint: disable=no-member
        if not self._existing and hasattr(self, "label") and hasattr(self, "name"):
            if self.label.value is None and self.name.value:
                self.label.value = " ".join([word.title() for word in self.name.value.split("_")])
                self.label.is_default = False

    async def new(self, db: InfrahubDatabase, id: Optional[str] = None, **kwargs: Any) -> Self:
        if id and not is_valid_uuid(id):
            raise ValidationError({"id": f"{id} is not a valid UUID"})
        if id:
            query = await NodeCheckIDQuery.init(db=db, node_id=id)
            if await query.count(db=db):
                raise ValidationError({"id": f"{id} is already in use"})

        self.id = id or str(UUIDT())

        await self._process_fields(db=db, fields=kwargs)
        await self._process_macros(db=db)

        return self

    async def resolve_relationships(self, db: InfrahubDatabase) -> None:
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            await relm.resolve(db=db)

    async def load(
        self,
        db: InfrahubDatabase,
        id: Optional[str] = None,
        db_id: Optional[str] = None,
        updated_at: Optional[Union[Timestamp, str]] = None,
        **kwargs: Any,
    ) -> Self:
        self.id = id
        self.db_id = db_id
        self._existing = True

        if updated_at:
            kwargs["updated_at"] = (
                updated_at  # FIXME: Allow users to use "updated_at" named attributes until we have proper metadata handling
            )
            self._updated_at = Timestamp(updated_at)

        await self._process_fields(db=db, fields=kwargs)
        return self

    async def _create(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> None:
        create_at = Timestamp(at)

        query = await NodeCreateAllQuery.init(db=db, node=self, at=create_at)
        await query.execute(db=db)

        _, self.db_id = query.get_self_ids()
        self._at = create_at
        self._updated_at = create_at
        self._existing = True

        new_ids = query.get_ids()

        # Go over the list of Attribute and assign the new IDs one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            attr.id, attr.db_id = new_ids[name]
            attr.at = create_at

        # Go over the list of relationships and assign the new IDs one by one
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            for rel in relm._relationships:
                identifier = f"{rel.schema.identifier}::{rel.peer_id}"
                rel.id, rel.db_id = new_ids[identifier]

    async def _update(
        self, db: InfrahubDatabase, at: Optional[Timestamp] = None, fields: list[str] | None = None
    ) -> None:
        """Update the node in the database if needed."""

        update_at = Timestamp(at)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            if fields and name in fields:
                attr: BaseAttribute = getattr(self, name)
                await attr.save(at=update_at, db=db)
            else:
                attr: BaseAttribute = getattr(self, name)
                await attr.save(at=update_at, db=db)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            if fields and name in fields:
                rel: RelationshipManager = getattr(self, name)
                await rel.save(at=update_at, db=db)
            else:
                attr: BaseAttribute = getattr(self, name)
                await attr.save(at=update_at, db=db)

    async def save(self, db: InfrahubDatabase, at: Optional[Timestamp] = None, fields: list[str] | None = None) -> Self:
        """Create or Update the Node in the database."""

        save_at = Timestamp(at)

        if self._existing:
            await self._update(at=save_at, db=db, fields=fields)
            return self

        await self._create(at=save_at, db=db)
        return self

    async def delete(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> None:
        """Delete the Node in the database."""

        delete_at = Timestamp(at)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            await attr.delete(at=delete_at, db=db)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel: RelationshipManager = getattr(self, name)
            await rel.delete(at=delete_at, db=db)

        # Need to check if there are some unidirectional relationship as well
        # For example, if we delete a tag, we must check the permissions and update all the relationships pointing at it
        branch = self.get_branch_based_on_support_type()

        # Update the relationship to the branch itself
        query = await NodeGetListQuery.init(
            db=db, schema=self._schema, filters={"id": self.id}, branch=self._branch, at=delete_at
        )
        await query.execute(db=db)
        result = query.get_result()

        if result and result.get("rb.branch") == branch.name:
            await update_relationships_to([result.get("rb_id")], to=delete_at, db=db)

        query = await NodeDeleteQuery.init(db=db, node=self, at=delete_at)
        await query.execute(db=db)

    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
        permissions: Optional[dict] = None,
    ) -> dict:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """

        response: dict[str, Any] = {"id": self.id, KIND_GRAPHQL_FIELD_NAME: self.get_kind()}

        if related_node_ids is not None:
            related_node_ids.add(self.id)

        FIELD_NAME_TO_EXCLUDE = ["id"] + self._schema.relationship_names

        if fields and isinstance(fields, dict):
            field_names = [field_name for field_name in fields.keys() if field_name not in FIELD_NAME_TO_EXCLUDE]
        else:
            field_names = self._schema.attribute_names + ["__typename", "display_label"]

        for field_name in field_names:
            if field_name == "__typename":
                # Note we already store kind within KIND_GRAPHQL_FIELD_NAME.
                response[field_name] = self.get_kind()
                continue

            if field_name == "display_label":
                response[field_name] = await self.render_display_label(db=db)
                continue

            if field_name == "hfid":
                response[field_name] = await self.get_hfid(db=db)
                continue

            if field_name == "_updated_at":
                if self._updated_at:
                    response[field_name] = await self._updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            field: Optional[BaseAttribute] = getattr(self, field_name, None)

            if not field:
                response[field_name] = None
                continue

            if fields and isinstance(fields, dict):
                response[field_name] = await field.to_graphql(
                    db=db,
                    fields=fields.get(field_name),
                    related_node_ids=related_node_ids,
                    filter_sensitive=filter_sensitive,
                    permissions=permissions,
                )
            else:
                response[field_name] = await field.to_graphql(
                    db=db, filter_sensitive=filter_sensitive, permissions=permissions
                )

        return response

    async def from_graphql(self, data: dict, db: InfrahubDatabase) -> bool:
        """Update object from a GraphQL payload."""

        changed = False

        for key, value in data.items():
            if key in self._attributes and isinstance(value, dict):
                attribute = getattr(self, key)
                changed |= await attribute.from_graphql(data=value, db=db)

            if key in self._relationships:
                rel: RelationshipManager = getattr(self, key)
                changed |= await rel.update(db=db, data=value)

        return changed

    async def render_display_label(self, db: Optional[InfrahubDatabase] = None) -> str:  # pylint: disable=unused-argument
        if not self._schema.display_labels:
            return repr(self)

        display_elements = []
        for item in self._schema.display_labels:
            item_elements = item.split("__")
            if len(item_elements) != 2:
                raise ValidationError("Display Label can only have one level")

            if item_elements[0] not in self._schema.attribute_names:
                raise ValidationError("Only Attribute can be used in Display Label")

            attr = getattr(self, item_elements[0])
            attr_value = getattr(attr, item_elements[1])
            if isinstance(attr_value, Enum):
                display_elements.append(attr_value.value)
            else:
                display_elements.append(attr_value)

        if not display_elements or all(de is None for de in display_elements):
            return ""
        display_label = " ".join([str(de) for de in display_elements])
        if not display_label.strip():
            return repr(self)
        return display_label.strip()
