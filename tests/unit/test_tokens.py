"""
tests/unit/test_tokens.py — Basic tests for token counting
"""

from src.utils.tokens import count_tokens, count_messages_tokens

def test_count_tokens_empty():
    assert count_tokens("") == 0

def test_count_tokens_basic():
    text = "Hello, world! This is a test."
    # Should be roughly 7-8 tokens depending on the tokenizer
    count = count_tokens(text)
    assert count > 0

def test_count_messages_tokens():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
    # tiktoken might count this as exactly 8 tokens, or more with role overhead
    count = count_messages_tokens(messages)
    assert count >= 8
