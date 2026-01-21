import httpx
from typing import Optional, Dict, Any

async def fetch_token_metadata(uri: str) -> Optional[Dict[str, Any]]:
    """Fetch token metadata from the given URI."""
    if not uri:
        return None
    
    # Use a faster IPFS gateway if it's an ipfs:// or ipfs.io link
    if "ipfs.io/ipfs/" in uri:
        uri = uri.replace("ipfs.io/ipfs/", "cf-ipfs.com/ipfs/")
    elif uri.startswith("ipfs://"):
        uri = uri.replace("ipfs://", "https://cf-ipfs.com/ipfs/")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(uri, timeout=10.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}
