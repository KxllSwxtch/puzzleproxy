import requests
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.currency import CurrencyRateResponse, CurrencyRateData, NaverApiResponse

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for fetching currency rates from external APIs"""

    def __init__(self):
        self.fallback_rate = 16.54  # Standardized fallback rate
        self.adjustment = -0.80     # Rate adjustment as specified

    async def fetch_naver_rub_rate(self) -> CurrencyRateResponse:
        """
        Fetch RUB/KRW rate directly from Naver API
        This bypasses browser CORS restrictions by making server-to-server calls
        """
        try:
            logger.info("🔄 Fetching RUB/KRW rate from Naver API...")

            # Exact headers from the provided Python example
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5',
                'origin': 'https://search.naver.com',
                'priority': 'u=1, i',
                'referer': 'https://search.naver.com/',
                'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            }

            # Exact parameters from the provided Python example
            params = {
                'key': 'calculator',
                'pkid': '141',
                'q': '환율',
                'where': 'm',
                'u1': 'keb',
                'u6': 'standardUnit',
                'u7': '0',
                'u3': 'RUB',
                'u4': 'KRW',
                'u8': 'down',
                'u2': '1',
            }

            # Make the API call with timeout
            response = requests.get(
                'https://ts-proxy.naver.com/content/qapirender.nhn',
                params=params,
                headers=headers,
                timeout=30
            )

            if not response.ok:
                logger.error(f"❌ Naver API returned status {response.status_code}: {response.text}")
                return self._create_fallback_response(f"HTTP error {response.status_code}")

            # Parse JSON response
            try:
                data = response.json()
            except Exception as json_error:
                logger.error(f"❌ Failed to parse JSON response: {json_error}")
                return self._create_fallback_response(f"Invalid JSON response: {json_error}")

            # Validate response structure (based on rubkrwrate.json example)
            if not isinstance(data, dict) or 'country' not in data:
                logger.error(f"❌ Invalid response structure: {data}")
                return self._create_fallback_response("Invalid API response structure")

            country = data.get('country', [])
            if not isinstance(country, list) or len(country) < 2:
                logger.error(f"❌ Invalid country array: {country}")
                return self._create_fallback_response("Invalid country data in response")

            # Extract rate from country[1].value (KRW rate)
            try:
                rate_text = country[1].get('value', '')
                original_rate = float(rate_text)
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"❌ Failed to extract rate: {e}")
                return self._create_fallback_response(f"Failed to extract rate: {e}")

            if original_rate <= 0:
                logger.error(f"❌ Invalid rate value: {original_rate}")
                return self._create_fallback_response(f"Invalid rate value: {original_rate}")

            # Apply adjustment: subtract 0.80 and round to 2 decimal places
            adjusted_rate = round(original_rate + self.adjustment, 2)

            logger.info(f"✅ Successfully fetched RUB/KRW rate: {original_rate} -> {adjusted_rate} (adjusted {self.adjustment})")

            return CurrencyRateResponse(
                success=True,
                data=CurrencyRateData(
                    rubToKrwRate=adjusted_rate,
                    originalRate=original_rate
                ),
                source="naver",
                lastUpdated=datetime.utcnow().isoformat() + "Z"
            )

        except requests.exceptions.Timeout:
            logger.error("❌ Timeout while fetching from Naver API")
            return self._create_fallback_response("Request timeout")

        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error while fetching from Naver API")
            return self._create_fallback_response("Connection error")

        except Exception as e:
            logger.error(f"❌ Unexpected error while fetching from Naver API: {e}")
            return self._create_fallback_response(f"Unexpected error: {str(e)}")

    def _create_fallback_response(self, error_message: str) -> CurrencyRateResponse:
        """Create a fallback response when the API call fails"""
        logger.warning(f"🔄 Using fallback rate {self.fallback_rate} due to error: {error_message}")

        return CurrencyRateResponse(
            success=False,
            data=CurrencyRateData(
                rubToKrwRate=self.fallback_rate,
                originalRate=None
            ),
            source="fallback",
            lastUpdated=datetime.utcnow().isoformat() + "Z",
            error=error_message
        )


# Singleton instance
currency_service = CurrencyService()