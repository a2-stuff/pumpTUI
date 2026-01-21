
import httpx
from PIL import Image
import io
import asyncio

async def render_image_to_ansi(url: str, width: int = 30) -> str:
    """
    Downloads an image and converts it to a string of block characters with ANSI colors.
    Uses the upper-half block char '▀' to fit two vertical pixels into one terminal line.
    """
    if not url:
        return ""
    
    # Extract CID if it's an IPFS link for fallback
    cid = None
    if "/ipfs/" in url:
        cid = url.split("/ipfs/")[-1]
    elif url.startswith("ipfs://"):
        cid = url.replace("ipfs://", "")

    if cid:
        gateways = [
            f"https://cf-ipfs.com/ipfs/{cid}",
            f"https://dweb.link/ipfs/{cid}", 
            f"https://ipfs.io/ipfs/{cid}",
            f"https://gateway.pinata.cloud/ipfs/{cid}"
        ]
    else:
        gateways = [url]

    img_data = None
    async with httpx.AsyncClient() as client:
        for gw_url in gateways:
            try:
                response = await client.get(gw_url, timeout=5.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    img_data = response.read()
                    break
            except:
                continue
    
    if not img_data:
        return "[red]Failed to download image[/]"
    
    try:
        img = Image.open(io.BytesIO(img_data))
        img = img.convert("RGB")
        
        # To get a square look in terminal with ▀ blocks:
        # 1 character width is approx equal to 2 pixels vertical (1 char height).
        # So for a square, pixel_width should equal pixel_height.
        height = width # Keep it square in pixel count
        
        # Ensure even height for vertical pairs
        if height % 2 != 0:
            height += 1
            
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        pixels = img.load()
        result = []
        
        for y in range(0, height, 2):
            line = []
            for x in range(width):
                r1, g1, b1 = pixels[x, y]
                r2, g2, b2 = pixels[x, y + 1] if y + 1 < height else (0, 0, 0)
                
                # Upper half block: Foreground = Top pixel, Background = Bottom pixel
                line.append(f"\x1b[38;2;{r1};{g1};{b1};48;2;{r2};{g2};{b2}m▀")
            
            result.append("".join(line) + "\x1b[0m")
            
        return "\n".join(result)
        
    except Exception as e:
        return f"[red]Error rendering image: {e}[/]"

if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        loop = asyncio.get_event_loop()
        print(loop.run_until_complete(render_image_to_ansi(test_url)))
