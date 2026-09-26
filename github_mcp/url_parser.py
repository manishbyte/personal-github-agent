from urllib.parse import urlparse


def parse_github_url(
    url: str,
) -> tuple[str | None, str | None]:

    url = url.strip()

    parsed = urlparse(url)

    if parsed.netloc.lower() not in {
        "github.com",
        "www.github.com",
    }:
        return None, None

    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if len(parts) < 2:
        return None, None

    owner = parts[0]
    repository = parts[1]

    if repository.endswith(".git"):
        repository = repository[:-4]

    return owner, repository