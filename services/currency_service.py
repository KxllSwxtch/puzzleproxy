import requests
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.currency import (
    CurrencyRateResponse,
    CurrencyRateData,
    UsdCurrencyRateResponse,
    UsdCurrencyRateData,
    NaverApiResponse
)

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for fetching currency rates from external APIs"""

    def __init__(self):
        self.fallback_rub_rate = 16.54   # Standardized fallback rate for RUB
        self.fallback_usd_rate = 1375.50 # Standardized fallback rate for USD
        self.rub_adjustment = -0.80      # Rate adjustment for RUB as specified
        self.usd_adjustment = -10.0      # Rate adjustment for USD (configurable)

    def fetch_naver_rub_rate(self) -> CurrencyRateResponse:
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
                'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
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
                timeout=5  # Reduced from 30 to 5 seconds to prevent hanging
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
                # Remove commas from the rate string (e.g., "16.54" or "1,466.10" -> "1466.10")
                rate_text_clean = rate_text.replace(',', '')
                original_rate = float(rate_text_clean)
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"❌ Failed to extract rate: {e}")
                return self._create_fallback_response(f"Failed to extract rate: {e}")

            if original_rate <= 0:
                logger.error(f"❌ Invalid rate value: {original_rate}")
                return self._create_fallback_response(f"Invalid rate value: {original_rate}")

            # Apply adjustment: subtract 0.80 and round to 2 decimal places
            adjusted_rate = round(original_rate + self.rub_adjustment, 2)

            logger.info(f"✅ Successfully fetched RUB/KRW rate: {original_rate} -> {adjusted_rate} (adjusted {self.rub_adjustment})")

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
        logger.warning(f"🔄 Using fallback RUB rate {self.fallback_rub_rate} due to error: {error_message}")

        return CurrencyRateResponse(
            success=False,
            data=CurrencyRateData(
                rubToKrwRate=self.fallback_rub_rate,
                originalRate=None
            ),
            source="fallback",
            lastUpdated=datetime.utcnow().isoformat() + "Z",
            error=error_message
        )

    def fetch_naver_usd_rate(self) -> UsdCurrencyRateResponse:
        """
        Fetch USD/KRW rate directly from Naver API
        This bypasses browser CORS restrictions by making server-to-server calls
        """
        try:
            logger.info("🔄 Fetching USD/KRW rate from Naver API...")

            # Same headers as RUB rate
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5',
                'origin': 'https://search.naver.com',
                'priority': 'u=1, i',
                'referer': 'https://search.naver.com/',
                'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            }

            # Parameters for USD/KRW conversion
            params = {
                'key': 'calculator',
                'pkid': '141',
                'q': '환율',
                'where': 'm',
                'u1': 'keb',
                'u6': 'standardUnit',
                'u7': '0',
                'u3': 'USD',  # From currency
                'u4': 'KRW',  # To currency
                'u8': 'down',
                'u2': '1',
            }

            # Make the API call with timeout
            response = requests.get(
                'https://ts-proxy.naver.com/content/qapirender.nhn',
                params=params,
                headers=headers,
                timeout=5  # Reduced from 30 to 5 seconds to prevent hanging
            )

            if not response.ok:
                logger.error(f"❌ Naver API returned status {response.status_code}: {response.text}")
                return self._create_usd_fallback_response(f"HTTP error {response.status_code}")

            # Parse JSON response
            try:
                data = response.json()
            except Exception as json_error:
                logger.error(f"❌ Failed to parse JSON response: {json_error}")
                return self._create_usd_fallback_response(f"Invalid JSON response: {json_error}")

            # Validate response structure
            if not isinstance(data, dict) or 'country' not in data:
                logger.error(f"❌ Invalid response structure: {data}")
                return self._create_usd_fallback_response("Invalid API response structure")

            country = data.get('country', [])
            if not isinstance(country, list) or len(country) < 2:
                logger.error(f"❌ Invalid country array: {country}")
                return self._create_usd_fallback_response("Invalid country data in response")

            # Extract rate from country[1].value (KRW rate)
            try:
                rate_text = country[1].get('value', '')
                # Remove commas from the rate string (e.g., "1,466.10" -> "1466.10")
                rate_text_clean = rate_text.replace(',', '')
                original_rate = float(rate_text_clean)
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"❌ Failed to extract rate: {e}")
                return self._create_usd_fallback_response(f"Failed to extract rate: {e}")

            if original_rate <= 0:
                logger.error(f"❌ Invalid rate value: {original_rate}")
                return self._create_usd_fallback_response(f"Invalid rate value: {original_rate}")

            # Apply adjustment: subtract 10.0 and round to 2 decimal places
            adjusted_rate = round(original_rate + self.usd_adjustment, 2)

            logger.info(f"✅ Successfully fetched USD/KRW rate: {original_rate} -> {adjusted_rate} (adjusted {self.usd_adjustment})")

            return UsdCurrencyRateResponse(
                success=True,
                data=UsdCurrencyRateData(
                    usdToKrwRate=adjusted_rate,
                    originalRate=original_rate
                ),
                source="naver",
                lastUpdated=datetime.utcnow().isoformat() + "Z"
            )

        except requests.exceptions.Timeout:
            logger.error("❌ Timeout while fetching USD rate from Naver API")
            return self._create_usd_fallback_response("Request timeout")

        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error while fetching USD rate from Naver API")
            return self._create_usd_fallback_response("Connection error")

        except Exception as e:
            logger.error(f"❌ Unexpected error while fetching USD rate from Naver API: {e}")
            return self._create_usd_fallback_response(f"Unexpected error: {str(e)}")

    def _create_usd_fallback_response(self, error_message: str) -> UsdCurrencyRateResponse:
        """Create a fallback response for USD rate when the API call fails"""
        logger.warning(f"🔄 Using fallback USD rate {self.fallback_usd_rate} due to error: {error_message}")

        return UsdCurrencyRateResponse(
            success=False,
            data=UsdCurrencyRateData(
                usdToKrwRate=self.fallback_usd_rate,
                originalRate=None
            ),
            source="fallback",
            lastUpdated=datetime.utcnow().isoformat() + "Z",
            error=error_message
        )


# Singleton instance
currency_service = CurrencyService()