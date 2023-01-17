import os
from dotenv import load_dotenv, find_dotenv
from dataclasses import dataclass

load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Variables:
    bingAPIKey: str = os.getenv("BING_API_KEY")
    uploadFolder: str = "data/upload/"
    databaseURI: str = "sqlite:///gs.db"
    debug: bool = True
    # host: str = "127.0.0.1"
    host: str = "0.0.0.0"
    port: int = 5000
    # port: int = 6969
    port2: int = 5050
