import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import first_time_initialization
from infrahub.core.node import Node
from infrahub.core.utils import count_relationships, delete_all_nodes
from infrahub.git import InfrahubRepository
from infrahub_client import InfrahubClient, NodeNotFound

# pylint: disable=unused-argument


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def base_dataset(self, session):
        await delete_all_nodes(session=session)
        await first_time_initialization(session=session)

    @pytest.fixture(scope="class")
    async def test_client(
        self,
        base_dataset,
    ):
        # pylint: disable=import-outside-toplevel
        from infrahub.api import main

        return TestClient(main.app)

    @pytest.fixture
    async def client(self, test_client, integration_helper):
        admin_token = await integration_helper.create_token()

        return await InfrahubClient.init(test_client=test_client, api_token=admin_token)

    @pytest.fixture(scope="class")
    async def query_99(self, session, test_client):
        obj = await Node.init(schema="GraphQLQuery", session=session)
        await obj.new(
            session=session,
            name="query99",
            query="query query99 { repository { edges { id }}}",
        )
        await obj.save(session=session)
        return obj

    @pytest.fixture
    async def repo(self, test_client, client, session, git_upstream_repo_10, git_repos_dir):
        # Create the repository in the Graph
        obj = await Node.init(schema="Repository", session=session)
        await obj.new(
            session=session,
            name=git_upstream_repo_10["name"],
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(session=session)

        # Initialize the repository on the file system
        repo = await InfrahubRepository.new(
            id=obj.id,
            name=git_upstream_repo_10["name"],
            location=git_upstream_repo_10["path"],
        )

        repo.client = client

        return repo

    async def test_import_all_graphql_query(self, session, client: InfrahubClient, repo: InfrahubRepository):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_graphql_query(branch_name="main", commit=commit)

        queries = await client.all(kind="GraphQLQuery")
        assert len(queries) == 5

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)
        await repo.import_all_graphql_query(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in GIt and validate that it's been deleted
        value_before_change = queries[0].query.value
        queries[0].query.value = "query myquery { location { edges { id }}}"
        await queries[0].save()

        obj = await Node.init(schema="GraphQLQuery", session=session)
        await obj.new(
            session=session,
            name="soontobedeletedquery",
            query="query soontobedeletedquery { location { edges { id }}}",
            repository=str(repo.id),
        )
        await obj.save(session=session)

        await repo.import_all_graphql_query(branch_name="main", commit=commit)

        modified_query = await client.get(kind="GraphQLQuery", id=queries[0].id)
        assert modified_query.query.value == value_before_change

        with pytest.raises(NodeNotFound):
            await client.get(kind="GraphQLQuery", id=obj.id)

    async def test_import_all_python_files(self, session, client: InfrahubClient, repo: InfrahubRepository, query_99):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_python_files(branch_name="main", commit=commit)

        checks = await client.all(kind="Check")
        assert len(checks) >= 1

        transforms = await client.all(kind="TransformPython")
        assert len(transforms) >= 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)
        await repo.import_all_python_files(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in Git and validate that it's been deleted
        check_timeout_value_before_change = checks[0].timeout.value
        check_query_value_before_change = checks[0].query.id
        checks[0].timeout.value = 44
        checks[0].query = query_99.id
        await checks[0].save()

        transform_timeout_value_before_change = transforms[0].timeout.value
        transforms[0].timeout.value = 44
        await transforms[0].save()

        transform_query_value_before_change = transforms[1].query.id
        transforms[1].query = query_99.id
        await transforms[1].save()

        # Create Object that will be deleted
        obj1 = await Node.init(schema="Check", session=session)
        await obj1.new(
            session=session,
            name="soontobedeletedcheck",
            query=str(query_99.id),
            file_path="check.py",
            class_name="MyCheck",
            repository=str(repo.id),
        )
        await obj1.save(session=session)

        obj2 = await Node.init(schema="TransformPython", session=session)
        await obj2.new(
            session=session,
            name="soontobedeletedtransform",
            query=str(query_99.id),
            file_path="mytransform.py",
            url="mytransform",
            class_name="MyTransform",
            repository=str(repo.id),
        )
        await obj2.save(session=session)

        await repo.import_all_python_files(branch_name="main", commit=commit)

        modified_check0 = await client.get(kind="Check", id=checks[0].id)
        assert modified_check0.timeout.value == check_timeout_value_before_change
        assert modified_check0.query.id == check_query_value_before_change

        modified_transform0 = await client.get(kind="TransformPython", id=transforms[0].id)
        modified_transform1 = await client.get(kind="TransformPython", id=transforms[1].id)

        assert modified_transform0.timeout.value == transform_timeout_value_before_change
        assert modified_transform1.query.id == transform_query_value_before_change

        # FIXME not implemented yet
        with pytest.raises(NodeNotFound):
            await client.get(kind="Check", id=obj1.id)

        with pytest.raises(NodeNotFound):
            await client.get(kind="TransformPython", id=obj2.id)

    async def test_import_all_yaml_files(self, session, client: InfrahubClient, repo: InfrahubRepository, query_99):
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_all_yaml_files(branch_name="main", commit=commit)

        rfiles = await client.all(kind="RFile")
        assert len(rfiles) == 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(session=session)
        await repo.import_all_yaml_files(branch_name="main", commit=commit)
        assert await count_relationships(session=session) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in Git and validate that it's been deleted
        rfile_template_path_value_before_change = rfiles[0].template_path.value
        rfile_query_value_before_change = rfiles[0].query.id
        rfiles[0].template_path.value = "my_path"
        rfiles[0].query = query_99.id
        await rfiles[0].save()

        obj = await Node.init(schema="RFile", session=session)
        await obj.new(
            session=session,
            name="soontobedeletedrfile",
            query=str(query_99.id),
            template_repository=str(repo.id),
            template_path="mytmp.j2",
        )
        await obj.save(session=session)

        await repo.import_all_yaml_files(branch_name="main", commit=commit)

        modified_rfile = await client.get(kind="RFile", id=rfiles[0].id)
        assert modified_rfile.template_path.value == rfile_template_path_value_before_change
        assert modified_rfile.query.id == rfile_query_value_before_change

        # FIXME not implemented yet
        with pytest.raises(NodeNotFound):
            await client.get(kind="RFile", id=obj.id)
