"""Configuration settings for the SIH26182 Tracing Engine.

Defines API endpoints, network timeouts, retry policies, and default parameters.
"""

from typing import Dict

# Mempool.space Public REST API base URL (Default API)
# No API key required for standard endpoints.
MEMPOOL_API_BASE: str = "https://mempool.space/api"

# Blockchair API base URL (Secondary fallback endpoint)
BLOCKCHAIR_API_BASE: str = "https://api.blockchair.com/bitcoin"

# Network & Retry Settings
REQUEST_TIMEOUT: int = 15  # seconds per HTTP request
MAX_RETRIES: int = 3       # maximum retry attempts for transient errors
INITIAL_RETRY_DELAY: float = 1.0  # seconds for exponential backoff base
BACKOFF_FACTOR: float = 2.0       # multiplier for backoff calculation

# Default Tracing Parameters
DEFAULT_MAX_HOPS: int = 4  # BFS exploration depth limit (hackathon prototype)

# User-Agent header for public API etiquette
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": "SIH26182-CryptoTraceAttribution/1.0 (Smart India Hackathon Prototype)"
}
