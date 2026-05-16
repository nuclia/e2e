from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing_extensions import Self


class E2ESettings(BaseSettings):
    """Pydantic settings for the E2E test suite.

    Per-environment variables are optional and validated based on TEST_ENV.
    """

    # Common
    test_env: str
    grafana_url: str
    test_zones: str | None = None

    # Prod environment
    prod_global_recaptcha: str = ""
    prod_root_pat_token: str = ""
    prod_permament_account_owner_pat_token: str = ""
    test_gmail_app_password: str = ""
    prod_gcp_europe1_nua: str = ""
    prod_aws_us_east_2_1_nua: str = ""
    prod_aws_il_central_1_1_nua: str = ""
    prod_aws_eu_central_1_1_nua: str = ""
    prod_aws_me_central_1_1_nua: str = ""

    # Stage environment
    stage_global_recaptcha: str = ""
    stage_root_pat_token: str = ""
    stage_permament_account_owner_pat_token: str = ""
    stage_gcp_europe1_nua: str = ""

    # Progress environment
    progress_global_recaptcha: str = ""
    progress_root_pat_token: str = ""
    progress_permament_account_owner_pat_token: str = ""
    progress_aws_proc_us_east_2_1_nua: str = ""

    # Benchmarking
    benchmark: str = ""
    gha_run_id: str = "unknown"
    prometheus_pushgateway: str = "http://prometheus-cloud-pushgateway-prometheus-pushgateway:9091"
    core_apps_repo_path: str = "/tmp/core-apps"

    # Cloud Storage Sync
    google_drive_client_id: str = "687895873226-3gd1euiov317l5i7rh9iliaobe95onv4.apps.googleusercontent.com"
    google_drive_client_secret: str = ""
    # The refresh token is expected to have the "https://www.googleapis.com/auth/drive" scope
    google_drive_refresh_token: str = ""
    google_external_connection_id: str = "00000000-0000-7000-8000-000000000000"

    @model_validator(mode="after")
    def validate_env_specific_vars(self) -> Self:
        env = self.test_env.lower()
        missing = []

        if env == "prod":
            fields = [
                "prod_global_recaptcha",
                "prod_root_pat_token",
                "prod_permament_account_owner_pat_token",
                "test_gmail_app_password",
                "prod_gcp_europe1_nua",
                "prod_aws_us_east_2_1_nua",
                "prod_aws_il_central_1_1_nua",
                "prod_aws_eu_central_1_1_nua",
                "prod_aws_me_central_1_1_nua",
            ]
        elif env == "stage":
            fields = [
                "stage_global_recaptcha",
                "stage_root_pat_token",
                "stage_permament_account_owner_pat_token",
                "test_gmail_app_password",
                "stage_gcp_europe1_nua",
            ]
        elif env == "progress":
            fields = [
                "progress_global_recaptcha",
                "progress_root_pat_token",
                "progress_permament_account_owner_pat_token",
                "test_gmail_app_password",
                "progress_aws_proc_us_east_2_1_nua",
            ]
        else:
            msg = f"Unknown TEST_ENV: {env!r}. Must be one of: prod, stage, progress"
            raise ValueError(msg)

        for field in fields:
            value = getattr(self, field)
            if not value or not value.strip():
                missing.append(field.upper())

        if missing:
            msg = f"Missing required env vars for TEST_ENV={env!r}: {', '.join(missing)}"
            raise ValueError(msg)

        return self


# Singleton instance — import this from other modules
settings = E2ESettings()  # type: ignore[call-arg]
