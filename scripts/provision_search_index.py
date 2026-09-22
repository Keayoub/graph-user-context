"""Create or update the organizational Azure AI Search index using Entra RBAC."""

from graph_context.config import get_settings
from graph_context.search.client import build_index_client
from graph_context.search.sync import provision_index


def main() -> None:
    settings = get_settings()
    settings.validate_sync()
    provision_index(build_index_client(settings), settings.search_index_name)
    print(f"Provisioned index: {settings.search_index_name}")


if __name__ == "__main__":
    main()
