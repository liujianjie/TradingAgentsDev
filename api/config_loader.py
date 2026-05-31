"""Load LLM and 3rd-party API keys from config/apikeys.local.json.

Reads the active provider's api_key + model names and exports them as
environment variables so that langchain/openai SDK and TradingAgents'
``DEFAULT_CONFIG`` (via TRADINGAGENTS_* overrides) pick them up.
"""
import json
import os
from pathlib import Path

_PROVIDER_TO_ENV = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    "glm": "ZHIPU_API_KEY",
    "minimax-cn": "MINIMAX_CN_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "xai": "XAI_API_KEY",
}


def _config_path() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent / "config" / "apikeys.local.json"


def load_apikeys(verbose: bool = True) -> dict:
    """Load apikeys.local.json and inject the active provider into environment.

    Returns the parsed config dict. Missing file is non-fatal: the function
    just logs a warning so the user sees what to do, and TradingAgents will
    later fail with the original "Missing credentials" error from the SDK.
    """
    path = _config_path()
    if not path.exists():
        if verbose:
            print(f"[apikeys] config not found: {path}. See docs/setup-apikeys.md")
        return {}

    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    active = cfg.get("active_provider")
    providers = cfg.get("providers", {})

    if not active or active not in providers:
        if verbose:
            print(f"[apikeys] active_provider '{active}' missing from providers")
        return cfg

    pcfg = providers[active]
    api_key = pcfg.get("api_key", "")
    if api_key:
        env_name = _PROVIDER_TO_ENV.get(active)
        if env_name:
            os.environ[env_name] = api_key
        os.environ["TRADINGAGENTS_LLM_PROVIDER"] = active
        if pcfg.get("deep_think_model"):
            os.environ["TRADINGAGENTS_DEEP_THINK_LLM"] = pcfg["deep_think_model"]
        if pcfg.get("quick_think_model"):
            os.environ["TRADINGAGENTS_QUICK_THINK_LLM"] = pcfg["quick_think_model"]
        if pcfg.get("base_url"):
            os.environ["TRADINGAGENTS_LLM_BACKEND_URL"] = pcfg["base_url"]
        if verbose:
            print(f"[apikeys] loaded provider={active} deep={pcfg.get('deep_think_model')}")
    else:
        if verbose:
            print(f"[apikeys] provider '{active}' has empty api_key")

    # Load data API keys
    data_apis = cfg.get("data_apis", {})
    av_key = data_apis.get("alpha_vantage", "") if isinstance(data_apis, dict) else ""
    if av_key:
        os.environ["ALPHA_VANTAGE_API_KEY"] = av_key
        if verbose:
            print("[apikeys] alpha_vantage key loaded")

    return cfg


def get_serverchan_key() -> str:
    """Read serverchan.send_key from the same config (used by C# via JSON, but
    Python may also need it for self-test scripts)."""
    cfg = load_apikeys(verbose=False)
    return (cfg.get("serverchan") or {}).get("send_key", "") or ""
