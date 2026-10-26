#!/usr/bin/env python3
"""
Verify that your environment is correctly set up for the CrewAI BPO Innovation Challenge.
Run this script after following the setup instructions in the README.
"""

import sys
import os

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def passed(msg: str):
    print(f"  {GREEN}✓ PASS{RESET}  {msg}")

def failed(msg: str):
    print(f"  {RED}✗ FAIL{RESET}  {msg}")

def warn(msg: str):
    print(f"  {YELLOW}⚠ WARN{RESET}  {msg}")

def main():
    print(f"\n{BOLD}CrewAI BPO Challenge — Environment Verification{RESET}\n")
    print("=" * 50)

    all_passed = True

    # 1. Python version check
    print(f"\n{BOLD}1. Python Version{RESET}")
    major, minor = sys.version_info.major, sys.version_info.minor
    if major >= 3 and minor >= 10:
        passed(f"Python {major}.{minor} (>= 3.10 required)")
    else:
        failed(f"Python {major}.{minor} — version 3.10 or higher is required")
        all_passed = False

    # 2. Required packages
    print(f"\n{BOLD}2. Required Packages{RESET}")
    packages = {
        "crewai": "crewai",
        "pydantic": "pydantic",
        "dotenv": "dotenv (python-dotenv)",
        "litellm": "litellm",
    }
    for import_name, display_name in packages.items():
        try:
            __import__(import_name)
            passed(f"{display_name}")
        except ImportError:
            failed(f"{display_name} — run: uv pip install -r requirements.txt")
            all_passed = False

    # 3. .env file
    print(f"\n{BOLD}3. Environment File{RESET}")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        passed(".env file exists")
    else:
        failed(".env file not found — run: cp .env.example .env")
        all_passed = False

    # 4. API key configured
    print(f"\n{BOLD}4. API Key Configuration{RESET}")
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    api_key = os.environ.get("LITELLM_API_KEY", "")
    base_url = os.environ.get("LITELLM_BASE_URL", "")
    model_name = os.environ.get("MODEL_NAME", "")

    if api_key and api_key != "your-api-key-here":
        passed("LITELLM_API_KEY is set")
    elif api_key == "your-api-key-here":
        failed("LITELLM_API_KEY is still the placeholder — update it in .env")
        all_passed = False
    else:
        failed("LITELLM_API_KEY is not set — add it to your .env file")
        all_passed = False

    if base_url and base_url != "your-litellm-endpoint-here":
        passed(f"LITELLM_BASE_URL is set")
    else:
        warn("LITELLM_BASE_URL not configured — set it in .env")

    if model_name:
        passed(f"MODEL_NAME = {model_name}")
    else:
        warn("MODEL_NAME not set — defaulting to gemini/gemini-2.5-flash")

    # 5. LLM connectivity test
    print(f"\n{BOLD}5. LLM Connectivity{RESET}")
    if not api_key or api_key == "your-api-key-here":
        warn("Skipping LLM test — API key not configured yet")
    else:
        try:
            import litellm
            response = litellm.completion(
                model=model_name or "gemini/gemini-2.5-flash",
                messages=[{"role": "user", "content": "Say 'hello' in one word."}],
                api_key=api_key,
                api_base=base_url if base_url and base_url != "your-litellm-endpoint-here" else None,
                #max_tokens=10,
            )
            reply = response.choices[0].message.content.strip()
            passed(f"LLM responded: \"{reply}\"")
        except Exception as e:
            failed(f"LLM call failed: {e}")
            all_passed = False

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print(f"\n{GREEN}{BOLD}All checks passed! You're ready to build. 🚀{RESET}\n")
    else:
        print(f"\n{RED}{BOLD}Some checks failed. Fix the issues above and re-run this script.{RESET}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
