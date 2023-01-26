import os
from dotenv import load_dotenv, find_dotenv
from dataclasses import dataclass

load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Variables:
    bingAPIKey: str = 'ApmSZKJVn_7dpTooD0MKEmAreORrBmpMRz69KAmuDthZlT1O93U_6VzjPm679m7k'
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
