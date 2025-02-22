from unittest.mock import AsyncMock, MagicMock, Mock, call, patch
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot
from infrahub.core.diff.models import RequestDiffRefresh, RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.component.registry import ComponentDependencyRegistry
from infrahub.message_bus import messages
from infrahub.message_bus.operations.event.branch import merge, rebased
from infrahub.services import InfrahubServices, services
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import (
    REQUEST_DIFF_REFRESH,
    REQUEST_DIFF_UPDATE,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from tests.adapters.message_bus import BusRecorder


@pytest.fixture
def init_service():
    original = services.service
    recorder = BusRecorder()
    database = MagicMock()
    workflow = WorkflowLocalExecution()
    service = InfrahubServices(message_bus=recorder, database=database, workflow=workflow)
    services.service = service
    yield service
    services.service = original


async def test_merged(default_branch: Branch, init_service: InfrahubServices, prefect_test_fixture):
    """
    Test that merge flow triggers corrects events/workflows. It does not actually test these events/workflows behaviors
    as they are mocked.
    """

    source_branch_name = "cr1234"
    target_branch_name = "main"
    right_now = Timestamp()
    message = messages.EventBranchMerge(
        source_branch=source_branch_name, target_branch=target_branch_name, ipam_node_details=[]
    )
    service = init_service

    tracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
            tracking_id=BranchTrackingId(name=str(uuid4())),
        )
        for _ in range(2)
    ]
    untracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
        )
        for _ in range(2)
    ]
    diff_repo = AsyncMock(spec=DiffRepository)
    diff_repo.get_empty_roots.return_value = untracked_diff_roots + tracked_diff_roots
    mock_component_registry = Mock(spec=ComponentDependencyRegistry)
    mock_get_component_registry = MagicMock(return_value=mock_component_registry)
    mock_component_registry.get_component.return_value = diff_repo

    with (
        patch("infrahub.message_bus.operations.event.branch.get_component_registry", new=mock_get_component_registry),
        patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow,
    ):
        await merge(message=message, service=service)

        expected_calls = [
            call(workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE, parameters={"branch": message.target_branch}),
            call(
                workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
                parameters={"branch": target_branch_name},
            ),
            call(
                workflow=REQUEST_DIFF_UPDATE,
                parameters={"model": RequestDiffUpdate(branch_name=tracked_diff_roots[0].diff_branch_name)},
            ),
            call(
                workflow=REQUEST_DIFF_UPDATE,
                parameters={"model": RequestDiffUpdate(branch_name=tracked_diff_roots[1].diff_branch_name)},
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)
        assert mock_submit_workflow.call_count == len(expected_calls)

    mock_component_registry.get_component.assert_awaited_once_with(
        DiffRepository, db=service.database, branch=default_branch
    )
    diff_repo.get_empty_roots.assert_awaited_once_with(base_branch_names=[target_branch_name])

    assert len(service.message_bus.messages) == 1
    assert service.message_bus.messages[0] == messages.RefreshRegistryBranches()


async def test_rebased(default_branch: Branch, prefect_test_fixture):
    """Validate that a rebased branch triggers a registry refresh and cancels open proposed changes"""
    branch_name = "cr1234"
    right_now = Timestamp()
    message = messages.EventBranchRebased(branch=branch_name)

    recorder = BusRecorder()
    database = MagicMock()
    service = InfrahubServices(message_bus=recorder, database=database, workflow=WorkflowLocalExecution())
    diff_roots = [
        EnrichedDiffRoot(
            base_branch_name="main",
            diff_branch_name=branch_name,
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
        )
        for _ in range(2)
    ]
    diff_repo = AsyncMock(spec=DiffRepository)
    diff_repo.get_empty_roots.return_value = diff_roots
    mock_component_registry = Mock(spec=ComponentDependencyRegistry)
    mock_get_component_registry = MagicMock(return_value=mock_component_registry)
    mock_component_registry.get_component.return_value = diff_repo

    with (
        patch("infrahub.message_bus.operations.event.branch.get_component_registry", new=mock_get_component_registry),
        patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow,
    ):
        await rebased(message=message, service=service)

        expected_calls = [
            call(
                workflow=REQUEST_DIFF_REFRESH,
                parameters={"model": RequestDiffRefresh(branch_name=branch_name, diff_id=diff_roots[0].uuid)},
            ),
            call(
                workflow=REQUEST_DIFF_REFRESH,
                parameters={"model": RequestDiffRefresh(branch_name=branch_name, diff_id=diff_roots[1].uuid)},
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)
        assert mock_submit_workflow.call_count == len(expected_calls)

    mock_component_registry.get_component.assert_awaited_once_with(DiffRepository, db=database, branch=default_branch)
    diff_repo.get_empty_roots.assert_awaited_once_with(diff_branch_names=[branch_name])
    assert len(recorder.messages) == 1
    assert isinstance(recorder.messages[0], messages.RefreshRegistryRebasedBranch)
    refresh_message: messages.RefreshRegistryRebasedBranch = recorder.messages[0]
    assert refresh_message.branch == "cr1234"
