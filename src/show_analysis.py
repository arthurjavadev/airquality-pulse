"""Read the saved, database-backed summary in a separate process."""
import argparse
from src.collector import CITIES
from src.data.database import make_engine
from src.data.analysis_gateway import AnalysisGateway


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="Berlin")
    args = parser.parse_args(argv)
    name = CITIES.get(args.city.strip().casefold())
    if name is None:
        parser.error("Unsupported city")
    engine = make_engine()
    try:
        report = AnalysisGateway(engine).find_by_city(name[0])
        if not report:
            parser.error("No analysis saved; run python -m src.analyzer first")
        for key, value in report.items():
            print(f"{key}: {value}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
