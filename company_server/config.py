"""Configuration for the company server, loaded from environment variables."""

from pydantic_settings import BaseSettings


class CompanyConfig(BaseSettings):
    model_config = {"env_prefix": "COMPANY_"}

    # Time
    acceleration: float = 10.0

    # Case generation
    base_cases_per_hour: float = 5.0
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o"
    ai_api_key: str = ""

    # Webhooks
    webhook_url: str | None = None
    webhook_secret: str | None = None

    # Unreal Objects service URLs
    rule_engine_url: str = "http://127.0.0.1:8001"
    decision_center_url: str = "http://127.0.0.1:8002"
    rule_pack_path: str = "rule_packs/support_company.json"

    # Server
    host: str = "0.0.0.0"
    port: int = 8010

    # Eviction
    max_cases: int = 5000

    # Seeding
    initial_customers: int = 20
    initial_orders: int = 50
