from sqlalchemy_utils import drop_database
from hololinked.server.database import create_DB_URL
from pathlib import Path
import os

config_file = str(Path(os.path.dirname(__file__)).parent) + "\\assets\\db_config.json"
URL = f"{create_DB_URL(config_file)}/hololinked-host"
drop_database(URL)
print(f"deleted DB with URL {URL}")