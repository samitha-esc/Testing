"""Main controller loop (placeholder).

This file will initialize the camera, selected engine, and MIDI controller,
then run the processing loop.
"""

import argparse

from engines.base_engine import BaseEngine


def main():
    parser = argparse.ArgumentParser(description="Gesture MIDI Controller")
    parser.add_argument("--engine", default="color", help="Engine to use: color, contours, medipipe")
    args = parser.parse_args()

    print(f"Starting scaffold with engine: {args.engine}")
    # Actual initialization will be added later


if __name__ == "__main__":
    main()
