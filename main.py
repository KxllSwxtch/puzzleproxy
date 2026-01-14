import requests
import asyncio
import random
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Union, Annotated
from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uuid

# KBChaChaCha imports
from schemas.kbchachacha import (
    KBMakersResponse,
    KBModelsResponse,
    KBGenerationsResponse,
    KBConfigsTrimsResponse,
    KBSearchResponse,
    KBDefaultListResponse,
    KBSearchFilters,
    KBCarDetailResponse,
    KBCarSpecification,
    KBCarPricing,
    KBCarCondition,
    KBCarOptions,
    KBSellerInfo,
)
from services.kbchachacha_service import KBChaChaService

# Currency imports
from schemas.currency import CurrencyRateResponse, UsdCurrencyRateResponse
from services.currency_service import currency_service

# Che168 imports
from schemas.che168 import (
    Che168BrandsResponse,
    Che168SearchResponse,
    Che168SearchFilters,
    Che168CarDetailResponse,
    Che168CarInfoResponse,
    Che168CarParamsResponse,
    Che168CarAnalysisResponse,
    TranslationRequest,
    TranslationResponse,
)
from services.che168_service import Che168Service

# Encar Record imports
from schemas.encar_record import (
    EncarRecordResponse,
    EncarRecordErrorResponse,
)
from services.encar_record_service import EncarRecordService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Puzzle Proxy", version="1.0")

# CORS — разрешаем все origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация residential прокси (Korean - for KBChaChaCha and Korean sites)
PROXY_CONFIGS = [
    {
        "name": "Oxylabs Proxy",
        "proxy": "pr.oxylabs.io:7777",
        "auth": "customer-puzzle_KbiMl-cc-kr:Puzzle_korea89",
        "location": "South Korea",
        "provider": "oxylabs",
    },
]

# Chinese Proxy Configuration (for Che168 and Chinese sites)
CN_PROXY_CONFIGS = [
    {
        "name": "Oxylabs China",
        "proxy": "cn-pr.oxylabs.io:10000",
        "auth": "customer-puzzle_KbiMl-cc-cn:Puzzle_korea89",
        "location": "China",
        "provider": "oxylabs",
    },
]


def get_proxy_config(proxy_info):
    """Формирует конфигурацию прокси для requests"""
    proxy_url = f"http://{proxy_info['auth']}@{proxy_info['proxy']}"
    return {"http": proxy_url, "https": proxy_url}


# Расширенный набор User-Agent для ротации
USER_AGENTS = [
    # Desktop Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.61 Safari/537.36",
    # Desktop Firefox
    "Mozilla/5.0 (Windows NT 10.0; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Mobile Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    # Mobile Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.78 Mobile Safari/537.36",
]


# Базовые заголовки
BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5",
    "origin": "https://cars.prokorea.trading",
    "priority": "u=1, i",
    "referer": "https://cars.prokorea.trading/",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}


