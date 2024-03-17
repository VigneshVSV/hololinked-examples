from sqlalchemy_utils import drop_database
from hololinked.server.database import BaseDB
from pathlib import Path
import os

config_file = str(Path(os.path.dirname(__file__)).parent) + "\\assets\\db_config.json"
URL = BaseDB.create_postgres_URL(config_file, database="hololinked-host", use_dialect=False)
drop_database(URL)
print(f"deleted DB with URL {URL}")