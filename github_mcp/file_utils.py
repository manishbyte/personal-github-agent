from pathlib import PurePosixPath


def normalize_requested_file(
    file_name: str,
) -> str:

    file_name = file_name.strip()

    file_name = file_name.strip(
        "`\"'"
    )

    file_name = file_name.replace(
        "\\",
        "/",
    )

    file_name = file_name.strip("/")

    return str(
        PurePosixPath(file_name)
    )