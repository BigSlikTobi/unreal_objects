"""CLI entry point for uo-company-server."""

import argparse
import logging
import sys

import uvicorn

from company_server.config import CompanyConfig


def main():
    parser = argparse.ArgumentParser(
        description="Run the Unreal Objects living virtual company server",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8010, help="Bind port (default: 8010)")
    parser.add_argument("--acceleration", type=float, default=10.0, help="Time acceleration factor (default: 10)")
    parser.add_argument("--base-rate", type=float, default=5.0, help="Base cases per virtual hour (default: 5)")
    parser.add_argument("--webhook-url", default=None, help="Webhook URL for case notifications")
    parser.add_argument("--webhook-secret", default=None, help="HMAC secret for webhook signatures")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI generation, use deterministic fallback")
    parser.add_argument("--ai-provider", default="openai", help="AI provider (default: openai)")
    parser.add_argument("--ai-model", default="gpt-4o", help="AI model (default: gpt-4o)")
    parser.add_argument("--ai-api-key", default="", help="AI API key (or set COMPANY_AI_API_KEY)")
    parser.add_argument("--rule-pack", default="rule_packs/support_company.json", help="Path to rule pack JSON")
    parser.add_argument("--rule-engine-url", default="http://127.0.0.1:8001", help="Rule Engine URL")
    parser.add_argument("--decision-center-url", default="http://127.0.0.1:8002", help="Decision Center URL")
    parser.add_argument("--customers", type=int, default=20, help="Initial customer count (default: 20)")
    parser.add_argument("--orders", type=int, default=50, help="Initial order count (default: 50)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = CompanyConfig(
        acceleration=args.acceleration,
        base_cases_per_hour=args.base_rate,
        ai_provider=args.ai_provider,
        ai_model=args.ai_model,
        ai_api_key=args.ai_api_key,
        webhook_url=args.webhook_url,
        webhook_secret=args.webhook_secret,
        rule_engine_url=args.rule_engine_url,
        decision_center_url=args.decision_center_url,
        rule_pack_path=args.rule_pack,
        host=args.host,
        port=args.port,
        initial_customers=args.customers,
        initial_orders=args.orders,
    )

    # Configure the app module before uvicorn imports it
    from company_server.app import configure
    configure(config, use_ai=not args.no_ai)

    print(f"Starting virtual company server on {args.host}:{args.port}")
    print(f"  Acceleration: {args.acceleration}x")
    print(f"  AI generation: {'disabled' if args.no_ai else args.ai_provider + '/' + args.ai_model}")
    print(f"  Webhook: {args.webhook_url or 'disabled'}")
    print(f"  Rule pack: {args.rule_pack}")

    uvicorn.run(
        "company_server.app:app",
        host=args.host,
        port=args.port,
        log_level="debug" if args.verbose else "info",
    )


if __name__ == "__main__":
    main()
