"""Unit tests for LLM client and rate limiter."""

import asyncio
import unittest
from pydantic import BaseModel

from app.llm.client import MockLLMClient, LLMResponse
from app.llm.rate_limiter import RateLimiter
from app.schemas import PersonaOutput


class TestLLM(unittest.IsolatedAsyncioTestCase):
    async def test_mock_client_generate(self):
        client = MockLLMClient(default_model="gemini-mock")
        response = await client.generate(
            prompt="Halo apa kabar?",
            system_instruction="Kamu penyiar radio.",
        )
        self.assertIsInstance(response, LLMResponse)
        self.assertTrue(len(response.raw) > 0)
        self.assertGreater(response.output_tokens, 0)
        self.assertGreaterEqual(response.latency_ms, 0)

    async def test_mock_client_structured_output(self):
        client = MockLLMClient(default_model="gemini-mock")
        response = await client.generate(
            prompt="Sapa pendengar",
            response_schema=PersonaOutput,
        )
        self.assertIsInstance(response, LLMResponse)
        self.assertIn("text", response.parsed)
        self.assertIn("emotion", response.parsed)

    async def test_rate_limiter_acquire(self):
        limiter = RateLimiter(requests_per_minute=60, name="test")
        wait_time = await limiter.acquire()
        self.assertEqual(wait_time, 0.0)


if __name__ == "__main__":
    unittest.main()
