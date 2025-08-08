#!/usr/bin/env python3
"""Test script for KCar session-based scraping"""

import asyncio
import logging
from services.kcar_session_service import KCarSessionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_kcar_session():
    """Test KCar session service"""
    session_service = KCarSessionService()
    
    try:
        print("Initializing session...")
        await session_service.initialize()
        
        print("\nSearching for cars...")
        result = await session_service.search_cars_html(
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
        else:
            print("\nNo cars found - this might be due to:")
            print("  1. KCar requiring Korean IP address")
            print("  2. Anti-bot protection")
            print("  3. Changed HTML structure")
            
        if result.get('error'):
            print(f"\nError details: {result['error']}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nCleaning up...")
        await session_service.cleanup()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(test_kcar_session())