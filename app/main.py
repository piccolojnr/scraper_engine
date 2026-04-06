from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config.registry import ConfigNotFoundError, registry
from app.extractors.factory import ExtractorFactory
from app.normalizers.default import DefaultUniversityNormalizer
from app.runner.page_runner import PageRunner
from app.runner.university_runner import UniversityRunner
from app.runtime.browser_client import PlaywrightBrowserClient
from app.runtime.http_client import SimpleHttpClient
from app.runtime.openai_llm_client import OpenAILLMClient
from app.schemas.results import UniversityRunResult
from app.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uniscraper",
        description="Run a university scraper config.",
    )
    parser.add_argument(
        "config_id",
        help="University config ID to run, for example: ug",
    )
    parser.add_argument(
        "--configs-package",
        default="configs",
        help="Python package name where config modules live. Default: configs",
    )
    parser.add_argument(
        "--configs-dir",
        default="configs",
        help="Directory path where config modules live. Default: configs",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write the run result JSON.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser pages in headed mode instead of headless mode.",
    )
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=["chromium", "firefox", "webkit"],
        help="Browser engine for Playwright pages. Default: chromium",
    )
    return parser


async def run_once(
    *,
    config_id: str,
    configs_package: str,
    configs_dir: str,
    headed: bool,
    browser: str,
) -> UniversityRunResult:
    registry.clear()
    registry.load_package(configs_package, Path(configs_dir))
    config = registry.get(config_id)
    settings = get_settings()
    llm_client = OpenAILLMClient.from_env()

    async with SimpleHttpClient(
        default_headers={
            "User-Agent": "UniScraper/1.0",
        },
        verify_ssl=settings.http_client.verify_ssl,
    ) as http_client, PlaywrightBrowserClient(
        headless=not headed,
        browser_type=browser,
        default_headers={
            "User-Agent": "UniScraper/1.0",
        },
    ) as browser_client:
        extractor_factory = ExtractorFactory(
            llm_client=llm_client,
        )

        page_runner = PageRunner(
            extractor_factory=extractor_factory,
            http_client=http_client,
            browser_client=browser_client,
        )

        university_runner = UniversityRunner(
            page_runner=page_runner,
            normalizer=DefaultUniversityNormalizer(),
        )

        return await university_runner.run(config)


def print_summary(result: UniversityRunResult) -> None:
    print()
    print(f"University: {result.university_name} ({result.university_id})")
    print(f"Run status: {result.status.value}")
    print(f"Duration: {result.duration_ms} ms")
    print(f"Pages: {len(result.page_results)}")
    print()

    for page_result in result.page_results:
        print(
            f"- {page_result.page_name} "
            f"[{page_result.page_category.value}] "
            f"=> {page_result.status.value}"
        )

        for field in page_result.extracted_fields:
            marker = "ok" if field.success else "fail"
            print(
                f"    • {field.name} -> {field.output_field} "
                f"[{field.strategy.value}] {marker}"
            )

        if page_result.error:
            print(f"    ! error: {page_result.error.error_code.value}")
            print(f"      {page_result.error.message}")

    if result.snapshot:
        print()
        print("Snapshot:")
        print(f"  status: {result.snapshot.status}")
        print(f"  programmes: {len(result.snapshot.programmes)}")
        print(f"  deadlines: {len(result.snapshot.deadlines)}")
        print(f"  cut-offs: {len(result.snapshot.cut_off_points)}")
        print(f"  scholarships: {len(result.snapshot.scholarships)}")

    if result.errors:
        print()
        print("Errors:")
        for error in result.errors:
            print(f"  - {error.page_name}: {error.error_code.value} - {error.message}")


def write_json(result: UniversityRunResult, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = await run_once(
            config_id=args.config_id,
            configs_package=args.configs_package,
            configs_dir=args.configs_dir,
            headed=args.headed,
            browser=args.browser,
        )
    except ConfigNotFoundError as exc:
        print(f"Config error: {exc}")
        return 2
    except Exception as exc:
        print(f"Run failed: {exc}")
        return 1

    print_summary(result)

    if args.output_json:
        write_json(result, args.output_json)
        print()
        print(f"Saved JSON result to: {args.output_json}")

    return 0


def main() -> None:
    if OpenAILLMClient.from_env() is not None:
        print("OpenAI LLM client enabled from environment.")
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
