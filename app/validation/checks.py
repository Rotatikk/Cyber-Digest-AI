from __future__ import annotations

from app.models import Event, GeneratedPackage

DIGEST_LIMIT = 4000
POST_LIMIT = 2000

def strip_urls(text: str) -> str:
    import re
    return re.sub(r"https?://\S+", "", text)

def validate_package(package: GeneratedPackage, selected_events: list[Event]) -> list[str]:
    errors: list[str] = []
    if len(strip_urls(package.digest)) > DIGEST_LIMIT:
        errors.append("digest_over_4000")
    if len(strip_urls(package.post)) > POST_LIMIT:
        errors.append("post_over_2000")
    if not package.email_subject.strip():
        errors.append("email_subject_empty")
    if len(selected_events) > 5:
        errors.append("more_than_5_events")
    return errors
