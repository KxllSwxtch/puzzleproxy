"""
Service layer for Encar vehicle record/accident history data
"""
import logging
from typing import Optional, Union
from urllib.parse import quote
from schemas.encar_record import EncarRecordResponse, EncarRecordErrorResponse

logger = logging.getLogger(__name__)


class EncarRecordService:
    """Service for fetching vehicle accident/insurance records from Encar"""

    def __init__(self, proxy_client=None):
        """
        Initialize the service

        Args:
            proxy_client: Optional proxy client for making authenticated requests
        """
        self.proxy_client = proxy_client

    async def get_vehicle_record(
        self,
        vehicle_id: str,
        car_plate: str
    ) -> Union[EncarRecordResponse, EncarRecordErrorResponse]:
        """
        Fetch vehicle accident/insurance record data

        Args:
            vehicle_id: Encar vehicle ID (e.g., "40243547")
            car_plate: Car plate number in Korean (e.g., "283구7812")

        Returns:
            EncarRecordResponse with accident history or EncarRecordErrorResponse on error
        """
        try:
            logger.info(f"Fetching record for vehicle {vehicle_id} with plate {car_plate}")

            # URL-encode the car plate number for Korean characters
            encoded_plate = quote(car_plate)

            # Construct the API URL
            url = f"https://encar-proxy.habsida.net/api/record/{vehicle_id}/{encoded_plate}"

            logger.info(f"Request URL: {url}")

            # Make the request using proxy client if available
            if self.proxy_client:
                response_data = await self.proxy_client.make_request(url)

                if not response_data.get("success"):
                    error_msg = response_data.get("error", "Unknown error")
                    status_code = response_data.get("status_code", 500)

                    logger.error(f"Failed to fetch record: {error_msg} (status: {status_code})")

                    return EncarRecordErrorResponse(
                        success=False,
                        error=error_msg,
                        error_code=str(status_code),
                        meta={
                            "vehicle_id": vehicle_id,
                            "car_plate": car_plate,
                            "url": url
                        }
                    )

                # Parse the response
                status_code = response_data["status_code"]
                response_text = response_data["text"]

                if status_code == 404:
                    logger.info(f"No record data found for vehicle {vehicle_id} (404) - this is normal for cars without accident history")
                    return EncarRecordErrorResponse(
                        success=False,
                        error="no_accident_data",
                        error_code="404",
                        meta={
                            "vehicle_id": vehicle_id,
                            "car_plate": car_plate,
                            "message": "No accident/insurance data available for this vehicle"
                        }
                    )

                if status_code != 200:
                    logger.error(f"Unexpected status code: {status_code}")
                    return EncarRecordErrorResponse(
                        success=False,
                        error=f"HTTP {status_code}",
                        error_code=str(status_code),
                        meta={
                            "vehicle_id": vehicle_id,
                            "car_plate": car_plate,
                            "response_preview": response_text[:200] if response_text else None
                        }
                    )

                # Parse JSON response
                import json
                try:
                    record_data = json.loads(response_text)

                    # Validate and return as EncarRecordResponse
                    logger.info(f"Successfully fetched record for vehicle {vehicle_id}")
                    logger.info(f"Accidents found: {record_data.get('accidentCnt', 0)}")

                    # Add success flag and metadata
                    record_data['success'] = True
                    record_data['meta'] = {
                        "vehicle_id": vehicle_id,
                        "car_plate": car_plate,
                        "source": "encar-proxy.habsida.net"
                    }

                    return EncarRecordResponse(**record_data)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return EncarRecordErrorResponse(
                        success=False,
                        error=f"Invalid JSON response: {str(e)}",
                        error_code="json_parse_error",
                        meta={
                            "vehicle_id": vehicle_id,
                            "car_plate": car_plate,
                            "response_preview": response_text[:200] if response_text else None
                        }
                    )

            else:
                # No proxy client available - direct request (fallback)
                logger.warning("No proxy client available, attempting direct request")
                import requests

                headers = {
                    'sec-ch-ua-platform': '"macOS"',
                    'Referer': 'https://www.intercarkorea.com/',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
                    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                    'sec-ch-ua-mobile': '?0',
                }

                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 404:
                    return EncarRecordErrorResponse(
                        success=False,
                        error="no_accident_data",
                        error_code="404",
                        meta={
                            "vehicle_id": vehicle_id,
                            "car_plate": car_plate,
                            "message": "No accident/insurance data available"
                        }
                    )

                response.raise_for_status()
                record_data = response.json()

                record_data['success'] = True
                record_data['meta'] = {
                    "vehicle_id": vehicle_id,
                    "car_plate": car_plate,
                    "source": "encar-proxy.habsida.net (direct)"
                }

                return EncarRecordResponse(**record_data)

        except Exception as e:
            logger.error(f"Unexpected error fetching vehicle record: {e}")
            return EncarRecordErrorResponse(
                success=False,
                error=f"Unexpected error: {str(e)}",
                error_code="internal_error",
                meta={
                    "vehicle_id": vehicle_id,
                    "car_plate": car_plate
                }
            )
