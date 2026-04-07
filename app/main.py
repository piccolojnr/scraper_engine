from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config.registry import ConfigNotFoundError, registry
from app.extractors.factory import ExtractorFactory
from app.normalizers.orchestrator import EntityRunNormalizer
from app.runner.page_runner import PageRunner
from app.runner.university_runner import UniversityRunner
from app.runtime.browser_client import PlaywrightBrowserClient
from app.runtime.http_client import SimpleHttpClient
from app.runtime.openai_llm_client import OpenAILLMClient
from app.schemas.results import UniversityRunResult
from app.settings import get_settings


USER_AGENT = "UniScraper/2.0"


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
        default_headers={"User-Agent": USER_AGENT},
        verify_ssl=settings.http_client.verify_ssl,
    ) as http_client, PlaywrightBrowserClient(
        headless=not headed,
        browser_type=browser,
        default_headers={"User-Agent": USER_AGENT},
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
            normalizer=EntityRunNormalizer(),
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
            f"[{page_result.page_type.value}/{page_result.intent.value}/{page_result.audience.value}] "
            f"=> {page_result.status.value}"
        )

        entity_count = len(page_result.entities)
        print(f"    • entities: {entity_count}")

        for entity in page_result.entities:
            print(
                f"      - {entity.identity.entity_type.value} "
                f"#{entity.identity.record_index} => {entity.status.value}"
            )

            for field in entity.field_results:
                marker = "ok" if field.success else "fail"
                print(
                    f"          • {field.field_name} "
                    f"[{field.strategy.value}] {marker}"
                )

            if entity.error:
                print(f"          ! entity error: {entity.error.error_code.value}")
                print(f"            {entity.error.message}")

        if page_result.error:
            print(f"    ! page error: {page_result.error.error_code.value}")
            print(f"      {page_result.error.message}")

    if result.normalized:
        print()
        print("Normalized output:")
        print(f"  university: {'yes' if result.normalized.university else 'no'}")
        print(f"  portals: {len(result.normalized.portals)}")
        print(f"  courses: {len(result.normalized.courses)}")

        if result.normalized.university:
            uni = result.normalized.university
            print(f"  university.name: {uni.name}")
            print(f"  university.country: {uni.country}")

        if result.normalized.portals:
            print("  portal titles:")
            for portal in result.normalized.portals[:5]:
                print(f"    - {portal.title} [{portal.status}]")

        if result.normalized.courses:
            print("  course names:")
            for course in result.normalized.courses[:5]:
                print(f"    - {course.name}")

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