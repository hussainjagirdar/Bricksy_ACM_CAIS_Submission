"""
Utility helpers for Databricks Apps integration.

Provides:
- header_store: ContextVar to capture per-request HTTP headers (set by middleware)
- get_workspace_client(): service-principal workspace client
- get_user_authenticated_workspace_client(): user-auth client via x-forwarded-access-token
"""

import contextvars

from databricks.sdk import WorkspaceClient


header_store: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "header_store", default={}
)


def get_workspace_client() -> WorkspaceClient:
    """Return a basic WorkspaceClient using service-principal / default auth."""
    return WorkspaceClient()


def get_user_authenticated_workspace_client() -> WorkspaceClient:
    """Return a WorkspaceClient authenticated as the calling user.

    In Databricks Apps the reverse proxy sets ``x-forwarded-access-token``
    with the end-user's OAuth token.  When running locally the header is
    absent, so we fall back to the default credential chain.
    """
    headers = header_store.get()
    user_token = headers.get("x-forwarded-access-token")

    if user_token:
        return WorkspaceClient(token=user_token)

    # Local dev — fall back to default auth
    return WorkspaceClient()
