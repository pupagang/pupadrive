from typing import Union
import os


class MissingEnvironmentVariable(Exception):
    pass


def try_get_env(var_name: str) -> str:
    """
    Try to get an environment variable, raises `MissingEnvironmentVariable` if the environment
    variable is not configured
    """
    try:
        return os.environ[var_name]
    except KeyError:
        raise MissingEnvironmentVariable(
            f"{var_name} environment variable is missing")


def get_readable_filesize(val: int):
    """
    Convert file size to human readable format.
    """
    units = ("B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB")
    for unit in units:
        if abs(val) < 1000:
            return f"{val:.3g}{unit}"

        val /= 1000  # type: ignore

    return f"{val:.3g}YB"


def get_readable_time(secs: Union[int, float]) -> str:
    """
    Convert seconds to human readable format.
    """
    seconds = int(secs)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    days = int(days)
    if days != 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours != 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes != 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
