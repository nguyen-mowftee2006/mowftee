"""Minimal interactive terminal runner for Mowftee Conversation Manager."""

from __future__ import annotations

import sys
from typing import Any

from mowftee.config import ConfigError, load_config
from mowftee.conversation import ConversationError, ConversationManager
from mowftee.llm import LLMError, OllamaLLMProvider


def run_interactive_chat(
    manager: ConversationManager,
    input_fn: Any = input,
    output_stream: Any = sys.stdout,
) -> None:
    """Run interactive text loop with ConversationManager."""
    print(
        "Mowftee Terminal Chat (gõ /exit hoặc /quit để thoát, /reset hoặc /clear để làm sạch lịch sử)",
        file=output_stream,
    )
    print("-" * 75, file=output_stream)

    while True:
        try:
            print("\nUser > ", end="", file=output_stream, flush=True)
            user_text = input_fn()
        except (EOFError, KeyboardInterrupt):
            print("\n[Thoát ứng dụng]", file=output_stream)
            break

        stripped = user_text.strip().casefold()
        if stripped in {"/exit", "/quit"}:
            print("[Thoát ứng dụng]", file=output_stream)
            break

        if stripped in {"/reset", "/clear"}:
            manager.clear_history()
            print("[Đã xoá lịch sử hội thoại]", file=output_stream)
            continue

        if not user_text.strip():
            continue

        print("Mowftee > ", end="", file=output_stream, flush=True)
        try:
            stream = manager.stream_chat(user_text)
            for chunk in stream:
                if chunk.delta:
                    print(chunk.delta, end="", file=output_stream, flush=True)
            print(file=output_stream)
        except KeyboardInterrupt:
            manager.cancel_current_turn()
            print("\n[Đã hủy lượt phản hồi]", file=output_stream)
        except (LLMError, ConversationError) as err:
            print(f"\n[Lỗi hội thoại: {err}]", file=output_stream)


def main() -> None:
    """Main CLI entry point."""
    try:
        config = load_config()
        provider = OllamaLLMProvider(config)
        if not provider.health_check():
            print("Lỗi: Dịch vụ Ollama không sẵn sàng (health_check = False)", file=sys.stderr)
            sys.exit(1)
        manager = ConversationManager(provider, config)
        run_interactive_chat(manager)
    except (ConfigError, LLMError, ConversationError) as exc:
        print(f"Lỗi khởi tạo Mowftee CLI: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
