"""互校协议版本（spec §2.3）.

Phase 4 MVP：单版本协议，无协商逻辑（Phase 5+ 多 Agent 跨实例时需要）。
"""

from __future__ import annotations

PROTOCOL_VERSION = "v1.0"


class VersionCompatibility:
    """协议版本兼容性（M2 W4 占位）."""

    SUPPORTED_VERSIONS = ("v1.0",)

    @classmethod
    def is_compatible(cls, version: str) -> bool:
        """检查版本是否兼容."""
        return version in cls.SUPPORTED_VERSIONS

    @classmethod
    def negotiate(cls, local_version: str, remote_version: str) -> str:
        """协商共同版本（占位）."""
        if local_version == remote_version:
            return local_version
        if local_version.startswith("v1.") and remote_version.startswith("v1."):
            return min(local_version, remote_version)
        raise ValueError(
            f"不兼容的协议版本: local={local_version}, remote={remote_version}"
        )


__all__ = ["PROTOCOL_VERSION", "VersionCompatibility"]