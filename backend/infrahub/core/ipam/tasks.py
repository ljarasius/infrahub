import ipaddress
from typing import TYPE_CHECKING

from prefect import flow

from infrahub.core import registry
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.services import services
from infrahub.workflows.utils import add_branch_tag

from .model import IpamNodeDetails

if TYPE_CHECKING:
    from infrahub.core.ipam.constants import AllIPTypes


@flow(
    name="ipam_reconciliation",
    flow_run_name="branch-{branch}",
    description="Ensure the IPAM Tree is up to date",
    persist_result=False,
)
async def ipam_reconciliation(branch: str, ipam_node_details: list[IpamNodeDetails]) -> None:
    service = services.service
    branch_obj = await registry.get_branch(db=service.database, branch=branch)

    await add_branch_tag(branch_name=branch_obj.name)

    ipam_reconciler = IpamReconciler(db=service.database, branch=branch_obj)

    for ipam_node_detail_item in ipam_node_details:
        if ipam_node_detail_item.is_address:
            ip_value: AllIPTypes = ipaddress.ip_interface(ipam_node_detail_item.ip_value)
        else:
            ip_value = ipaddress.ip_network(ipam_node_detail_item.ip_value)
        await ipam_reconciler.reconcile(
            ip_value=ip_value,
            namespace=ipam_node_detail_item.namespace_id,
            node_uuid=ipam_node_detail_item.node_uuid,
            is_delete=ipam_node_detail_item.is_delete,
        )
