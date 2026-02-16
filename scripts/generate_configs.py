import argparse
import os

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=3)
    parser.add_argument("--output", default="configs/")
    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    for i in range(1, args.nodes + 1):
        config = {
            "node_id": f"node-{i}",
            "phi_target": 1.618,
            "sacred_frequency": 108,
            "mesh_backend": "simulation",
        }
        with open(os.path.join(args.output, f"node-{i}.yaml"), "w") as f:
            yaml.dump(config, f)


if __name__ == "__main__":
    main()
