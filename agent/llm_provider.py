"""
agent/llm_provider.py

Abstraction layer for LLM providers.
Supports: Anthropic (Claude), OpenAI (GPT-4o), Ollama (local).

All providers expose the same interface:
    provider.diagnose(prompt: str) -> str
"""

import os
import getpass

#  Base                                                               
class LLMProvider:
    name = "base"

    def diagnose(self, prompt: str) -> str:
        raise NotImplementedError


#  Anthropic                                                          

class AnthropicProvider(LLMProvider):
    name = "Anthropic (Claude)"

    def __init__(self, model="claude-opus-4-6", api_key=None):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Run: pip install anthropic")

        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("No API key provided and ANTHROPIC_API_KEY is not set.")

        self.client = Anthropic(api_key=api_key)
        self.model  = model

    def diagnose(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()


#  OpenAI                                                             
class OpenAIProvider(LLMProvider):
    name = "OpenAI (GPT-4o)"

    def __init__(self, model="gpt-4o", api_key=None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Run: pip install openai")

        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No API key provided and OPENAI_API_KEY is not set.")

        self.client = OpenAI(api_key=api_key)
        self.model  = model

    def diagnose(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()


#  Ollama (local)                                                     

class OllamaProvider(LLMProvider):
    name = "Ollama (local)"

    def __init__(self, model="llama3", api_key=None):  # api_key ignored, no auth needed
        try:
            import requests
        except ImportError:
            raise ImportError("Run: pip install requests")

        self.model = model
        self.url   = "http://localhost:11434/api/generate"

        import requests as req
        try:
            req.get("http://localhost:11434", timeout=2)
        except Exception:
            raise ConnectionError(
                "Ollama not reachable at localhost:11434. "
                "Make sure Ollama is running: https://ollama.com"
            )

    def diagnose(self, prompt: str) -> str:
        import requests
        response = requests.post(self.url, json={
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
        }, timeout=60)
        response.raise_for_status()
        return response.json()["response"].strip()


#  Provider registry                                                  

PROVIDERS = {
    "1": {
        "label":   "Anthropic (Claude)",
        "cls":     AnthropicProvider,
        "env_var": "ANTHROPIC_API_KEY",
        "needs_key": True,
        "default_model": "claude-opus-4-6",
    },
    "2": {
        "label":   "OpenAI (GPT-4o)",
        "cls":     OpenAIProvider,
        "env_var": "OPENAI_API_KEY",
        "needs_key": True,
        "default_model": "gpt-4o",
    },
    "3": {
        "label":   "Ollama (local — no key needed)",
        "cls":     OllamaProvider,
        "env_var": None,
        "needs_key": False,
        "default_model": "llama3",
    },
}


#  Helpers                                                            

def _divider():
    print("  " + "─" * 46)

def _check_env_var(env_var: str) -> str | None:
    """Return masked value if env var is set, else None."""
    val = os.environ.get(env_var)
    if val:
        masked = val[:6] + "*" * (len(val) - 6) if len(val) > 6 else "***"
        return masked
    return None


#  Main selector                                                      
def select_provider() -> LLMProvider:
    """
    Interactive CLI startup menu.

    Flow:
      1. Choose a provider
      2. For API-key providers: choose between env var or manual input
         - If env var: show what variable to set and its current status
         - If manual:  securely prompt for the key (hidden input)
      3. Optionally override the model name
      4. Return a configured LLMProvider ready to use
    """

    print("\n" + "=" * 50)
    print("  AgentOps-Lite  |  LLM Provider Setup")
    print("=" * 50)

    # ── Step 1: Choose provider ──────────────────────────────────────
    print("\n  Which LLM provider do you want to use?\n")
    for key, meta in PROVIDERS.items():
        print(f"    [{key}] {meta['label']}")
    print()

    while True:
        choice = input("  Enter choice (1/2/3): ").strip()
        if choice in PROVIDERS:
            break
        print("  ❌ Please enter 1, 2, or 3.")

    meta = PROVIDERS[choice]
    print(f"\n  ✅ Selected: {meta['label']}")
    _divider()

    # ── Step 2: API key setup ────────────────────────────────────────
    api_key = None

    if meta["needs_key"]:
        env_var      = meta["env_var"]
        env_status   = _check_env_var(env_var)
        env_is_set   = env_status is not None

        print(f"\n  How do you want to provide your API key?\n")
        print(f"    [1] Use environment variable  ({env_var})")

        if env_is_set:
            print(f"         ✅ Currently set: {env_status}")
        else:
            print(f"         ⚠️  Not set — to set it permanently:")
            print(f"             Windows:  $env:{env_var}=\"your-key\"  (PowerShell)")
            print(f"             Mac/Linux: export {env_var}=\"your-key\"")

        print(f"\n    [2] Enter key manually now  (not saved anywhere)")
        print()

        while True:
            key_choice = input("  Enter choice (1/2): ").strip()
            if key_choice in ("1", "2"):
                break
            print("  ❌ Please enter 1 or 2.")

        if key_choice == "1":
            if not env_is_set:
                print(f"\n  ❌ {env_var} is not set. Set it and re-run, or choose option 2.")
                raise SystemExit("No API key available.")
            print(f"  ✅ Using {env_var} from environment ({env_status})")
            api_key = None  # provider will read it from env itself

        else:
            print(f"\n  Enter your {meta['label']} API key (input hidden):")
            api_key = getpass.getpass("  Key: ").strip()
            if not api_key:
                raise SystemExit("❌ No key entered. Exiting.")
            print("  ✅ Key received.")

    else:
        # Ollama — no key needed
        print("\n  No API key required for local Ollama.")

    _divider()

    # ── Step 3: Model selection ──────────────────────────────────────
    default_model = meta["default_model"]
    print(f"\n  Model to use [default: {default_model}]")
    custom_model = input("  Model name (press Enter to use default): ").strip()
    model = custom_model if custom_model else default_model
    print(f"  ✅ Model: {model}")
    _divider()

    # ── Step 4: Instantiate ──────────────────────────────────────────
    provider_cls = meta["cls"]
    try:
        provider = provider_cls(model=model, api_key=api_key) if api_key else provider_cls(model=model)
        print(f"\n  ✅ Provider ready: {provider.name}  |  Model: {model}")
        print("=" * 50 + "\n")
        return provider

    except (ImportError, ValueError, ConnectionError) as e:
        print(f"\n  ❌ Setup failed: {e}")
        raise SystemExit("Could not initialise provider. Exiting.")