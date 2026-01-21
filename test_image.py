
import asyncio
from pump_tui.ui.image_renderer import render_image_to_ansi

async def main():
    # Use a real image URL from earlier logs or a known one
    url = "https://ipfs.io/ipfs/QmUumnmzZJ6dygYXvHj9mS7urzrt7U9aQL4qYuSE7JhXwk"
    print(f"Testing image rendering for: {url}")
    ansi = await render_image_to_ansi(url, width=60)
    print("\nRender Result:")
    print(ansi)
    print("\n--- End of Render ---")

if __name__ == "__main__":
    asyncio.run(main())
