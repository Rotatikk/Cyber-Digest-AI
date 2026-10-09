from __future__ import annotations

from app.models import Event, GeneratedPackage, ValidationReport, PackageCheck
from app.validation.evidence import deterministic_package_check, strip_urls

DIGEST_LIMIT = 4000
POST_LIMIT = 2000


def validate_package(package: GeneratedPackage, selected_events: list[Event]) -> list[str]:
    return validate_report(package, selected_events).errors


def validate_report(package: GeneratedPackage, selected_events: list[Event]) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if len(strip_urls(package.digest)) > DIGEST_LIMIT:
        errors.append("digest_over_4000")
    if len(strip_urls(package.post)) > POST_LIMIT:
        errors.append("post_over_2000")
    if not package.email_subject.strip():
        errors.append("email_subject_empty")
    if len(selected_events) > 5:
        errors.append("more_than_5_events")
    if len(selected_events) < 5:
        warnings.append(f"less_than_5_events:{len(selected_events)}")
    package_check = deterministic_package_check(package, selected_events)
    errors.extend(package_check.violations)
    return ValidationReport(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        package_check=package_check,
        events_selected=len(selected_events),
    )
