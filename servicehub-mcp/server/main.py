"""Entry point for ServiceHub — starts uvicorn with the combined app."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start ServiceHub server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    uvicorn.run(
        "server.app:combined_app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
