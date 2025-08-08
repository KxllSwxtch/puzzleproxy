#!/usr/bin/env python3
"""Test script for KCar browser automation"""

import asyncio
import logging
from services.kcar_browser_service import KCarBrowserService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_kcar_browser():
    """Test KCar browser service"""
    browser_service = KCarBrowserService()
    
    try:
        print("Initializing browser...")
        await browser_service.initialize()
        
        print("\nSearching for cars...")
        result = await browser_service.search_cars(
            manufacturer_code=None,  # Get all manufacturers
            page_num=1,
            limit=5
        )
        
        print(f"\nSearch result:")
        print(f"Success: {result.get('success')}")
        print(f"Total cars found: {result.get('total')}")
        print(f"Cars returned: {len(result.get('data', []))}")
        
        if result.get('data'):
            print("\nFirst car details:")
            first_car = result['data'][0]
            for key, value in first_car.items():
                print(f"  {key}: {value}")
                
        print("\nGetting manufacturers...")
        manufacturers = await browser_service.get_manufacturers()
        print(f"Found {len(manufacturers)} manufacturers")
        if manufacturers:
            print("First 5 manufacturers:")
            for mfr in manufacturers[:5]:
                print(f"  - {mfr.get('mnuftrNm')} (code: {mfr.get('mnuftrCd')})")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nCleaning up...")
        await browser_service.cleanup()
        print("Done!")

if __name__ == "__main__":
    # First install playwright browsers if not already installed
    import subprocess
    print("Installing Playwright browsers...")
    subprocess.run(["playwright", "install", "chromium"], check=False)
    
    # Run the test
    asyncio.run(test_kcar_browser())