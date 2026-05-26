from urllib.parse import urlsplit, urlunsplit


DATABASE_URL_NOT_SET_MESSAGE = (
    "DATABASE_URL is not set. Please configure external PostgreSQL database."
)


def normalize_database_url(url: str) -> str:
    if not url or not url.strip():
        raise ValueError(DATABASE_URL_NOT_SET_MESSAGE)

    normalized_url = url.strip()
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"postgresql", "postgresql+asyncpg"}:
        return normalized_url

    if parsed_url.scheme == "postgresql":
        parsed_url = parsed_url._replace(scheme="postgresql+asyncpg")

    if parsed_url.query:
        query = "&".join(_normalize_query_param(param) for param in parsed_url.query.split("&"))
        parsed_url = parsed_url._replace(query=query)

    return urlunsplit(parsed_url)


def _normalize_query_param(param: str) -> str:
    key, separator, value = param.partition("=")
    if key == "sslmode" and separator and value == "require":
        return "ssl=require"
    return param
