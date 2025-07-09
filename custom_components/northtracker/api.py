"""North-Tracker API Client."""
import aiohttp

class NorthTrackerException(Exception):
    """Base exception for North-Tracker API errors."""

class AuthenticationError(NorthTrackerException):
    """Exception for authentication errors."""

class NorthTracker:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = "https://apiv2.northtracker.com/api/v1"
        self.http_headers = {
            "Content-Type": "application/json",
            "Timezone": "Europe/Stockholm",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Request-Type": "web",
        }
        self.rate_limit = 0
        self.rate_limit_remaining = 0

    async def _update_rate_limits(self, response):
        self.rate_limit = int(response.headers.get("X-RateLimit-Limit", self.rate_limit))
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))

    async def _get_data(self, url):
        async with self.session.get(url, headers=self.http_headers) as response:
            await self._update_rate_limits(response)
            response.raise_for_status()
            return NorthTrackerResponse(await response.json())

    async def _post_data(self, url, payload=None):
        async with self.session.post(url, json=payload, headers=self.http_headers) as response:
            await self._update_rate_limits(response)
            response.raise_for_status()
            return NorthTrackerResponse(await response.json())

    async def login(self, username, password):
        url = f"{self.base_url}/login"
        payload = {"username": username, "password": password, "remember_me": False, "subsiteid": 0}
        resp = await self._post_data(url, payload)
        if resp.success:
            self.http_headers["Authorization"] = f"Bearer {resp.data.get('user', {}).get('token', '')}"
            return True
        raise AuthenticationError("Login failed, please check username and password")

    async def get_all_units_details(self):
        url = f"{self.base_url}/user/terminal/get-all-units-details"
        return await self._get_data(url)

    async def get_unit_details(self, device_id, device_type):
        url = f"{self.base_url}/user/terminal/edit-terminal"
        return await self._post_data(url, {"device_id": device_id, "device_type": device_type})

    async def get_unit_lock_status(self, device_id):
        url = f"{self.base_url}/user/terminal/access/lockstatus"
        return await self._post_data(url, {"terminal_id": device_id})

    async def output_turn_on(self, device_id, output_number):
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {"terminal_id": device_id, "doutnumber": output_number, "doutvalue": 1}
        return await self._post_data(url, payload)

    async def output_turn_off(self, device_id, output_number):
        url = f"{self.base_url}/user/terminal/relaysetting/sendmsg"
        payload = {"terminal_id": device_id, "doutnumber": output_number, "doutvalue": 0}
        return await self._post_data(url, payload)

class NorthTrackerResponse:
    def __init__(self, data):
        self.response_data = data

    @property
    def success(self):
        return self.response_data.get("success", False)

    @property
    def data(self):
        return self.response_data.get("data", {})

class NorthTrackerDevice:
    def __init__(self, tracker: NorthTracker, device_data: dict):
        self.tracker = tracker
        self._device_data = device_data
        self._device_data_extra = {}
        self._device_lock_data = {}

    async def async_update(self):
        resp_details = await self.tracker.get_unit_details(self.id, self.device_type)
        if resp_details.success:
            self._device_data_extra = resp_details.data

        resp_lock = await self.tracker.get_unit_lock_status(self.id)
        if resp_lock.success:
            self._device_lock_data = resp_lock.data

    @property
    def id(self):
        return self._device_data.get("ID", 0)
    
    @property
    def name(self):
        return self._device_data.get("NameOnly", "")

    @property
    def device_type(self):
        return self._device_data.get("DeviceType", "")

    @property
    def imei(self):
        return self._device_data.get("Imei", "")

    @property
    def model(self):
        return self._device_data.get("GpsModel", "")

    @property
    def gps_signal(self):
        return self._device_data.get("GPS", 0)

    @property
    def last_seen(self):
        return self._device_data.get("LastSeen")

    @property
    def battery_voltage(self):
        return self._device_data.get("BatteryVoltage")

    @property
    def odometer(self):
        return self._device_data.get("Odometer", 0)

    @property
    def lock_status(self) -> bool:
        return self._device_lock_data.get("lockedstatus", False)

    @property
    def output_status_1(self) -> bool:
        return self._device_data.get("Dout1Status") == "On"

    @property
    def output_status_2(self) -> bool:
        return self._device_data.get("Dout2Status") == "On"

    @property
    def output_status_3(self) -> bool:
        return self._device_data.get("Dout3Status") == "On"