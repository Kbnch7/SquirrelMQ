from abc import ABC, abstractmethod
from src.domain.models import Message, Exchange, Queue

class IStorage(ABC):
    @abstractmethod
    async def save_message(self, message: Message) -> None:
        pass

    @abstractmethod
    def get_exchange(self, name: str) -> Exchange:
        pass

    @abstractmethod
    def get_queues_by_exchange(self, exchange_name: str) -> list[Queue]:
        pass
