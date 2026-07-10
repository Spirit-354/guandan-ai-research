import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


STEP_01_URL = "http://183.175.14.145:8003/step_01"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "python-step-client/1.0"})
    with urlopen(request, timeout=10) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset)
    return json.loads(body)


def extract_next_url(payload: dict) -> str:
    if not payload.get("is_success"):
        raise RuntimeError(f"Request did not succeed: {payload!r}")

    message = payload.get("message")
    if not isinstance(message, str):
        raise RuntimeError(f"JSON response has no text message: {payload!r}")

    match = re.search(r"https?://\S+", message)
    if not match:
        raise RuntimeError(f"Message does not contain a URL: {message!r}")

    return match.group(0)


def main() -> None:
    try:
        payload = fetch_json(STEP_01_URL)
        next_url = extract_next_url(payload)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        raise SystemExit(f"Failed to get next instruction: {exc}") from exc

    print(next_url)


if __name__ == "__main__":
    main()
