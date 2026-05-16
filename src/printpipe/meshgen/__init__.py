"""Mesh generation provider interface and built-in provider skeletons."""

from .contracts import (
    DeleteResult,
    MeshGenCapabilities,
    MeshGenCost,
    MeshGenError,
    MeshGenEstimate,
    MeshGenProvider,
    MeshGenRequest,
    MeshGenResult,
    MeshGenTiming,
    ProviderHealth,
)
from .providers import (
    ExistingMeshProvider,
    Hunyuan3DProvider,
    PlaceholderMeshProvider,
    available_provider_ids,
    default_registry,
    generate_with_retries,
    get_provider,
    register_provider,
    sha256_file,
    write_provider_receipts,
)

__all__ = [
    "DeleteResult",
    "ExistingMeshProvider",
    "Hunyuan3DProvider",
    "MeshGenCapabilities",
    "MeshGenCost",
    "MeshGenError",
    "MeshGenEstimate",
    "MeshGenProvider",
    "MeshGenRequest",
    "MeshGenResult",
    "MeshGenTiming",
    "PlaceholderMeshProvider",
    "ProviderHealth",
    "available_provider_ids",
    "default_registry",
    "generate_with_retries",
    "get_provider",
    "register_provider",
    "sha256_file",
    "write_provider_receipts",
]
