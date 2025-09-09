"""
Encar History Service
Service for fetching car history data from Encar's history API
"""

import asyncio
import logging
import random
import time
from typing import Dict, Any, Optional
import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)


class EncarHistoryService:
    """
    Encar History service for fetching car manufacturing and registration data
    
    Provides functionality for:
    - Fetching car history from Encar's history page
    - Handling proxy rotation and session management
    - Rate limiting and error handling
    - Session management with Korean site requirements
    """

    def __init__(self, proxy_client=None):
        self.proxy_client = proxy_client
        self.base_url = "https://car.encar.com"
        
        # Session management
        self.session = requests.Session()
        self._setup_session()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
    
    def _setup_session(self):
        """Setup session with appropriate headers for Encar history API"""
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Referer': 'https://fem.encar.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
        })
        
        # Use proxy if available
        if self.proxy_client and hasattr(self.proxy_client, 'session'):
            self.session.proxies = self.proxy_client.session.proxies
    
    def _rate_limit(self):
        """Rate limiting to avoid being blocked"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def get_car_history(self, car_id: str) -> Optional[str]:
        """
        Fetch car history HTML from Encar's history API
        
        Args:
            car_id: The car ID to fetch history for
            
        Returns:
            HTML content as string or None if failed
        """
        try:
            self._rate_limit()
            
            url = f"{self.base_url}/history"
            params = {'carId': car_id}
            
            logger.info(f"Fetching car history for ID: {car_id}")
            
            # Make request with retry logic
            response = await self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                logger.info(f"Successfully fetched history for car {car_id}")
                return response.text
            else:
                logger.error(f"Failed to fetch history for car {car_id}: HTTP {response.status_code if response else 'No response'}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching car history for {car_id}: {str(e)}")
            return None
    
    async def _make_request_with_retry(self, url: str, params: Dict[str, str], max_retries: int = 3) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and proxy rotation
        
        Args:
            url: URL to request
            params: Query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            requests.Response object or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                # Add random delay between retries
                if attempt > 0:
                    delay = random.uniform(1, 3) * (attempt + 1)
                    logger.info(f"Retry attempt {attempt + 1} after {delay:.1f}s delay")
                    await asyncio.sleep(delay)
                
                # Make the request
                response = self.session.get(
                    url,
                    params=params,
                    timeout=(10, 30),  # (connect timeout, read timeout)
                    allow_redirects=True
                )
                
                # Check for common error status codes
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden received (attempt {attempt + 1})")
                    if self.proxy_client and hasattr(self.proxy_client, '_rotate_proxy'):
                        self.proxy_client._rotate_proxy()
                        self.session.proxies = self.proxy_client.session.proxies
                    continue
                elif response.status_code == 429:
                    logger.warning(f"429 Too Many Requests (attempt {attempt + 1})")
                    # Longer delay for rate limiting
                    await asyncio.sleep(random.uniform(5, 10))
                    continue
                elif response.status_code >= 500:
                    logger.warning(f"Server error {response.status_code} (attempt {attempt + 1})")
                    continue
                
                # Success or client error (4xx) that won't be fixed by retry
                return response
                
            except (RequestException, Timeout) as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} attempts failed for {url}")
                    return None
                continue
        
        return None
    
    def close_session(self):
        """Close the session to clean up resources"""
        if self.session:
            self.session.close()