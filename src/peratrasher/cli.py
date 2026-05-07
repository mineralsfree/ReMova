import argparse

from peratrasher.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the peratrasher data-cleaning pipeline."
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
