"""python -m carob_ml {data,train,evaluate,all}"""

import argparse
import json

from carob_ml import data, evaluate, train


def main() -> None:
    parser = argparse.ArgumentParser(prog="carob_ml", description="Support router data and models")
    parser.add_argument("step", choices=["data", "train", "evaluate", "all"])
    parser.add_argument("--version", help="model version to evaluate (default: newest)")
    args = parser.parse_args()
    if args.step in ("data", "all"):
        print(json.dumps(data.build()["splits"], indent=2))
    if args.step in ("train", "all"):
        manifest = train.train()
        print(manifest["version"], json.dumps(manifest["metrics"]))
    if args.step in ("evaluate", "all"):
        print(json.dumps(evaluate.evaluate(args.version), indent=2))


if __name__ == "__main__":
    main()
