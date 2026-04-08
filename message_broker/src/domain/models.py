from dataclasses import dataclass, field
from enum import Enum
from typing import List
import uuid
import time

class ExchangeType(Enum):
    DIRECT = "direct"
    FANOUT = "fanout"
    TOPIC = "topic"

@dataclass
class Message:
    payload: str
    routing_key: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

@dataclass
class Binding:
    queue_name: str
    binding_key: str

@dataclass
class Exchange:
    name: str
    type: ExchangeType
    bindings: List[Binding] = field(default_factory=list)

@dataclass
class Queue:
    name: str
    messages: List[Message] = field(default_factory=list)
