from prefect import flow

from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository, get_initialized_repo, initialize_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.services import InfrahubServices
from infrahub.worker import WORKER_IDENTITY

log = get_logger()


@flow(name="git-repository-check-connectivity")
async def connectivity(message: messages.GitRepositoryConnectivity, service: InfrahubServices) -> None:
    response_data = GitRepositoryConnectivityResponseData(message="Successfully accessed repository", success=True)

    try:
        InfrahubRepository.check_connectivity(name=message.repository_name, url=message.repository_location)
    except RepositoryError as exc:
        response_data.success = False
        response_data.message = exc.message

    if message.reply_requested:
        response = GitRepositoryConnectivityResponse(
            data=response_data,
        )
        await service.reply(message=response, initiator=message)


@flow(name="git-repository-import-object")
async def import_objects(message: messages.GitRepositoryImportObjects, service: InfrahubServices) -> None:
    async with service.git_report(
        related_node=message.repository_id,
        title=f"Processing repository ({message.repository_name})",
    ) as git_report:
        repo = await get_initialized_repo(
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )
        repo.task_report = git_report
        await repo.import_objects_from_files(infrahub_branch_name=message.infrahub_branch_name, commit=message.commit)


@flow(name="refresh-git-fetch", flow_run_name="Fetch git repository {message.repository_name} on " + WORKER_IDENTITY)
async def fetch(message: messages.RefreshGitFetch, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git fetch request originating from self", worker=WORKER_IDENTITY)
        return

    try:
        repo = await get_initialized_repo(
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )
    except RepositoryError:
        repo = await initialize_repo(
            location=message.location,
            repository_id=message.repository_id,
            name=message.repository_name,
            service=service,
            repository_kind=message.repository_kind,
        )

    await repo.fetch()
    await repo.pull(branch_name=message.infrahub_branch_name)
