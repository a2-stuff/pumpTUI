import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig


class TradingClient:
    """Client for PumpPortal trading API and transaction management."""
    
    PUMPPORTAL_API_URL = "https://pumpportal.fun/api/trade-local"
    
    def __init__(self, rpc_url: str, wallet_private_key: str, api_key: Optional[str] = None):
        """
        Initialize trading client.
        
        Args:
            rpc_url: Solana RPC endpoint URL
            wallet_private_key: Base58 encoded private key for signing transactions
            api_key: Optional PumpPortal API key
        """
        self.rpc_url = rpc_url
        self.api_key = api_key
        try:
            self.keypair = Keypair.from_base58_string(wallet_private_key)
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")
    
    async def create_transaction(
        self,
        mint: str,
        action: str,
        amount: float,
        denominated_in_sol: bool,
        slippage: float = 10.0,
        priority_fee: float = 0.005,
        pool: str = "auto"
    ) -> Optional[bytes]:
        """
        Create a buy or sell transaction via PumpPortal API.
        
        Args:
            mint: Token contract address
            action: "buy" or "sell"
            amount: Amount of SOL or tokens to trade
            denominated_in_sol: True if amount is SOL, False if tokens
            slippage: Slippage percentage (default: 10%)
            priority_fee: Priority fee in SOL (default: 0.005)
            pool: Trading pool - "pump", "raydium", "bonk", or "auto" (default: "auto")
        
        Returns:
            Serialized transaction bytes or None if failed
        """
        request_data = {
            "publicKey": str(self.keypair.pubkey()),
            "action": action,
            "mint": mint,
            "denominatedInSol": bool(denominated_in_sol),
            "amount": amount, # Leave as is (can be float or "100%")
            "slippage": float(slippage),
            "priorityFee": float(priority_fee),
            "pool": pool
        }
        
        headers = {}
        if self.api_key:
            headers["api-key"] = self.api_key
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.PUMPPORTAL_API_URL,
                    json=request_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    error_msg = response.text if response.text else f"HTTP {response.status_code}"
                    # Log failure details for debugging
                    with open("error.log", "a") as f:
                        import json
                        f.write(f"\n--- PumpPortal API Error {datetime.now()} ---\n")
                        f.write(f"URL: {self.PUMPPORTAL_API_URL}\n")
                        f.write(f"Payload: {json.dumps(request_data)}\n")
                        f.write(f"Response: {error_msg}\n")
                    raise Exception(f"PumpPortal API error: {error_msg}")
                    
        except Exception as e:
            # Catch timeouts and other connection issues
            if "PumpPortal API error" not in str(e):
                with open("error.log", "a") as f:
                    f.write(f"\n--- Trade Creation Exception {datetime.now()} ---\n")
                    f.write(f"Error: {e}\n")
            raise Exception(f"Failed to create transaction: {e}")
    
    async def send_transaction(self, serialized_tx: bytes) -> str:
        """
        Sign and send a transaction to the Solana network.
        
        Args:
            serialized_tx: Serialized transaction bytes from PumpPortal
        
        Returns:
            Transaction signature
        """
        try:
            # Deserialize and sign the transaction
            tx = VersionedTransaction.from_bytes(serialized_tx)
            tx_message = tx.message
            signed_tx = VersionedTransaction(tx_message, [self.keypair])
            
            # Prepare RPC request
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            tx_payload = SendVersionedTransaction(signed_tx, config)
            
            # Send to RPC
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.rpc_url,
                    headers={"Content-Type": "application/json"},
                    content=tx_payload.to_json()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        return data["result"]
                    elif "error" in data:
                        err_data = data["error"]
                        msg = err_data.get("message", "")
                        if "AccountNotFound" in str(err_data) or "record of a prior credit" in msg:
                            raise Exception("Insufficient SOL: Your wallet has no balance or hasn't been funded.")
                        raise Exception(f"RPC error: {msg}")
                    else:
                        raise Exception(f"Unexpected response: {data}")
                else:
                    raise Exception(f"RPC HTTP error: {response.status_code}")
        except Exception as e:
            raise Exception(f"Failed to send transaction: {e}")
    
    async def execute_trade(
        self,
        mint: str,
        action: str,
        amount: float,
        denominated_in_sol: bool,
        slippage: float = 10.0,
        priority_fee: float = 0.005,
        pool: str = "auto"
    ) -> str:
        """
        Execute a complete trade: create transaction and send it.
        
        Args:
            mint: Token contract address
            action: "buy" or "sell"
            amount: Amount of SOL or tokens to trade
            denominated_in_sol: True if amount is SOL, False if tokens
            slippage: Slippage percentage (default: 10%)
            priority_fee: Priority fee in SOL (default: 0.005)
            pool: Trading pool (default: "auto")
        
        Returns:
            Transaction signature
        """
        # Create transaction
        serialized_tx = await self.create_transaction(
            mint=mint,
            action=action,
            amount=amount,
            denominated_in_sol=denominated_in_sol,
            slippage=slippage,
            priority_fee=priority_fee,
            pool=pool
        )
        
        if not serialized_tx:
            raise Exception("Failed to create transaction")
        
        # Sign and send transaction
        signature = await self.send_transaction(serialized_tx)
        return signature
    
    async def get_token_balance(self, mint: str) -> float:
        """
        Get user's token balance for a specific mint.
        
        Args:
            mint: Token contract address
        
        Returns:
            Token balance (raw amount, not UI amount)
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                str(self.keypair.pubkey()),
                {"mint": mint},
                {"encoding": "jsonParsed"}
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.rpc_url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "value" in data["result"]:
                        accounts = data["result"]["value"]
                        if accounts:
                            # Get the first token account's balance
                            token_amount = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]
                            return float(token_amount["amount"])
                    return 0.0
                else:
                    return 0.0
        except Exception:
            return 0.0
