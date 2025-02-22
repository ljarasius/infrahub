"""Replacement for Makefile."""

# from typing import Optional

from invoke.context import Context
from invoke.tasks import task

from .container_ops import (
    destroy_environment,
    migrate_database,
    pull_images,
    restart_services,
    show_service_status,
    start_services,
    stop_services,
    update_core_schema,
)
from .infra_ops import load_infrastructure_data, load_infrastructure_menu, load_infrastructure_schema
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    SERVICE_SERVER_NAME,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

NAMESPACE = Namespace.DEFAULT


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Pull external containers from registry."""
    pull_images(context=context, database=database, namespace=NAMESPACE)


# ----------------------------------------------------------------------------
# Local Environment tasks
# ----------------------------------------------------------------------------


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE, wait: bool = False) -> None:
    """Start a local instance of Infrahub within docker compose."""
    start_services(context=context, database=database, namespace=NAMESPACE, wait=wait)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Restart Infrahub API Server and Task worker within docker compose."""
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Stop the running instance of Infrahub."""
    stop_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def destroy(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Destroy all containers and volumes."""
    destroy_environment(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def migrate(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Apply the latest database migrations."""
    migrate_database(context=context, database=database, namespace=NAMESPACE)
    update_core_schema(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def cli_server(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = (
            f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {SERVICE_SERVER_NAME} bash"
        )
        execute_command(context=context, command=command)


@task(optional=["database"])
def cli_git(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = (
            f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {SERVICE_WORKER_NAME} bash"
        )
        execute_command(context=context, command=command)


@task(optional=["database"])
def status(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Display the status of all containers."""
    show_service_status(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load the base schema for infrastructure."""
    load_infrastructure_schema(context=context, database=database, namespace=NAMESPACE, add_wait=False)
    load_infrastructure_menu(context=context, database=database, namespace=NAMESPACE)
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_menu(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load the base schema for infrastructure."""
    load_infrastructure_menu(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load infrastructure demo data."""
    load_infrastructure_data(context=context, database=database, namespace=NAMESPACE)
