from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:devpass@localhost:5432/expense_tracker"
    )
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_SECRET_PREVIOUS: str = ""
    INTERNAL_CRON_TOKEN: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.ENVIRONMENT not in ("development", "test"):
            errors = []
            if self.JWT_SECRET == "dev-secret-change-me":
                errors.append("JWT_SECRET must be changed from default")
            if not self.GOOGLE_CLIENT_ID:
                errors.append("GOOGLE_CLIENT_ID is required")
            if not self.GOOGLE_CLIENT_SECRET:
                errors.append("GOOGLE_CLIENT_SECRET is required")
            if errors:
                raise ValueError(
                    f"Production configuration errors: {'; '.join(errors)}"
                )
        return self


settings = Settings()