class EncarProxyClient:
    """Продвинутый клиент для обхода защиты Encar API с residential прокси"""

    def __init__(self, proxy_configs=None, name="Default"):
        self.proxy_configs = proxy_configs or PROXY_CONFIGS  # Use passed configs or default
        self.name = name
        self.session = requests.Session()
        self.current_proxy_index = 0
        self.request_count = 0
        self.last_request_time = 0
        self.session_rotation_count = 0

        # Базовая конфигурация сессии
        self.session.timeout = (10, 30)  # connect timeout, read timeout
        self.session.max_redirects = 3

        # Устанавливаем первый residential прокси
        self._rotate_proxy()

    def _get_dynamic_headers(self) -> Dict[str, str]:
        ua = random.choice(USER_AGENTS)

        # Подбираем headers под User-Agent
        headers = BASE_HEADERS.copy()
        headers["user-agent"] = ua

        # Chrome версия (нужно для sec-ch-ua)
        if "Chrome/125" in ua:
            headers["sec-ch-ua"] = (
                '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
            )
        elif "Chrome/124" in ua:
            headers["sec-ch-ua"] = (
                '"Google Chrome";v="124", "Chromium";v="124", "Not.A/Brand";v="24"'
            )
        elif "Chrome/123" in ua:
            headers["sec-ch-ua"] = (
                '"Google Chrome";v="123", "Chromium";v="123", "Not.A/Brand";v="24"'
            )
        else:
            headers["sec-ch-ua"] = '"Chromium";v="125", "Not.A/Brand";v="24"'

        # Платформа и мобильность
        if "Android" in ua:
            headers["sec-ch-ua-platform"] = '"Android"'
            headers["sec-ch-ua-mobile"] = "?1"
        elif "iPhone" in ua:
            headers["sec-ch-ua-platform"] = '"iOS"'
            headers["sec-ch-ua-mobile"] = "?1"
        elif "Macintosh" in ua:
            headers["sec-ch-ua-platform"] = '"macOS"'
            headers["sec-ch-ua-mobile"] = "?0"
        elif "Windows" in ua:
            headers["sec-ch-ua-platform"] = '"Windows"'
            headers["sec-ch-ua-mobile"] = "?0"
        else:
            headers["sec-ch-ua-platform"] = '"Unknown"'
            headers["sec-ch-ua-mobile"] = "?0"

        return headers

    def _rotate_proxy(self):
        """Ротация residential прокси"""
        if self.proxy_configs:
            proxy_info = self.proxy_configs[self.current_proxy_index % len(self.proxy_configs)]
            proxy_config = get_proxy_config(proxy_info)
            self.session.proxies = proxy_config
            self.current_proxy_index += 1
            logger.info(
                f"[{self.name}] Switched to {proxy_info['name']} ({proxy_info['location']}) via {proxy_info['provider']}"
            )
            logger.info(f"[{self.name}] Proxy: {proxy_info['proxy']}")

    def _create_new_session(self):
        """Создает новую сессию для полного сброса IP"""
        logger.info("Creating new session to reset IP address...")

        # Закрываем старую сессию
        self.session.close()

        # Создаем новую сессию
        self.session = requests.Session()
        self.session.timeout = (10, 30)
        self.session.max_redirects = 3

        # Принудительно меняем прокси на следующий
        self._rotate_proxy()
        self.session_rotation_count += 1

        logger.info(f"New session created (rotation #{self.session_rotation_count})")

    def _rate_limit(self):
        """Простая защита от rate limiting"""
        current_time = time.time()
        if current_time - self.last_request_time < 0.5:  # Минимум 500ms между запросами
            time.sleep(0.5 - (current_time - self.last_request_time))
        self.last_request_time = time.time()

        # Каждые 15 запросов - ротация прокси для избежания rate limits
        if self.request_count % 15 == 0 and self.request_count > 0:
            self._rotate_proxy()

        # Каждые 50 запросов - полная ротация сессии для профилактики
        if self.request_count % 50 == 0 and self.request_count > 0:
            logger.info("Preventive session rotation")
            self._create_new_session()

        self.request_count += 1

    async def make_request(self, url: str, max_retries: int = 3) -> Dict:
        """Выполняет запрос с retry логикой и обходом защиты"""

        for attempt in range(max_retries):
            try:
                # Rate limiting
                self._rate_limit()

                # Получаем свежие заголовки
                headers = self._get_dynamic_headers()

                logger.info(f"Attempt {attempt + 1}/{max_retries}: {url}")
                logger.info(f"Using UA: {headers['user-agent'][:50]}...")

                # Выполняем запрос в отдельном потоке
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: self.session.get(url, headers=headers)
                )

                logger.info(f"Response status: {response.status_code}")

                if response.status_code == 200:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "text": response.text,
                        "headers": dict(response.headers),
                        "url": url,
                        "attempt": attempt + 1,
                    }
                elif response.status_code == 403:
                    logger.warning(f"IP blacklisted (403) - creating new session")
                    self._create_new_session()
                    # Дополнительная пауза при блокировке IP
                    await asyncio.sleep(3 + random.uniform(0, 2))
                    continue
                elif response.status_code == 407:
                    logger.warning("Proxy authentication failed - rotating proxy")
                    self._rotate_proxy()
                    continue
                elif response.status_code in [429, 503]:
                    logger.warning(
                        f"Rate limited ({response.status_code}) - waiting and rotating proxy"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    self._rotate_proxy()
                    continue
                else:
                    logger.warning(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "text": response.text,
                        "error": f"HTTP {response.status_code}",
                        "url": url,
                        "attempt": attempt + 1,
                    }

            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout error: {str(e)}")
                if attempt == max_retries - 1:
                    return {"success": False, "error": f"Timeout: {str(e)}", "url": url}
                await asyncio.sleep(1)
                continue

            except requests.exceptions.ProxyError as e:
                logger.error(f"Proxy error: {str(e)} - creating new session")
                self._create_new_session()
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Proxy error: {str(e)}",
                        "url": url,
                    }
                await asyncio.sleep(2)
                continue

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {str(e)} - creating new session")
                self._create_new_session()
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Connection error: {str(e)}",
                        "url": url,
                    }
                await asyncio.sleep(3)
                continue

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Unexpected error: {str(e)}",
                        "url": url,
                    }
                await asyncio.sleep(1)
                continue

        return {"success": False, "error": "Max retries exceeded", "url": url}


# Глобальный клиент (Korean proxy for Korean sites)
proxy_client = EncarProxyClient(name="KR")

# Chinese proxy client for Che168 and Chinese sites
cn_proxy_client = EncarProxyClient(proxy_configs=CN_PROXY_CONFIGS, name="CN")

# Initialize KBChaChaCha service WITH Korean proxy for Korean site access
kbchachacha_service = KBChaChaService(proxy_client)

# Initialize Che168 service WITH Chinese proxy for Chinese site access
che168_service = Che168Service(cn_proxy_client)

encar_record_service = EncarRecordService(proxy_client)


@app.on_event("shutdown")
async def shutdown_event():
    """Корректное закрытие сессий при выключении сервера"""
    logger.info("Shutting down server...")
    if hasattr(proxy_client, "session"):
        proxy_client.session.close()
    logger.info("Sessions closed")


async def handle_api_request(endpoint: str, params: Dict[str, str]) -> JSONResponse:
    """Универсальный обработчик API запросов"""

    # Кодируем параметры
    encoded_params = {}
    for key, value in params.items():
        if isinstance(value, str):
            encoded_params[key] = value.replace("|", "%7C")
        else:
            encoded_params[key] = value

    # Формируем URL
    param_string = "&".join([f"{k}={v}" for k, v in encoded_params.items()])
    primary_url = f"https://encar-proxy.habsida.net/api/{endpoint}?{param_string}"

    # Backup URL с исходными параметрами
    backup_param_string = "&".join([f"{k}={v}" for k, v in params.items()])
    backup_url = f"https://encar-proxy.habsida.net/api/{endpoint}?{backup_param_string}"

    attempts = []

    # Пробуем основной URL
    response_data = await proxy_client.make_request(primary_url)
    attempts.append(
        {
            "url": primary_url,
            "success": response_data.get("success", False),
            "status_code": response_data.get("status_code"),
            "attempt": response_data.get("attempt", 1),
        }
    )

    # Если не удалось, пробуем backup
    if not response_data.get("success") or response_data.get("status_code") != 200:
        logger.info("Primary URL failed, trying backup...")
        response_data = await proxy_client.make_request(backup_url)
        attempts.append(
            {
                "url": backup_url,
                "success": response_data.get("success", False),
                "status_code": response_data.get("status_code"),
                "attempt": response_data.get("attempt", 1),
            }
        )

    if not response_data.get("success"):
        return JSONResponse(
            status_code=502,
            content={
                "error": f"API request failed: {response_data.get('error')}",
                "attempts": attempts,
                "debug": {"endpoint": endpoint, "params": params},
            },
        )

    status_code = response_data["status_code"]
    response_text = response_data["text"]

    if status_code != 200:
        return JSONResponse(
            status_code=status_code,
            content={
                "error": f"API returned status {status_code}",
                "attempts": attempts,
                "preview": response_text[:500] if response_text else None,
            },
        )

    # Проверяем и парсим JSON
    try:
        if not response_text or response_text.strip() == "":
            return JSONResponse(
                status_code=502,
                content={"error": "Empty response from API", "attempts": attempts},
            )

        # Проверяем на HTML вместо JSON
        if response_text.strip().startswith(("<!DOCTYPE", "<html")):
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Received HTML instead of JSON",
                    "attempts": attempts,
                    "preview": response_text[:500],
                },
            )

        import json

        json_data = json.loads(response_text)

        # Добавляем мета-информацию
        if isinstance(json_data, dict):
            json_data["_meta"] = {
                "proxy_info": {
                    "attempts": len(attempts),
                    "successful_url": response_data["url"],
                    "response_size": len(response_text),
                }
            }

        return json_data

    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": f"JSON decode error: {str(e)}",
                "attempts": attempts,
                "preview": response_text[:500] if response_text else None,
            },
        )


