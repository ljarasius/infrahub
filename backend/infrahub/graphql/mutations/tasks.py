from __future__ import annotations

from prefect import flow

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge import BranchMerger
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import ValidationError
from infrahub.services import services
from infrahub.workflows.catalogue import BRANCH_MERGE
from infrahub.workflows.utils import add_branch_tag


@flow(name="merge-branch-mutation", flow_run_name="Merge branch graphQL mutation")
async def merge_branch_mutation(branch: str) -> None:
    service = services.service
    db = service.database

    await add_branch_tag(branch_name=branch)

    obj = await Branch.get_by_name(db=db, name=branch)
    base_branch = await Branch.get_by_name(db=db, name=registry.default_branch)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=base_branch, diff_branch=obj)
    if enriched_diff.get_all_conflicts():
        raise ValidationError(
            f"Branch {obj.name} contains conflicts with the default branch."
            " Please create a Proposed Change to resolve the conflicts or manually update them before merging."
        )
    node_diff_field_summaries = await diff_repository.get_node_field_summaries(
        diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
    )

    merger = BranchMerger(
        db=db,
        diff_coordinator=diff_coordinator,
        diff_merger=diff_merger,
        source_branch=obj,
        service=service,
    )
    candidate_schema = merger.get_candidate_schema()
    determiner = ConstraintValidatorDeterminer(schema_branch=candidate_schema)
    constraints = await determiner.get_constraints(node_diffs=node_diff_field_summaries)
    if obj.has_schema_changes:
        constraints += await merger.calculate_validations(target_schema=candidate_schema)

    if constraints:
        error_messages = await schema_validate_migrations(
            message=SchemaValidateMigrationData(branch=obj, schema_branch=candidate_schema, constraints=constraints)
        )
        if error_messages:
            raise ValidationError(",\n".join(error_messages))

    await service.workflow.execute_workflow(workflow=BRANCH_MERGE, parameters={"branch": obj.name})
