"""Blockchain transaction fetcher using public APIs.

Retrieves and normalizes Bitcoin transaction data for addresses using
the public mempool.space REST API (with exponential backoff retries and graceful error handling).
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from tracing_engine.config import (
    BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    INITIAL_RETRY_DELAY,
    MAX_RETRIES,
    MEMPOOL_API_BASE,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _format_timestamp(block_time: Optional[int]) -> Optional[str]:
    """Convert a Unix epoch timestamp to an ISO-8601 UTC string.
    
    Args:
        block_time: Unix timestamp in seconds, or None if unconfirmed.
        
    Returns:
        ISO-8601 formatted string (e.g. '2026-09-01T10:08:32Z') or None.
    """
    if block_time is None or not isinstance(block_time, (int, float)):
        return None
    try:
        dt = datetime.fromtimestamp(block_time, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        logger.warning(f"Error parsing timestamp {block_time}: {e}")
        return None


def _normalize_transaction(raw_tx: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw mempool.space transaction payload into a standardized dictionary.
    
    Extracts transaction id, block timestamp, confirmation status, fee, and maps
    both inputs (vin) and outputs (vout) with amounts in satoshis and BTC.
    
    Args:
        raw_tx: Raw dictionary returned from mempool.space API.
        
    Returns:
        Clean, structured transaction dictionary.
    """
    tx_hash = raw_tx.get("txid", "")
    status = raw_tx.get("status", {})
    confirmed = status.get("confirmed", False)
    block_time = status.get("block_time")
    timestamp = _format_timestamp(block_time)
    fee_sat = raw_tx.get("fee", 0)

    # Process inputs (vin)
    inputs: List[Dict[str, Any]] = []
    for vin in raw_tx.get("vin", []):
        prevout = vin.get("prevout") or {}
        in_addr = prevout.get("scriptpubkey_address")
        in_sat = prevout.get("value", 0)
        inputs.append({
            "address": in_addr,
            "value_sat": in_sat,
            "value_btc": round(in_sat / 1e8, 8) if in_sat else 0.0,
            "is_coinbase": vin.get("is_coinbase", False),
            "txid": vin.get("txid"),
            "vout": vin.get("vout")
        })

    # Process outputs (vout)
    outputs: List[Dict[str, Any]] = []
    for vout in raw_tx.get("vout", []):
        out_addr = vout.get("scriptpubkey_address")
        out_sat = vout.get("value", 0)
        outputs.append({
            "address": out_addr,
            "value_sat": out_sat,
            "value_btc": round(out_sat / 1e8, 8) if out_sat else 0.0,
            "scriptpubkey_type": vout.get("scriptpubkey_type")
        })

    return {
        "tx_hash": tx_hash,
        "timestamp": timestamp,
        "block_time": block_time,
        "confirmed": confirmed,
        "fee_sat": fee_sat,
        "fee_btc": round(fee_sat / 1e8, 8) if fee_sat else 0.0,
        "inputs": inputs,
        "outputs": outputs
    }


def get_transactions(address: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """Fetch and normalize all confirmed/unconfirmed transactions for a given Bitcoin address.
    
    Calls mempool.space's public endpoint: GET /api/address/{address}/txs.
    Implements exponential backoff on HTTP 429 (Rate Limit) and 5xx server errors.
    Gracefully handles invalid addresses (HTTP 400), non-existent addresses (HTTP 404),
    and network connection timeouts by returning an empty list instead of crashing.
    
    Args:
        address: Base58 or Bech32 Bitcoin address string.
        session: Optional persistent requests.Session instance for connection pooling.
        
    Returns:
        List of normalized transaction dictionaries. Empty list if address has no transactions
        or if an unrecoverable request error occurs.
    """
    clean_address = address.strip() if address else ""
    if not clean_address:
        logger.warning("Empty Bitcoin address provided to get_transactions().")
        return []

    url = f"{MEMPOOL_API_BASE}/address/{clean_address}/txs"
    http = session or requests

    retry_delay = INITIAL_RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = http.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            
            # Rate limit or server error -> backoff retry
            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    f"mempool.space API returned HTTP {response.status_code} for address {clean_address}. "
                    f"Attempt {attempt}/{MAX_RETRIES}. Retrying in {retry_delay:.2f}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= BACKOFF_FACTOR
                continue

            # Bad Request (invalid address) or Not Found
            if response.status_code == 400:
                logger.warning(f"Invalid Bitcoin address format: {clean_address} (HTTP 400)")
                return []
            if response.status_code == 404:
                logger.info(f"Bitcoin address not found on mempool.space: {clean_address} (HTTP 404)")
                return []

            response.raise_for_status()

            raw_txs = response.json()
            if not isinstance(raw_txs, list):
                logger.warning(f"Unexpected response format from mempool.space for {clean_address}: {type(raw_txs)}")
                return []

            return [_normalize_transaction(tx) for tx in raw_txs if isinstance(tx, dict)]

        except requests.exceptions.Timeout:
            logger.warning(
                f"Timeout requesting mempool.space for address {clean_address}. "
                f"Attempt {attempt}/{MAX_RETRIES}."
            )
            if attempt < MAX_RETRIES:
                time.sleep(retry_delay)
                retry_delay *= BACKOFF_FACTOR
            else:
                logger.error(f"Max retries reached on timeout for {clean_address}.")
                return []

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Network exception connecting to mempool.space for {clean_address}: {e}. "
                f"Attempt {attempt}/{MAX_RETRIES}."
            )
            if attempt < MAX_RETRIES:
                time.sleep(retry_delay)
                retry_delay *= BACKOFF_FACTOR
            else:
                logger.error(f"Unrecoverable network error for {clean_address}: {e}")
                return []

        except ValueError as e:
            logger.error(f"Failed to parse JSON response from mempool.space for {clean_address}: {e}")
            return []

    logger.error(f"Failed to fetch transactions for {clean_address} after {MAX_RETRIES} attempts.")
    return []
