"""Init file for easyearth_plugin.core module."""
from .prompt_editor import BoxMapTool, map_id, create_point_box
# from .docker_manager import DockerManager
from .utils import setup_logger
from .env_manager import EnvManager

__all__ = [
    "BoxMapTool",
    # "DockerManager",
    "setup_logger",
    "map_id",
    "create_point_box",
    "EnvManager"
]