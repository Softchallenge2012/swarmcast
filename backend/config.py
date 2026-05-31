from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str

    # W&B Weave
    wandb_api_key: str
    wandb_project: str = "swarmcast"

    # WC history API
    wc_api_key: str = ""

    # Football data
    football_data_api_key: str = ""
    api_football_key: str = ""

    # Polymarket — validation layer only, never touched during deliberation
    polymarket_api_key: str = ""
    polymarket_private_key: str = ""
    polymarket_chain_id: int = 137

    # Edge threshold in probability units (0.08 = 8 pp)
    edge_threshold: float = 0.08

    # Models
    orchestrator_model: str = "claude-sonnet-4-20250514"
    specialist_model: str = "claude-sonnet-4-20250514"
    critic_model: str = "claude-haiku-4-5-20251001"
    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
