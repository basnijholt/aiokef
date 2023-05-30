"""A module for asynchronously interacting with KEF wireless speakers."""
import pkg_resources

from aiokef.aiokef import AsyncKefSpeaker, SyncKefSpeaker

__version__ = pkg_resources.get_distribution("aiokef").version

__all__ = ["AsyncKefSpeaker", "SyncKefSpeaker", "__version__"]
