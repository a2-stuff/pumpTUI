import json
import asyncio
import websockets
import httpx
from typing import AsyncGenerator, Dict, Any, Optional
from .helpers import get_http_client

class PumpPortalClient:
    URI = "wss://pumpportal.fun/api/data"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.websocket = None
        self.running = False

    async def connect(self):
        """Establish the WebSocket connection."""
        if self.websocket and not self.websocket.closed:
            return  # Reuse existing connection

        try:
            print(f"Connecting to {self.URI}...")
            self.websocket = await websockets.connect(self.URI, open_timeout=10, ping_interval=2, ping_timeout=5)
            self.running = True
            print("Connected to PumpPortal WebSocket.")
        except Exception as e:
            print(f"Failed to connect: {e}")
            raise

    async def subscribe_new_tokens(self):
        """Subscribe to token creation events."""
        if not self.websocket:
            await self.connect()
        
        payload = {
            "method": "subscribeNewToken"
        }
        await self.websocket.send(json.dumps(payload))
        print("Subscribed to New Tokens.")

    async def subscribe_token_trade(self, keys: list[str]):
        """Subscribe to trades for specific tokens."""
        if not self.websocket:
            await self.connect()
        
        payload = {
            "method": "subscribeTokenTrade",
            "keys": keys
        }
        await self.websocket.send(json.dumps(payload))
        # print(f"Subscribed to trades for {len(keys)} tokens.")

    async def create_wallet(self) -> Dict[str, str]:
        """Generate a new wallet via PumpPortal API."""
        url = "https://pumpportal.fun/api/create-wallet"
        client = get_http_client()
        response = await client.get(url)
        if response.status_code == 200:
            # Returns: {"apiKey": "...", "privateKey": "...", "walletPublicKey": "..."}
            return response.json()
        else:
            raise Exception(f"Failed to create wallet: {response.text}")

    async def get_sol_balance(self, public_key: str) -> float:
        """Get SOL balance via RPC."""
        from .config import config
        rpc_url = config.rpc_url
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key]
        }
        
        client = get_http_client()
        try:
            response = await client.post(rpc_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "result" in data and "value" in data["result"]:
                    lamports = data["result"]["value"]
                    return lamports / 1_000_000_000
        except:
            pass
        return 0.0

    async def get_batch_balances(self, public_keys: list[str]) -> Dict[str, float]:
        """Get SOL balances for multiple wallets in one RPC call."""
        if not public_keys:
            return {}
            
        from .config import config
        rpc_url = config.rpc_url
        
        # Build batch request
        # JSON-RPC batch is an array of requests
        batch_payload = []
        for idx, pub in enumerate(public_keys):
            batch_payload.append({
                "jsonrpc": "2.0",
                "id": idx,
                "method": "getBalance",
                "params": [pub]
            })
            
        results = {}
        client = get_http_client()
        try:
            response = await client.post(rpc_url, json=batch_payload)
            if response.status_code == 200:
                data = response.json()
                # data is a list of responses corresponding to requests
                if isinstance(data, list):
                    for res in data:
                        req_id = res.get("id")
                        if req_id is not None and 0 <= req_id < len(public_keys):
                            pub = public_keys[req_id]
                            if "result" in res and "value" in res["result"]:
                                lamports = res["result"]["value"]
                                results[pub] = lamports / 1_000_000_000
                            else:
                                results[pub] = 0.0
        except Exception as e:
            print(f"Batch balance error: {e}")
            pass
                
        return results

    async def get_tx_count(self, public_key: str) -> int:
        """Get transaction count for a wallet."""
        from .config import config
        rpc_url = config.rpc_url
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [public_key, {"limit": 1000}]
        }
        
        client = get_http_client()
        try:
            response = await client.post(rpc_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return len(data["result"])
        except:
            pass
        return 0

    async def listen(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield messages from the WebSocket."""
        if not self.websocket:
            await self.connect()

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    yield data
                except json.JSONDecodeError:
                    print(f"Failed to decode message: {message}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")
            self.running = False

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.running = False
            print("PumpPortal Connection Closed.")
