from __future__ import annotations

from enum import IntFlag, StrEnum, auto
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission


class AssignedPermissions(TypedDict):
    global_permissions: list[GlobalPermission]
    object_permissions: list[ObjectPermission]


class PermissionDecisionFlag(IntFlag):
    DENY = 1
    ALLOW_DEFAULT = 2
    ALLOW_OTHER = 4
    ALLOW_ALL = ALLOW_DEFAULT | ALLOW_OTHER


class BranchRelativePermissionDecision(StrEnum):
    """This enum is only used to communicate a permission decision relative to a branch."""

    DENY = auto()
    ALLOW = auto()
    ALLOW_DEFAULT = auto()
    ALLOW_OTHER = auto()