@app.get("/api/catalog")
async def proxy_catalog(q: str = Query(...), sr: str = Query(...)):
    """Прокси для каталога автомобилей с продвинутым обходом защиты"""
    return await handle_api_request("catalog", {"count": "true", "q": q, "sr": sr})


@app.get("/api/nav")
async def proxy_nav(
    q: str = Query(...), inav: str = Query(...), count: str = Query(default="true")
):
    """Прокси для навигации с продвинутым обходом защиты"""
    return await handle_api_request("nav", {"count": count, "q": q, "inav": inav})


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    current_proxy_info = None
    if PROXY_CONFIGS:
        current_index = (proxy_client.current_proxy_index - 1) % len(PROXY_CONFIGS)
        current_proxy_info = PROXY_CONFIGS[current_index]

    # Собираем информацию о всех провайдерах
    providers = {}
    for config in PROXY_CONFIGS:
        provider = config["provider"]
        if provider not in providers:
            providers[provider] = 0
        providers[provider] += 1

    return {
        "status": "healthy",
        "proxy_client": {
            "request_count": proxy_client.request_count,
            "session_rotations": proxy_client.session_rotation_count,
            "current_proxy": (
                current_proxy_info["name"] if current_proxy_info else "None"
            ),
            "current_provider": (
                current_proxy_info["provider"] if current_proxy_info else "None"
            ),
            "current_location": (
                current_proxy_info["location"] if current_proxy_info else "Direct"
            ),
            "available_proxies": len(PROXY_CONFIGS),
            "providers": providers,
            "proxy_type": "Residential multi-provider with session rotation",
        },
        "services": {
            "encar_api": "✅ Active (cars) - with proxy",
            "kbchachacha_cars": "✅ Active (Korean car marketplace) - with proxy",
            "parser_engine": "BeautifulSoup4 + lxml",
        },
    }


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "Multi-Platform Vehicle Proxy API",
        "version": "3.1",
        "endpoints": {
            "cars": ["/api/catalog", "/api/nav"],
            "encar_records": ["/api/encar/record/{vehicle_id}/{car_plate}"],
            "kbchachacha": [
                "/api/kbchachacha/manufacturers",
                "/api/kbchachacha/models/{maker_code}",
                "/api/kbchachacha/generations/{car_code}",
                "/api/kbchachacha/configs-trims/{car_code}",
                "/api/kbchachacha/search",
                "/api/kbchachacha/filters",
                "/api/kbchachacha/default",
                "/api/kbchachacha/car/{car_seq}",
                "/api/kbchachacha/test",
            ],
            "system": ["/health"],
        },
        "features": [
            "User-Agent rotation",
            "Multi-provider residential proxy rotation (Korea) - for cars",
            "Automatic session rotation on 403 errors",
            "Rate limiting protection",
            "Retry logic with exponential backoff",
            "Advanced error handling",
            "Proxy authentication & rotation",
            "BeautifulSoup4 + lxml parsing",
            "Korean site optimization",
            "Enhanced query parameter validation",
        ],
        "platforms": {
            "encar.com": "Car listings and navigation (via proxy)",
            "kbchachacha.com": "Korean car marketplace - manufacturers, models, search (via proxy)",
        },
        "providers": [config["provider"] for config in PROXY_CONFIGS],
        "total_proxies": len(PROXY_CONFIGS),
        "api_status": {
            "cars_core": "✅ Fully operational",
            "kbchachacha_cars": "✅ Fully operational (Korean car marketplace integration)",
        },
    }


# ============================================================================
# KBChaChaCha API Endpoints
# ============================================================================


