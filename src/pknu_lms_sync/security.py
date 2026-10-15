from urllib.parse import urljoin, urlparse


BASE_URL = "https://lms.pknu.ac.kr"
ALLOWED_HOST = "lms.pknu.ac.kr"


def same_origin(url: str) -> str:
    result = urljoin(BASE_URL, url)
    parsed = urlparse(result)
    if parsed.scheme != "https" or parsed.netloc != ALLOWED_HOST:
        raise ValueError("부경대 LMS가 아닌 주소에는 요청하지 않습니다.")
    return result
