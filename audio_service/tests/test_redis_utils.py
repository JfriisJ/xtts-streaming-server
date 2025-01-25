from unittest.mock import patch

@patch("redis.StrictRedis")
def test_redis_interaction(mock_redis):
    redis_instance = mock_redis.return_value
    redis_instance.get.return_value = "mock_value"
    result = redis_instance.get("some_key")
    assert result == "mock_value"
