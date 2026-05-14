import unittest

from src.domain.models import Binding, Exchange, ExchangeType, Message
from src.domain.router import Router


class RouterTest(unittest.TestCase):
    def test_fanout_routes_to_all_bound_queues(self):
        exchange = Exchange(
            name="events",
            type=ExchangeType.FANOUT,
            bindings=[
                Binding(queue_name="audit", binding_key=""),
                Binding(queue_name="notifications", binding_key=""),
            ],
        )

        queues = Router.get_destination_queues(
            exchange,
            Message(payload="payload", routing_key="user.created"),
        )

        self.assertEqual(set(queues), {"audit", "notifications"})

    def test_topic_wildcards_match_amqp_style_keys(self):
        exchange = Exchange(
            name="topic",
            type=ExchangeType.TOPIC,
            bindings=[
                Binding(queue_name="payments", binding_key="payment.*"),
                Binding(queue_name="all_users", binding_key="user.#"),
            ],
        )

        queues = Router.get_destination_queues(
            exchange,
            Message(payload="payload", routing_key="user.profile.updated"),
        )

        self.assertEqual(queues, ["all_users"])


if __name__ == "__main__":
    unittest.main()
