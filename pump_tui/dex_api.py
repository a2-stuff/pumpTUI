from typing import Dict, Any, Optional
import httpx
import logging

class DexScreenerClient:
    """Client for fetching data from DexScreener API."""
    
    BASE_URL = "https://api.dexscreener.com/latest/dex"
    
    async def get_token_price(self, chain_id: str, token_address: str) -> Optional[float]:
        """Fetch current price of a token in USD."""
        try:
            url = f"{self.BASE_URL}/tokens/{token_address}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    data = response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        # Find pair for specific chain if possible, or take first high liquidity one
                        # Filter by chainId matches
                        valid_pairs = [p for p in pairs if p.get("chainId") == chain_id]
                        if not valid_pairs:
                             valid_pairs = pairs
                             
                        # Sort by liquidity/volume to get most accurate price? 
                        # Usually the first one returned is the best match.
                        best_pair = valid_pairs[0]
                        price_usd = best_pair.get("priceUsd")
                        return float(price_usd) if price_usd else None
        except Exception as e:
            # logging.error(f"DexScreener fetch error: {e}")
            pass
        return None

    async def get_sol_price(self) -> Optional[float]:
        # Wrapped SOL address on Solana
        return await self.get_token_price("solana", "So11111111111111111111111111111111111111112")

    async def get_btc_price(self) -> Optional[float]:
        # Wrapped BTC on Solana, or fetch from a major pair like ETH/BTC? 
        # DexScreener is DEX specific. Fetching BTC price might be better via a stablecoin pair on a major chain.
        # Let's use WBTC on Ethereum or Solana.
        # WBTC on Solana (Portal): 3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh
        return await self.get_token_price("solana", "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh")

if __name__ == "__main__":
    import asyncio
    async def main():
        client = DexScreenerClient()
        print("Fetching prices...")
        sol = await client.get_sol_price()
        print(f"SOL: {sol}")
        btc = await client.get_btc_price()
        print(f"BTC: {btc}")
    
    asyncio.run(main())
