from app.connectors.openai_client import OpenAIClient


def test_openai_cache_key_is_stable_and_content_sensitive():
    key1 = OpenAIClient.cache_key("prompt", "hash1")
    key2 = OpenAIClient.cache_key("prompt", "hash1")
    key3 = OpenAIClient.cache_key("prompt", "hash2")
    assert key1 == key2
    assert key1 != key3
