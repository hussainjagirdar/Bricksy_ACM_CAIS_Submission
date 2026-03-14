"""
Entry point for the car dashboard MCP server
This module provides the main() function that is called by uv
Following Databricks official MCP server template pattern
"""
import uvicorn
import argparse


def main():
    """
    Main entry point for the car dashboard MCP server.
    Called by uv run when executing the car-dashboard-mcp command.

    Starts the uvicorn server with the combined app (MCP + REST API).
    """
    parser = argparse.ArgumentParser(description="Run the Car Dashboard MCP Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)"
    )
    args = parser.parse_args()

    # Run the combined app following Databricks pattern
    uvicorn.run(
        "backend:combined_app",
        host="0.0.0.0",
        port=args.port,
    )


if __name__ == "__main__":
    main()
