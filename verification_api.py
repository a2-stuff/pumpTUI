import asyncio
from pump_tui.api import PumpFunClient

async def verify_api():
    print("Verifying API...")
    client = PumpFunClient()
    try:
        print("Fetching New Tokens...")
        new_tokens = await client.get_new_tokens(limit=5)
        print(f"Success: Fetched {len(new_tokens)} new tokens.")
        if new_tokens:
            print(f"Sample: {new_tokens[0].get('name')} ({new_tokens[0].get('mint')})")

        print("Fetching Live Tokens...")
        live_tokens = await client.get_live_tokens(limit=5)
        print(f"Success: Fetched {len(live_tokens)} live tokens.")
        
        # Depending on API response structure, we might need to adjust key access during real usage.
        # This script helps confirm the structure.

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"API Verification Failed: {e!r}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(verify_api())
