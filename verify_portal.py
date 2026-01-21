import asyncio
from pump_tui.api import PumpPortalClient

async def verify_portal():
    print("--- Verifying PumpPortal WebSocket API ---")
    
    # Use the key from the request/app
    key = "8hw2peb2a92q0ya475gkgnbdb4nmev9r9134gjkra9m4pc3m6ttqebup9dw6rwvh98tq8ub389jpcckg91pn2t3he8r34wb298r6yvb465vn4c9nat75euhgf1n62nbd84rn0mu7a4ykuathppthqa8rpcnbt6d87jbuh7471672yj65d2p4h3natpqjpb3ax2mwrba8hkkuf8"
    client = PumpPortalClient(api_key=key)
    
    try:
        print("1. Connecting...")
        await client.connect()
        print("   Connected.")

        print("2. Subscribing to New Tokens...")
        await client.subscribe_new_tokens()
        
        print("3. Listening for 5 events...")
        count = 0
        async for event in client.listen():
            count += 1
            print(f"\nEvent {count}:")
            print(event)
            
            # Print specific fields if available
            if 'mint' in event:
                 print(f"   Mint: {event.get('mint')}")
            if 'name' in event:
                 print(f"   Name: {event.get('name')}")
            
            if count >= 5:
                break
        
        print("\n✅ Verification Successful: Received 5 events.")

    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(verify_portal())
