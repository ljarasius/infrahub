from infrahub.message_bus.messages.proposed_change.base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeDataIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger data integrity checks for a proposed change"""
