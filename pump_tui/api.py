import json
import asyncio
import websockets
from typing import AsyncGenerator, Dict, Any, Optional

class PumpPortalClient:
    URI = "wss://pumpportal.fun/api/data"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.websocket = None
        self.running = False

    async def connect(self):
        """Establish the WebSocket connection."""
        try:
            print(f"Connecting to {self.URI}...")
            self.websocket = await websockets.connect(self.URI, open_timeout=10, ping_interval=None)
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
        import httpx
        url = "https://pumpportal.fun/api/create-wallet"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                # Returns: {"apiKey": "...", "privateKey": "...", "walletPublicKey": "..."}
                return response.json()
            else:
                raise Exception(f"Failed to create wallet: {response.text}")

    async def get_sol_balance(self, public_key: str) -> float:
        """Get SOL balance via RPC (using httpx/json-rpc)."""
        import httpx
        # Use a public RPC or user provided? Defaulting to a reliable public one.
        rpc_url = "https://api.mainnet-beta.solana.com" 
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(rpc_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "result" in data and "value" in data["result"]:
                    lamports = data["result"]["value"]
                    return lamports / 1_000_000_000 # Convert to SOL
            return 0.0

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
