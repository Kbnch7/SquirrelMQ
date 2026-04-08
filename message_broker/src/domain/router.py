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
            pass
            
        return list(set(target_queues))
