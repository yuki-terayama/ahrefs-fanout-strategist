"""共通ユーティリティ。

- .env の読み込み
- 環境変数アクセス
- パスヘルパー
- ドメイン正規化
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = PROJECT_ROOT / "output"

load_dotenv(ENV_PATH)


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} が未設定です。{ENV_PATH} に記入してください（.env.example 参照）"
        )
    return val


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def ensure_output_dir(subdir: str = "") -> Path:
    d = OUTPUT_DIR / subdir if subdir else OUTPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_domain(url: str) -> str:
    """URL → ホスト名（先頭 www. を除去）"""
    if not url:
        return ""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return host.lower()


def normalize_domain(url: str) -> str:
    """URL → ドメイン（サブドメイン含む）軽量版"""
    if not url:
        return ""
    s = url.lower().replace("http://", "").replace("https://", "")
    return s.split("/")[0]


def domain_matches(domain: str, target: str) -> bool:
    """domain が target と一致、または target のサブドメインか"""
    domain = (domain or "").lower()
    target = (target or "").lower()
    return bool(domain) and (domain == target or domain.endswith("." + target))
