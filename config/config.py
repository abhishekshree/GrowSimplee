import os
from dotenv import load_dotenv, find_dotenv
from dataclasses import dataclass

load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Variables:
    bingAPIKey: str = "Ap3h89OtqBYK-5F6fBbi43Pk97AYAOkICizZiIFEqB9NXplPD_1AOaFiKwTU8WgX"
    uploadFolder: str = "data/upload/"
    databaseURI: str = "sqlite:///gs.db"
    debug: bool = True
    # host: str = "127.0.0.1"
    host: str = "0.0.0.0"
    port: int = 5050
    # port: int = 6969
    port2: int = 5000
    # osrm: str = os.environ["OSRM"]
    osrm: str = "http://osrm:5000"
    GeoApifyKey: str = "295dd37df0674ff9ade5603ac2e14baf"
    time_penalty: int = 100
    drop_penalty: int = 1800000
    timeout: int = 500
    # twilio
    twilioAccountSID: str = "AC2c3f0629857d4cd25d0a5a809604e711"
    twilioAuthToken: str = "d373c4aac3353de2045b9937c7c98135"
    twilioSMSserviceSID: str = "VA21497fbb7dafd38266628c025ebb5aef"
    twilioPhoneNumber: str = "+918317084914"