@app.get("/api/kbchachacha/manufacturers", response_model=KBMakersResponse)
async def get_kbchachacha_manufacturers():
    """
    Get list of car manufacturers from KBChaChaCha

    Returns both domestic (국산) and imported (수입) manufacturers
    with car counts for each manufacturer.

    **Example Response:**
    ```json
    {
        "success": true,
        "domestic": [
            {"makerName": "현대", "makerCode": "101", "count": 15234},
            {"makerName": "기아", "makerCode": "102", "count": 12456}
        ],
        "imported": [
            {"makerName": "벤츠", "makerCode": "108", "count": 8203},
            {"makerName": "BMW", "makerCode": "107", "count": 8431}
        ]
    }
    ```
    """
    try:
        result = await kbchachacha_service.get_manufacturers()

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch manufacturers: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha manufacturers endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/kbchachacha/models/{maker_code}", response_model=KBModelsResponse)
async def get_kbchachacha_models(maker_code: str):
    """
    Get car models for specific manufacturer

    **Parameters:**
    - **maker_code**: Manufacturer code (e.g., "101" for 현대, "102" for 기아)

    **Returns:**
    List of models with usage types (대형, SUV, 준중형, etc.)
    """
    try:
        result = await kbchachacha_service.get_models(maker_code)

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch models for maker {maker_code}: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha models endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get(
    "/api/kbchachacha/generations/{class_code}", response_model=KBGenerationsResponse
)
async def get_kbchachacha_generations(class_code: str):
    """
    Get car generations for specific model class

    **Parameters:**
    - **class_code**: Model class code (e.g., "1101" for 그랜저, "1109" for 아반떼, "1108" for 쏘나타)

    **Returns:**
    List of generations/variants for the specified car model
    with year ranges and generation names (e.g., "DN8", "LF", "YF").

    **Example:**
    - Hyundai Grandeur generations: `/api/kbchachacha/generations/1101`
    - Hyundai Avante generations: `/api/kbchachacha/generations/1109`
    - Hyundai Sonata generations: `/api/kbchachacha/generations/1108`

    **Note:** Class codes can be found in the models endpoint result (classCode field).

    **What you get:**
    - Real car generations like "쏘나타 디 엣지(DN8) (2023-현재)", "LF쏘나타 (2014-2017)"
    - Not engine configurations (those are in configs-trims endpoint)
    """
    try:
        result = await kbchachacha_service.get_generations(class_code)

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch generations for class {class_code}: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha generations endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get(
    "/api/kbchachacha/configs-trims/{car_code}", response_model=KBConfigsTrimsResponse
)
async def get_kbchachacha_configs_trims(car_code: str):
    """
    Get configurations and trim levels for specific car

    **Parameters:**
    - **car_code**: Car code (same as generations endpoint, e.g., "3301")

    **Returns:**
    - **configurations**: Available model configurations
    - **trims**: Available trim levels/grades

    **Example:**
    - Model configurations and trims: `/api/kbchachacha/configs-trims/3301`

    This provides the deepest level of filtering for precise car searches.
    """
    try:
        result = await kbchachacha_service.get_configs_trims(car_code)

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch configs/trims for car {car_code}: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha configs/trims endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/kbchachacha/search", response_model=KBSearchResponse)
async def search_kbchachacha_cars(
    page: int = Query(default=1, description="Page number"),
    sort: str = Query(default="-orderDate", description="Sort order"),
    makerCode: Optional[str] = Query(None, description="Manufacturer code"),
    classCode: Optional[str] = Query(None, description="Model class code"),
    carCode: Optional[str] = Query(None, description="Car code"),
    modelCode: Optional[str] = Query(None, description="Model code"),
    modelGradeCode: Optional[str] = Query(None, description="Model grade codes"),
    # Year filter (연식)
    year_from: Optional[int] = Query(
        None, description="Minimum year (e.g., 2020)", ge=1990, le=2030
    ),
    year_to: Optional[int] = Query(
        None, description="Maximum year (e.g., 2025)", ge=1990, le=2030
    ),
    # Mileage filter (주행거리) - in kilometers
    mileage_from: Optional[int] = Query(
        None, description="Minimum mileage in km", ge=0
    ),
    mileage_to: Optional[int] = Query(None, description="Maximum mileage in km", ge=0),
    # Price filter (가격) - in 만원 (10,000 KRW units)
    price_from: Optional[int] = Query(None, description="Minimum price in 만원", ge=0),
    price_to: Optional[int] = Query(None, description="Maximum price in 만원", ge=0),
    # Fuel types (연료) - comma-separated list
    fuel_types: Optional[str] = Query(
        None, description="Fuel types: gasoline,diesel,electric,hybrid_gasoline,lpg,etc"
    ),
):
    """
    Search cars on KBChaChaCha with comprehensive filters

    **Basic Parameters:**
    - **page**: Page number for pagination
    - **sort**: Sort order (default: -orderDate)
    - **makerCode**: Filter by manufacturer (e.g., "101" for 현대)
    - **classCode**: Filter by model class (e.g., "1101" for 그랜저)

    **Year Filter (연식):**
    - **year_from**: Minimum year (e.g., 2020)
    - **year_to**: Maximum year (e.g., 2025)

    **Mileage Filter (주행거리):**
    - **mileage_from**: Minimum mileage in km (e.g., 0)
    - **mileage_to**: Maximum mileage in km (e.g., 50000)

    **Price Filter (가격):**
    - **price_from**: Minimum price in 만원 (e.g., 1000 for 1000만원)
    - **price_to**: Maximum price in 만원 (e.g., 5000 for 5000만원)

    **Fuel Types (연료):**
    - **fuel_types**: Comma-separated list of fuel types:
      - `gasoline` - 가솔린
      - `diesel` - 디젤
      - `electric` - 전기
      - `hybrid_gasoline` - 하이브리드(가솔린)
      - `hybrid_diesel` - 하이브리드(디젤)
      - `lpg` - LPG
      - `cng` - CNG

    **Example Usage:**
    - All cars: `/api/kbchachacha/search`
    - 현대 cars 2020-2025: `/api/kbchachacha/search?makerCode=101&year_from=2020&year_to=2025`
    - Electric cars under 3000만원: `/api/kbchachacha/search?fuel_types=electric&price_to=3000`
    - Low mileage gasoline cars: `/api/kbchachacha/search?fuel_types=gasoline&mileage_to=30000`
    """
    try:
        # Parse fuel types from string to enum list
        parsed_fuel_types = None
        if fuel_types:
            fuel_type_mapping = {
                "gasoline": "004001",  # 가솔린
                "diesel": "004002",  # 디젤
                "lpg": "004003",  # LPG
                "hybrid_lpg": "004004",  # 하이브리드(LPG)
                "hybrid_gasoline": "004005",  # 하이브리드(가솔린)
                "hybrid_diesel": "004011",  # 하이브리드(디젤)
                "cng": "004006",  # CNG
                "electric": "004007",  # 전기
                "other": "004008",  # 기타
                "gasoline_lpg": "004010",  # 가솔린+LPG
            }

            fuel_list = [ft.strip().lower() for ft in fuel_types.split(",")]
            from schemas.kbchachacha import FuelType

            parsed_fuel_types = []

            for fuel in fuel_list:
                if fuel in fuel_type_mapping:
                    parsed_fuel_types.append(FuelType(fuel_type_mapping[fuel]))

        filters = KBSearchFilters(
            page=page,
            sort=sort,
            makerCode=makerCode,
            classCode=classCode,
            carCode=carCode,
            modelCode=modelCode,
            modelGradeCode=modelGradeCode,
            year_from=year_from,
            year_to=year_to,
            mileage_from=mileage_from,
            mileage_to=mileage_to,
            price_from=price_from,
            price_to=price_to,
            fuel_types=parsed_fuel_types,
        )

        result = await kbchachacha_service.search_cars(filters)

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to search cars: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha search endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/kbchachacha/default", response_model=KBDefaultListResponse)
async def get_kbchachacha_default_listings():
    """
    Get default car listings from KBChaChaCha homepage

    Returns KB Star Pick cars and certified/diagnosed cars
    from the main page without any filters.

    **Returns:**
    - **star_pick_listings**: KB Star Pick featured cars
    - **certified_listings**: Certified and diagnosed cars
    - **total_count**: Total number of listings
    """
    try:
        result = await kbchachacha_service.get_default_listings()

        if not result.success:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch default listings: {result.meta.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha default listings endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/kbchachacha/test")
async def test_kbchachacha_integration():
    """
    Test KBChaChaCha integration with sample requests

    Tests all major endpoints to verify functionality
    """
    try:
        results = {}

        # Test manufacturers
        logger.info("Testing KBChaChaCha manufacturers...")
        manufacturers_result = await kbchachacha_service.get_manufacturers()
        results["manufacturers"] = {
            "success": manufacturers_result.success,
            "total_count": manufacturers_result.total_count,
            "domestic_count": len(manufacturers_result.domestic),
            "imported_count": len(manufacturers_result.imported),
            "sample_domestic": (
                manufacturers_result.domestic[:3]
                if manufacturers_result.domestic
                else []
            ),
            "sample_imported": (
                manufacturers_result.imported[:3]
                if manufacturers_result.imported
                else []
            ),
        }

        # Test models (using 현대 as example)
        if manufacturers_result.success and manufacturers_result.domestic:
            hyundai_code = "101"  # 현대
            logger.info(
                f"Testing KBChaChaCha models for 현대 (code: {hyundai_code})..."
            )
            models_result = await kbchachacha_service.get_models(hyundai_code)
            results["models"] = {
                "success": models_result.success,
                "total_count": models_result.total_count,
                "sample_models": (
                    models_result.models[:5] if models_result.models else []
                ),
                "maker_code": hyundai_code,
            }

        # Test default listings
        logger.info("Testing KBChaChaCha default listings...")
        default_result = await kbchachacha_service.get_default_listings()
        results["default_listings"] = {
            "success": default_result.success,
            "total_count": default_result.total_count,
            "star_pick_count": len(default_result.star_pick_listings),
            "certified_count": len(default_result.certified_listings),
            "sample_listings": (
                default_result.star_pick_listings + default_result.certified_listings
            )[:3],
        }

        # Test search with filters (using 현대 as example)
        if manufacturers_result.success and manufacturers_result.domestic:
            hyundai_code = "101"  # 현대
            logger.info(f"Testing KBChaChaCha filtered search for 현대...")

            # Test comprehensive filters
            from schemas.kbchachacha import KBSearchFilters, FuelType

            test_filters = KBSearchFilters(
                page=1,
                makerCode=hyundai_code,
                year_from=2020,
                year_to=2025,
                price_to=5000,  # Under 5000만원
                mileage_to=50000,  # Under 50,000km
                fuel_types=[FuelType.GASOLINE, FuelType.HYBRID_GASOLINE],
            )

            search_result = await kbchachacha_service.search_cars(test_filters)
            results["filtered_search"] = {
                "success": search_result.success,
                "total_count": search_result.total_count,
                "listings_count": len(search_result.listings),
                "filters_applied": {
                    "manufacturer": "현대",
                    "year_range": "2020-2025",
                    "max_price": "5000만원",
                    "max_mileage": "50000km",
                    "fuel_types": ["gasoline", "hybrid_gasoline"],
                },
                "sample_listings": (
                    search_result.listings[:2] if search_result.listings else []
                ),
            }

        return {
            "test_successful": True,
            "timestamp": time.time(),
            "note": "KBChaChaCha integration test completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error in KBChaChaCha test endpoint: {str(e)}")
        return {
            "test_successful": False,
            "error": str(e),
            "timestamp": time.time(),
            "note": "KBChaChaCha integration test failed",
        }


@app.get("/api/kbchachacha/filters")
async def get_kbchachacha_filters():
    """
    Get information about available KBChaChaCha search filters

    Returns comprehensive information about all available filter options
    including fuel types, year ranges, price ranges, and usage examples.

    **Returns:**
    - **fuel_types**: All available fuel type options with codes
    - **year_range**: Supported year range for filtering
    - **price_info**: Information about price filtering (in 만원)
    - **mileage_info**: Information about mileage filtering (in km)
    - **usage_examples**: Example API calls with different filters
    """
    try:
        from schemas.kbchachacha import FuelType

        return {
            "success": True,
            "filters": {
                "fuel_types": {
                    "description": "Available fuel type filters",
                    "options": {
                        "gasoline": {
                            "code": "004001",
                            "name": "가솔린",
                            "description": "Gasoline",
                        },
                        "diesel": {
                            "code": "004002",
                            "name": "디젤",
                            "description": "Diesel",
                        },
                        "lpg": {"code": "004003", "name": "LPG", "description": "LPG"},
                        "hybrid_lpg": {
                            "code": "004004",
                            "name": "하이브리드(LPG)",
                            "description": "Hybrid LPG",
                        },
                        "hybrid_gasoline": {
                            "code": "004005",
                            "name": "하이브리드(가솔린)",
                            "description": "Hybrid Gasoline",
                        },
                        "hybrid_diesel": {
                            "code": "004011",
                            "name": "하이브리드(디젤)",
                            "description": "Hybrid Diesel",
                        },
                        "cng": {"code": "004006", "name": "CNG", "description": "CNG"},
                        "electric": {
                            "code": "004007",
                            "name": "전기",
                            "description": "Electric",
                        },
                        "other": {
                            "code": "004008",
                            "name": "기타",
                            "description": "Other",
                        },
                        "gasoline_lpg": {
                            "code": "004010",
                            "name": "가솔린+LPG",
                            "description": "Gasoline + LPG",
                        },
                    },
                    "usage": "Comma-separated list: ?fuel_types=gasoline,electric,hybrid_gasoline",
                },
                "year_filter": {
                    "description": "Year range filter (연식)",
                    "range": {"min": 1990, "max": 2030},
                    "parameters": ["year_from", "year_to"],
                    "usage": "?year_from=2020&year_to=2025",
                    "examples": {
                        "recent_cars": "?year_from=2020",
                        "2020_to_2025": "?year_from=2020&year_to=2025",
                        "before_2015": "?year_to=2015",
                    },
                },
                "price_filter": {
                    "description": "Price range filter (가격) in 만원 (10,000 KRW units)",
                    "unit": "만원 (10,000 KRW)",
                    "range": {"min": 0, "max": 99999},
                    "parameters": ["price_from", "price_to"],
                    "usage": "?price_from=1000&price_to=5000",
                    "examples": {
                        "under_3000": "?price_to=3000",
                        "1000_to_5000": "?price_from=1000&price_to=5000",
                        "above_2000": "?price_from=2000",
                    },
                },
                "mileage_filter": {
                    "description": "Mileage range filter (주행거리) in kilometers",
                    "unit": "km",
                    "range": {"min": 0, "max": 999999},
                    "parameters": ["mileage_from", "mileage_to"],
                    "usage": "?mileage_from=0&mileage_to=50000",
                    "examples": {
                        "low_mileage": "?mileage_to=30000",
                        "medium_mileage": "?mileage_from=30000&mileage_to=100000",
                        "high_mileage": "?mileage_from=100000",
                    },
                },
            },
            "usage_examples": {
                "basic_search": "/api/kbchachacha/search",
                "manufacturer_filter": "/api/kbchachacha/search?makerCode=101",
                "comprehensive_filter": "/api/kbchachacha/search?makerCode=101&year_from=2020&year_to=2025&price_to=3000&fuel_types=gasoline,hybrid_gasoline",
                "electric_cars": "/api/kbchachacha/search?fuel_types=electric&price_to=5000",
                "low_mileage_luxury": "/api/kbchachacha/search?mileage_to=20000&price_from=3000",
                "recent_hybrids": "/api/kbchachacha/search?year_from=2022&fuel_types=hybrid_gasoline,hybrid_diesel",
            },
            "combining_filters": {
                "note": "All filters can be combined for precise search results",
                "examples": [
                    "Recent electric cars under 4000만원: ?year_from=2021&fuel_types=electric&price_to=4000",
                    "Low mileage 현대 cars 2020-2023: ?makerCode=101&year_from=2020&year_to=2023&mileage_to=30000",
                    "Hybrid cars in mid price range: ?fuel_types=hybrid_gasoline,hybrid_diesel&price_from=2000&price_to=4000",
                ],
            },
            "meta": {
                "service": "kbchachacha_filters",
                "supported_manufacturers": "Use /api/kbchachacha/manufacturers to get all available manufacturers",
                "supported_models": "Use /api/kbchachacha/models/{maker_code} to get models for specific manufacturer",
            },
        }

    except Exception as e:
        logger.error(f"Error in KBChaChaCha filters endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/kbchachacha/car/{car_seq}", response_model=KBCarDetailResponse)
async def get_kbchachacha_car_details(car_seq: str):
    """
    Get detailed information for a specific car

    **Parameters:**
    - **car_seq**: Car sequence ID (e.g., "27069369")

    **Returns:**
    Comprehensive car information including:
    - Basic details (title, brand, model, images)
    - Technical specifications (engine, transmission, mileage, etc.)
    - Pricing information (current price, market range, confidence)
    - Condition assessment (inspection status, mileage analysis)
    - Options and features (safety, convenience, multimedia)
    - Seller information (location, description, contact)

    **Example Usage:**
    - Get Hyundai Veloster details: `/api/kbchachacha/car/27069369`
    - Use car_seq from search results to get full details

    **Data Sources:**
    - JSON-LD structured data for basic info and images
    - HTML table parsing for technical specifications
    - Multiple page sections for pricing, condition, and options
    """
    try:
        result = await kbchachacha_service.get_car_details(car_seq)

        if not result.get("success"):
            # Handle specific error cases
            error_msg = result.get("error", "Unknown error")

            if "may not exist" in error_msg or "unavailable" in error_msg:
                raise HTTPException(
                    status_code=404, detail=f"Car not found: {error_msg}"
                )
            else:
                raise HTTPException(
                    status_code=502, detail=f"Failed to fetch car details: {error_msg}"
                )

        # Import schema classes for response validation
        from schemas.kbchachacha import (
            KBCarDetailResponse,
            KBCarSpecification,
            KBCarPricing,
            KBCarCondition,
            KBCarOptions,
            KBSellerInfo,
        )

        # Validate and structure the response
        return KBCarDetailResponse(
            success=True,
            car_seq=result["car_seq"],
            title=result["title"],
            brand=result["brand"],
            model=result["model"],
            full_name=result["full_name"],
            images=result["images"],
            main_image=result["main_image"],
            specifications=result["specifications"],
            pricing=result["pricing"],
            condition=result["condition"],
            options=result["options"],
            seller=result["seller"],
            description=result["description"],
            tags=result["tags"],
            badges=result["badges"],
            detail_url=result["detail_url"],
            meta=result.get("meta"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KBChaChaCha car details endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# =============================================================================
# ENCAR RECORD/ACCIDENT HISTORY ENDPOINTS
# =============================================================================

@app.get("/api/encar/record/{vehicle_id}/{car_plate}", response_model=Union[EncarRecordResponse, EncarRecordErrorResponse])
async def get_encar_vehicle_record(
    vehicle_id: str = Path(..., description="Encar vehicle ID (e.g., '40243547')"),
    car_plate: str = Path(..., description="Car plate number in Korean (e.g., '283구7812')")
):
    """
    Get vehicle accident/insurance record history from Encar

    **Parameters:**
    - **vehicle_id**: Encar vehicle ID (numeric string)
    - **car_plate**: Car plate number in Korean format (e.g., "283구7812")

    **Returns:**
    Comprehensive accident and insurance history including:
    - Accident counts (own-fault vs other-party)
    - Detailed accident records with costs breakdown
    - Insurance claim amounts
    - Ownership change history
    - Special conditions (theft, total loss, flood damage)
    - Car information changes

    **Response Codes:**
    - **200**: Success with accident data
    - **404**: No accident data found (normal for clean history cars)
    - **502**: Failed to fetch data from source

    **Example Usage:**
    ```
    GET /api/encar/record/40243547/283구7812
    ```

    **Accident Type Codes:**
    - **1**: 자차 (Own vehicle damage)
    - **2**: 대인 (Personal injury to others)
    - **3**: 대물 (Property damage to others)
    """
    try:
        logger.info(f"Vehicle record request: vehicle_id={vehicle_id}, car_plate={car_plate}")

        result = await encar_record_service.get_vehicle_record(vehicle_id, car_plate)

        if not result.success:
            # Return error response with appropriate status code
            error_code = getattr(result, 'error_code', '500')

            if error_code == '404':
                # 404 is normal for cars without accident history
                logger.info(f"No accident data for vehicle {vehicle_id} (clean history)")
                return JSONResponse(
                    status_code=200,  # Return 200 with success=False for clean cars
                    content=result.dict()
                )
            elif error_code == '403':
                logger.warning(f"Access denied for vehicle {vehicle_id}")
                return JSONResponse(status_code=502, content=result.dict())
            else:
                logger.error(f"Error fetching record: {result.error}")
                return JSONResponse(status_code=502, content=result.dict())

        logger.info(f"Successfully fetched record for vehicle {vehicle_id}")
        return result

    except Exception as e:
        logger.error(f"Unexpected error in encar record endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Internal server error: {str(e)}",
                "error_code": "500",
                "meta": {
                    "vehicle_id": vehicle_id,
                    "car_plate": car_plate
                }
            }
        )


# ================================
# CURRENCY ENDPOINTS
# ================================

@app.get("/api/currency/rub-krw", response_model=CurrencyRateResponse)
def get_rub_krw_rate():
    """
    Get current RUB to KRW exchange rate from Naver API

    This endpoint fetches the exchange rate directly from Naver's API to bypass
    browser CORS restrictions. The rate is adjusted by -0.80 as specified.

    Returns:
        CurrencyRateResponse: Current exchange rate with metadata
    """
    try:
        logger.info("🔄 Processing RUB/KRW rate request...")

        # Fetch rate from Naver API using the currency service
        result = currency_service.fetch_naver_rub_rate()

        # Log the result for monitoring
        if result.success:
            logger.info(f"✅ Successfully returned RUB/KRW rate: {result.data.rubToKrwRate} (source: {result.source})")
        else:
            logger.warning(f"⚠️ Returned fallback rate: {result.data.rubToKrwRate} (error: {result.error})")

        return result

    except Exception as e:
        logger.error(f"❌ Unexpected error in currency endpoint: {e}")

        # Return fallback response in case of unexpected errors
        from datetime import datetime
        from schemas.currency import CurrencyRateData

        return CurrencyRateResponse(
            success=False,
            data=CurrencyRateData(
                rubToKrwRate=16.54,
                originalRate=None
            ),
            source="fallback",
            lastUpdated=datetime.utcnow().isoformat() + "Z",
            error=f"Unexpected server error: {str(e)}"
        )


@app.get("/api/currency/usd-krw", response_model=UsdCurrencyRateResponse)
def get_usd_krw_rate():
    """
    Get current USD to KRW exchange rate from Naver API

    This endpoint fetches the exchange rate directly from Naver's API to bypass
    browser CORS restrictions.

    Returns:
        UsdCurrencyRateResponse: Current exchange rate with metadata
    """
    try:
        logger.info("🔄 Processing USD/KRW rate request...")

        # Fetch rate from Naver API using the currency service
        result = currency_service.fetch_naver_usd_rate()

        # Log the result for monitoring
        if result.success:
            logger.info(f"✅ Successfully returned USD/KRW rate: {result.data.usdToKrwRate} (source: {result.source})")
        else:
            logger.warning(f"⚠️ Returned fallback rate: {result.data.usdToKrwRate} (error: {result.error})")

        return result

    except Exception as e:
        logger.error(f"❌ Unexpected error in USD currency endpoint: {e}")

        # Return fallback response in case of unexpected errors
        from datetime import datetime
        from schemas.currency import UsdCurrencyRateData

        return UsdCurrencyRateResponse(
            success=False,
            data=UsdCurrencyRateData(
                usdToKrwRate=1375.50,
                originalRate=None
            ),
            source="fallback",
            lastUpdated=datetime.utcnow().isoformat() + "Z",
            error=f"Unexpected server error: {str(e)}"
        )


# =============================================================================
# CHE168 CHINESE CARS ENDPOINTS
# =============================================================================

@app.get("/api/che168/brands", response_model=Che168BrandsResponse)
async def get_che168_brands():
    """
    Get all available car brands from Che168 Chinese marketplace

    Returns:
        Che168BrandsResponse: List of hot brands and all brands with metadata
    """
    try:
        result = await che168_service.get_brands()
        return result

    except Exception as e:
        logger.error(f"Error in che168 brands endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Brands fetch failed: {str(e)}")


@app.get("/api/che168/models/{brand_id}", response_model=Che168SearchResponse)
async def get_che168_models(brand_id: int):
    """
    Get available models for a specific brand from Che168

    This endpoint searches with the brand filter and extracts model options
    from the service filters in the response.

    Args:
        brand_id: The brand ID to get models for

    Returns:
        Che168SearchResponse: Search response with models in the result.series array

    Example:
        GET /api/che168/models/15  # Get BMW models
    """
    try:
        logger.info(f"Fetching models for brand_id={brand_id}")
        result = await che168_service.get_models(brand_id)
        return result

    except Exception as e:
        logger.error(f"Error in che168 models endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Models fetch failed: {str(e)}")


@app.get("/api/che168/years/{brand_id}/{series_id}", response_model=Che168SearchResponse)
async def get_che168_years(brand_id: int, series_id: int):
    """
    Get available years for a specific brand and model from Che168

    This endpoint searches with brand and series filters and extracts year options
    from the service filters in the response.

    Args:
        brand_id: The brand ID
        series_id: The series (model) ID

    Returns:
        Che168SearchResponse: Search response with years in the result.years array

    Example:
        GET /api/che168/years/15/65  # Get BMW X3 years
    """
    try:
        logger.info(f"Fetching years for brand_id={brand_id}, series_id={series_id}")
        result = await che168_service.get_years(brand_id, series_id)
        return result

    except Exception as e:
        logger.error(f"Error in che168 years endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Years fetch failed: {str(e)}")


@app.post("/api/che168/search", response_model=Che168SearchResponse)
async def search_che168_cars(filters: Che168SearchFilters):
    """
    Search Chinese cars with advanced filtering on Che168

    Args:
        filters: Search filters including brand, price range, year, etc.

    Returns:
        Che168SearchResponse: Search results with car listings and pagination
    """
    try:
        # Convert Pydantic model to dict for service
        filters_dict = filters.dict(exclude_unset=True)
        result = await che168_service.search_cars(filters_dict)
        return result

    except Exception as e:
        logger.error(f"Error in che168 search endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/che168/car/{info_id}", response_model=Che168CarDetailResponse)
async def get_che168_car_detail(
    info_id: Annotated[str, Path(description="Car info ID")]
):
    """
    Get detailed information for a specific Chinese car

    Args:
        info_id: Che168 car info ID

    Returns:
        Che168CarDetailResponse: Complete car details including specs and seller info
    """
    try:
        result = await che168_service.get_car_detail(int(info_id))
        return result

    except Exception as e:
        logger.error(f"Error in che168 car detail endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Car detail fetch failed: {str(e)}")


@app.get("/api/che168/car/{info_id}/info", response_model=Che168CarInfoResponse)
async def get_che168_car_info(
    info_id: Annotated[str, Path(description="Car info ID")]
):
    """
    Get basic car information

    Args:
        info_id: Che168 car info ID

    Returns:
        Che168CarInfoResponse: Basic car information
    """
    try:
        result = await che168_service.get_car_info(int(info_id))
        return result

    except Exception as e:
        logger.error(f"Error in che168 car info endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Car info fetch failed: {str(e)}")


@app.get("/api/che168/car/{info_id}/params", response_model=Che168CarParamsResponse)
async def get_che168_car_params(
    info_id: Annotated[str, Path(description="Car info ID")]
):
    """
    Get car technical parameters

    Args:
        info_id: Che168 car info ID

    Returns:
        Che168CarParamsResponse: Car technical specifications
    """
    try:
        result = await che168_service.get_car_params(int(info_id))
        return result

    except Exception as e:
        logger.error(f"Error in che168 car params endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Car params fetch failed: {str(e)}")


@app.get("/api/che168/car/{info_id}/analysis", response_model=Che168CarAnalysisResponse)
async def get_che168_car_analysis(
    info_id: Annotated[str, Path(description="Car info ID")]
):
    """
    Get car market analysis

    Args:
        info_id: Che168 car info ID

    Returns:
        Che168CarAnalysisResponse: Market analysis and price trends
    """
    try:
        result = await che168_service.get_car_analysis(int(info_id))
        return result

    except Exception as e:
        logger.error(f"Error in che168 car analysis endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Car analysis fetch failed: {str(e)}")


@app.post("/api/che168/translate", response_model=TranslationResponse)
async def translate_che168_text(translation_request: TranslationRequest):
    """
    Translate Chinese text to target language

    Args:
        translation_request: Text and target language

    Returns:
        TranslationResponse: Translated text
    """
    try:
        # Translation not implemented in current service
        result = {
            "returncode": 1,
            "message": "Translation service not available",
            "result": {}
        }
        return result

    except Exception as e:
        logger.error(f"Error in che168 translate endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@app.get("/api/che168/test")
async def test_che168_service():
    """
    Test Che168 service health

    Returns:
        dict: Service health status
    """
    try:
        result = che168_service.health_check()
        return result

    except Exception as e:
        logger.error(f"Error in che168 test endpoint: {str(e)}")
        return {
            "returncode": 1,
            "message": f"Service test failed: {str(e)}",
            "result": {"status": "unhealthy"}
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
