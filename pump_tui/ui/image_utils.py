import httpx
from typing import Optional, Dict, Any

async def fetch_token_metadata(uri: str) -> Optional[Dict[str, Any]]:
    """Fetch token metadata from the given URI with gateway fallback."""
    if not uri:
        return None
    
    # Extract CID if it's an IPFS link
    cid = None
    if "/ipfs/" in uri:
        cid = uri.split("/ipfs/")[-1]
    elif uri.startswith("ipfs://"):
        cid = uri.replace("ipfs://", "")

    if cid:
        # Multiple gateways to try if Pinata is ratelimited (429)
        gateways = [
            f"https://gateway.pinata.cloud/ipfs/{cid}",
            f"https://cf-ipfs.com/ipfs/{cid}",
            f"https://ipfs.io/ipfs/{cid}",
            f"https://gateway.ipfs.io/ipfs/{cid}"
        ]
        
        last_error = "Unknown error"
        async with httpx.AsyncClient() as client:
            for gw_url in gateways:
                try:
                    response = await client.get(gw_url, timeout=7.0)
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:
                        last_error = "429 Rate Limited"
                        continue # Try next gateway
                    else:
                        last_error = f"HTTP {response.status_code}"
                except Exception as e:
                    last_error = str(e)
                    continue
        return {"error": f"All gateways failed: {last_error}"}

    # Regular URL fetch
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(uri, timeout=10.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}
