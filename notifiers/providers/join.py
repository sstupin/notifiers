import json
from urllib.parse import urljoin

import requests
from pydantic import Extra
from pydantic import Field
from pydantic import HttpUrl
from pydantic import root_validator
from pydantic import validator

from ..exceptions import ResourceError
from ..models.provider import Provider
from ..models.provider import ProviderResource
from ..models.provider import SchemaModel
from ..models.response import Response


class JoinMixin:
    """Shared resources between :class:`Join` and :class:`JoinDevices`"""

    name = "join"
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1"

    @staticmethod
    def _join_request(url: str, data: dict) -> tuple:
        # Can 't use generic requests util since API doesn't always return error status
        errors = None
        try:
            response = requests.get(url, params=data)
            response.raise_for_status()
            rsp = response.json()
            if not rsp["success"]:
                errors = [rsp["errorMessage"]]
        except requests.RequestException as e:
            if e.response is not None:
                response = e.response
                try:
                    errors = [response.json()["errorMessage"]]
                except json.decoder.JSONDecodeError:
                    errors = [response.text]
            else:
                response = None
                errors = [(str(e))]

        return response, errors


class JoinBaseSchema(SchemaModel):
    api_key: str = Field(..., description="User API key", alias="apikey")

    class Config:
        extra = Extra.forbid


class JoinDevices(JoinMixin, ProviderResource):
    """Return a list of Join devices IDs"""

    resource_name = "devices"
    devices_url = "/listDevices"
    schema_model = JoinBaseSchema

    def _get_resource(self, data: dict):
        url = urljoin(self.base_url, self.devices_url)
        response, errors = self._join_request(url, data)
        if errors:
            raise ResourceError(
                errors=errors,
                resource=self.resource_name,
                provider=self.name,
                data=data,
                response=response,
            )
        return response.json()["records"]


class JoinSchema(JoinBaseSchema):
    message: str = Field(
        ...,
        alias="text",
        description="Usually used as a Tasker or EventGhost command."
        " Can also be used with URLs and Files to add a description for those elements",
    )
    device_id: str = Field(
        "group.all",
        description="The device ID or group ID of the device you want to send the message to",
        alias="deviceId",
    )
    device_ids: SchemaModel.single_or_list(str) = Field(
        None,
        description="A comma separated list of device IDs you want to send the push to",
        alias="deviceIds",
    )
    device_names: SchemaModel.single_or_list(str) = Field(
        None,
        description="A comma separated list of device names you want to send the push to",
        alias="deviceNames",
    )
    url: HttpUrl = Field(
        None,
        description="A URL you want to open on the device. If a notification is created with this push, "
        "this will make clicking the notification open this URL",
    )
    clipboard: str = Field(
        None,
        description="Some text you want to set on the receiving device’s clipboard",
    )
    file: HttpUrl = Field(None, description="A publicly accessible URL of a file")
    mms_file: HttpUrl = Field(
        None, description="A publicly accessible MMS file URL", alias="mmsfile"
    )
    wallpaper: HttpUrl = Field(
        None, description="A publicly accessible URL of an image file"
    )
    icon: HttpUrl = Field(None, description="Notification's icon URL")
    small_icon: HttpUrl = Field(
        None, description="Status Bar Icon URL", alias="smallicon"
    )
    image: HttpUrl = Field(None, description="Notification image URL")
    sms_number: str = Field(
        None, description="Phone number to send an SMS to", alias="smsnumber"
    )
    sms_text: str = Field(
        None, description="Some text to send in an SMS", alias="smstext"
    )
    call_number: str = Field(None, description="Number to call to", alias="callnumber")
    interruption_filter: int = Field(
        None,
        gt=0,
        lt=5,
        description="set interruption filter mode",
        alias="interruptionFilter",
    )
    media_volume: int = Field(
        None, description="Set device media volume", alias="mediaVolume"
    )
    ring_volume: int = Field(
        None, description="Set device ring volume", alias="ringVolume"
    )
    alarm_volume: int = Field(
        None, description="Set device alarm volume", alias="alarmVolume"
    )
    find: bool = Field(None, description="Set to true to make your device ring loudly")
    title: str = Field(
        None,
        description="If used, will always create a notification on the receiving device with "
        "this as the title and text as the notification’s text",
    )
    priority: int = Field(
        None, gt=-3, lt=3, description="Control how your notification is displayed"
    )
    group: str = Field(
        None, description="Allows you to join notifications in different groups"
    )

    @root_validator(pre=True)
    def sms_validation(cls, values):
        if "sms_number" in values and not any(
            value in values for value in ("sms_text", "mms_file")
        ):
            raise ValueError(
                "Must use either 'sms_text' or 'mms_file' with 'sms_number'"
            )
        return values

    @validator("device_ids", "device_names")
    def values_to_list(cls, v):
        return cls.to_list(v)

    class Config:
        extra = Extra.forbid
        allow_population_by_field_name = True


class Join(JoinMixin, Provider):
    """Send Join notifications"""

    push_url = "/sendPush"
    site_url = "https://joaoapps.com/join/api/"

    _resources = {"devices": JoinDevices()}
    schema_model = JoinSchema

    def _send_notification(self, data: dict) -> Response:
        # Can 't use generic requests util since API doesn't always return error status
        url = urljoin(self.base_url, self.push_url)
        response, errors = self._join_request(url, data)
        return self.create_response(data, response, errors)
