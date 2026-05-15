import argparse

from app.pipeline import handle_message


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local multi-agent inference")
    parser.add_argument("message", nargs="?", default="Где мой заказ 5532?")
    args = parser.parse_args()
    result = handle_message(args.message)
    print(result.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
