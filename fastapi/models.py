from pydantic import BaseModel
from typing import List


class ContainerData(BaseModel):
    container_ids: List[str]
