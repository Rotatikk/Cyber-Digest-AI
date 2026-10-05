from __future__ import annotations

import re
from app.models import Article, Classification

TERMS = [
    "кибербезопас", "информационн.* безопас", "кибератак", "киберинцидент",
    "ddos", "ransomware", "фишинг", "spear phishing", "вредонос", "malware",
    "троян", "ботнет", "уязвимост", "zero-day", "0-day", "exploit", "rce",
    "утечк.* данн", "компрометац", "credential", "mfa", "iam", "soc", "siem",
    "firewall", "waf", "edr", "apt", "кии", "фстэк", "фсб", "роскомнадзор",
]


def lexical_candidate(article: Article) -> bool:
    text = f"{article.title} {article.text}".lower()
    return any(re.search(term, text) for term in TERMS)
