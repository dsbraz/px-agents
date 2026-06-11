from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    portal_bau_connection_string: str = Field(
        default="",
        validation_alias="PORTAL_BAU_STAGING_CONNECTION_STRING",
    )
    mcp_host: str = Field(default="0.0.0.0", validation_alias="MCP_HOST")
    mcp_port: int = Field(default=8000, validation_alias="MCP_PORT")


settings = Settings()
