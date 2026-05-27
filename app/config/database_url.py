from urllib.parse import urlsplit, urlunsplit


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"
DATABASE_URL_NOT_SET_MESSAGE = (
    f"DATABASE_URL is not set. Defaulting to SQLite database: {DEFAULT_DATABASE_URL}"
)
DATABASE_URL_EXTERNAL_HOST_MESSAGE = (
    "DATABASE_URL host must be an external PostgreSQL hostname, not a local Docker host "
    "or placeholder."
)
LOCAL_OR_PLACEHOLDER_HOSTS = frozenset({"host", "db", "postgres", "localhost", "127.0.0.1", "::1"})
UNSUPPORTED_ASYNCPG_QUERY_PARAMS = frozenset({"channel_binding"})


def normalize_database_url(url: str | None) -> str:
    if url is None or not str(url).strip():
        return DEFAULT_DATABASE_URL

    normalized_url = str(url).strip()
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"postgresql", "postgresql+asyncpg"}:
        return normalized_url

    if parsed_url.scheme == "postgresql":
        parsed_url = parsed_url._replace(scheme="postgresql+asyncpg")

    if parsed_url.query:
        query = "&".join(
            normalized_param
            for param in parsed_url.query.split("&")
            if (normalized_param := _normalize_query_param(param)) is not None
        )
        parsed_url = parsed_url._replace(query=query)

    return urlunsplit(parsed_url)


def validate_external_database_url(url: str | None) -> str:
    normalized_url = normalize_database_url(url)
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"postgresql", "postgresql+asyncpg"}:
        return normalized_url

    host = parsed_url.hostname
    if host is None or host.casefold() in LOCAL_OR_PLACEHOLDER_HOSTS:
        raise ValueError(f"{DATABASE_URL_EXTERNAL_HOST_MESSAGE} Current host: {host or '-'}")

    return normalized_url


def _normalize_query_param(param: str) -> str | None:
    key, separator, value = param.partition("=")
    if key in UNSUPPORTED_ASYNCPG_QUERY_PARAMS:
        return None
    if key == "sslmode" and separator and value == "require":
        return "ssl=require"
    return param
