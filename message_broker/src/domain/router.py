import re
from src.domain.models import Exchange, ExchangeType, Message
from typing import List

class Router:
    @staticmethod
    def get_destination_queues(exchange: Exchange, message: Message) -> List[str]:
        target_queues = []
        
        if exchange.type == ExchangeType.FANOUT:
            target_queues = [b.queue_name for b in exchange.bindings]
            
        elif exchange.type == ExchangeType.DIRECT:
            for binding in exchange.bindings:
                if binding.binding_key == message.routing_key:
                    target_queues.append(binding.queue_name)
                    
        elif exchange.type == ExchangeType.TOPIC:
            for binding in exchange.bindings:
                if Router._match_topic(binding.binding_key, message.routing_key):
                    target_queues.append(binding.queue_name)
                    
        return list(set(target_queues))

    @staticmethod
    def _match_topic(binding_key: str, routing_key: str) -> bool:
        regex_pattern = binding_key.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("*", r"[^\.]+")
        regex_pattern = regex_pattern.replace("#", r".*")
        
        return bool(re.fullmatch(f"^{regex_pattern}$", routing_key))
