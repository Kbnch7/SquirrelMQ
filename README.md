# SquirrelMQ

SquirrelMQ - мой учебный брокер сообщений. Я делал его как небольшой аналог RabbitMQ: есть exchange, queue, binding, publisher, consumer, подтверждение доставки и хранение состояния в PostgreSQL.

Проект написан на Python, сетевой протокол сделан через gRPC/Protobuf, для клиента есть простой SDK.

## Отчёт для финальной сдачи

В этом разделе я указал, какие технологии и части из системы оценивания использовал, где они лежат в проекте и как именно применяются.

| Требование / технология | Где реализовано | Как применил |
| --- | --- | --- |
| Python | `message_broker/src/`, `sdk/`, `demo_stands/` | На Python написаны сам брокер, SDK и демонстрационные стенды. |
| Publisher/Subscriber | `message_broker/src/application/services.py`, `sdk/client.py`, `demo_stands/stand_1_pubsub.py` | Producer-логика публикует сообщения в exchange, consumer-логика подписывается на очереди и получает сообщения через streaming gRPC. |
| Очереди сообщений | `message_broker/src/infrastructure/memory/storage.py`, `message_broker/src/infrastructure/persistence/storage.py` | Runtime-очереди используются для доставки consumers, а состояние сообщений хранится в PostgreSQL. |
| FIFO | `message_broker/src/infrastructure/persistence/storage.py` | При выборке сообщений используется сортировка по `created_at`, поэтому сообщения выдаются в порядке публикации внутри очереди. |
| Exchange routing | `message_broker/src/domain/router.py` | Реализованы типы exchange: `DIRECT`, `FANOUT`, `TOPIC`. |
| Protobuf/gRPC | `message_broker/proto/broker.proto`, `message_broker/src/interfaces/grpc/handler.py`, `message_broker/src/interfaces/grpc/broker_pb2.py`, `message_broker/src/interfaces/grpc/broker_pb2_grpc.py` | Через gRPC реализован API брокера: declare exchange, declare queue, bind, publish, consume, ack. |
| Персистентность | `message_broker/src/infrastructure/persistence/storage.py` | В PostgreSQL сохраняются сообщения, очереди, exchanges, bindings и статусы доставки. |
| Восстановление после перезапуска | `message_broker/src/application/services.py`, `message_broker/src/infrastructure/persistence/storage.py` | При старте брокер загружает из БД exchanges, queues и bindings, затем восстанавливает доступные сообщения для доставки. |
| Гарантия доставки | `message_broker/src/application/services.py`, `message_broker/src/infrastructure/persistence/storage.py` | Реализована гарантия `at-least-once`: сообщение помечается `in_flight`, после ACK становится `delivered`; если ACK не пришёл, сообщение может быть выдано повторно. |
| ACK | `message_broker/src/interfaces/grpc/handler.py`, `message_broker/src/application/services.py`, `sdk/client.py` | Consumer подтверждает обработку сообщения через `AckMessage`; после этого сообщение больше не выдаётся. |
| Клиентская библиотека | `sdk/client.py`, `sdk/__init__.py` | SDK скрывает gRPC-вызовы и даёт методы `declare_exchange`, `declare_queue`, `bind_queue`, `publish`, `consume`, `ack`. |
| Docker / Docker Compose | `message_broker/Dockerfile`, `docker-compose.yml` | Через Docker Compose запускаются broker и PostgreSQL. |
| Тесты | `message_broker/tests/test_router.py`, `message_broker/tests/test_delivery.py` | Unit-тесты проверяют роутинг и поведение доставки после ACK/NACK. |
| Документация и схемы | `README.md` | В README описаны архитектура, модель данных, запуск, SDK, демонстрационные стенды и отчёт по критериям оценивания. |

### Дополнительный функционал

Помимо обязательной части я добавил несколько дополнительных возможностей:

- `TOPIC` exchange с шаблонами `*` и `#` - реализован в `message_broker/src/domain/router.py`.
- `visibility timeout` - если consumer получил сообщение, но не отправил ACK, сообщение снова становится доступным после таймаута; реализовано в `message_broker/src/infrastructure/persistence/storage.py`.
- Dead Letter состояние - после превышения количества попыток сообщение переводится в `dead_letter`; реализовано в `message_broker/src/infrastructure/persistence/storage.py`.
- Метрики в формате Prometheus - реализованы в `message_broker/src/main.py`, доступны по адресу `http://localhost:8001/metrics`.
- Демонстрационные стенды для защиты - лежат в `demo_stands/`.

### Что показываю на финальной сдаче

Для демонстрации я подготовил три сценария:

1. `demo_stands/stand_1_pubsub.py` - показывает Pub/Sub и `FANOUT`, одно сообщение приходит в две очереди.
2. `demo_stands/stand_2_ack_no_duplicates.py` - показывает, что после ACK сообщение повторно не появляется.
3. `demo_stands/stand_3_redelivery_without_ack.py` - показывает `at-least-once`: если ACK не отправить, сообщение возвращается после `visibility timeout`.

Отдельно можно показать метрики:

```bash
curl http://localhost:8001/metrics
```

По ним видно количество сообщений в состояниях `pending`, `in_flight`, `delivered`, `dead_letter`, а также количество очередей и exchanges.

## Что реализовано

- Публикация и получение сообщений по модели Publisher/Subscriber.
- Exchange и очереди:
  - `DIRECT` - сообщение попадает в очередь по точному routing key;
  - `FANOUT` - сообщение копируется во все привязанные очереди;
  - `TOPIC` - поддерживаются шаблоны `*` и `#`.
- Несколько очередей и несколько consumers.
- FIFO-порядок внутри очереди.
- Персистентность через PostgreSQL:
  - сохраняются сообщения;
  - сохраняются exchanges, queues и bindings;
  - после перезапуска брокер восстанавливает топологию.
- Подтверждение доставки через ACK.
- Сообщения, которые уже подтверждены, повторно не выдаются.
- Гарантия доставки `at-least-once`.
- `visibility timeout`: если consumer получил сообщение, но не отправил ACK, сообщение снова станет доступно после таймаута.
- Dead Letter состояние: после нескольких неудачных доставок сообщение переводится в `dead_letter`.
- Метрики в формате Prometheus.
- Python SDK для publisher/consumer.
- Docker Compose для запуска брокера и базы.
- Unit-тесты для роутинга и доставки.
- Демонстрационные стенды для защиты.

## Общая схема

```mermaid
graph TB
    Producer[Producer через SDK] --> GRPC[gRPC API]
    Consumer[Consumer через SDK] --> GRPC
    GRPC --> Service[BrokerService]
    Service --> Router[Exchange Router]
    Router --> RuntimeQueues[Очереди в памяти]
    Service --> Postgres[(PostgreSQL)]
    RuntimeQueues --> Service
    Service --> Metrics[Метрики]
```

PostgreSQL здесь является основным хранилищем. Очереди в памяти нужны не как единственный источник данных, а как быстрый runtime-слой, чтобы будить consumers. Перед выдачей сообщения broker всё равно атомарно помечает его в PostgreSQL как `in_flight`.

## Модель данных

```mermaid
erDiagram
    EXCHANGES ||--o{ BINDINGS : has
    QUEUES ||--o{ BINDINGS : has
    MESSAGES ||--o{ QUEUE_MESSAGES : routed
    QUEUES ||--o{ QUEUE_MESSAGES : stores

    EXCHANGES {
        string name PK
        string type
    }
    QUEUES {
        string name PK
        float created_at
    }
    BINDINGS {
        string exchange_name PK
        string queue_name PK
        string binding_key PK
    }
    MESSAGES {
        string id PK
        string routing_key
        string payload
        float timestamp
    }
    QUEUE_MESSAGES {
        string queue_name PK
        string message_id PK
        string status
        int attempts
        float locked_until
        float delivered_at
    }
```

## Статусы доставки

Основной жизненный цикл сообщения в очереди:

```text
pending -> in_flight -> delivered
```

Что это значит:

- `pending` - сообщение лежит в очереди и ждёт consumer;
- `in_flight` - сообщение уже выдано consumer, broker ждёт ACK;
- `delivered` - consumer подтвердил сообщение, повторно оно не выдаётся;
- `dead_letter` - сообщение слишком много раз не было подтверждено.

Я не заявляю `exactly-once`, потому что в таком брокере это нельзя честно гарантировать без транзакционной связки между обработкой на стороне consumer и ACK. Реализован нормальный для брокеров вариант `at-least-once`.

## Запуск

В корне проекта нужен `.env`:

```env
DATABASE_URL=postgres://squirrel:squirrel_pass@postgres:5432/squirrelmq
POSTGRES_USER=squirrel
POSTGRES_PASSWORD=squirrel_pass
POSTGRES_DB=squirrelmq
```

Запуск брокера и PostgreSQL:

```bash
docker compose up --build
```

После запуска:

- gRPC broker доступен на `localhost:50051`;
- метрики доступны на `http://localhost:8001/metrics`;
- PostgreSQL проброшен наружу на `localhost:5433`.

Проверка метрик:

```bash
curl http://localhost:8001/metrics
```

## Демонстрационные стенды

Я подготовил отдельные стенды, чтобы на защите можно было показать поведение без ручной настройки очередей.

### Стенд 1: Pub/Sub и FANOUT

Показывает, что одно опубликованное событие попадает в несколько очередей.

```bash
venv/bin/python demo_stands/stand_1_pubsub.py
```

Что должно быть видно:

- создаётся отдельный exchange;
- создаются две очереди;
- публикуются 3 сообщения;
- обе очереди получают одинаковый набор сообщений.

### Стенд 2: ACK и отсутствие дублей

Показывает главный фикс: прочитанное и подтверждённое сообщение больше не появляется.

```bash
venv/bin/python demo_stands/stand_2_ack_no_duplicates.py
```

Ожидаемый вывод в конце:

```text
OK: после ACK сообщение повторно не выдалось.
```

### Стенд 3: повторная доставка без ACK

Показывает `at-least-once`: если consumer получил сообщение, но не подтвердил его, broker выдаст это же сообщение повторно после `visibility timeout`.

```bash
venv/bin/python demo_stands/stand_3_redelivery_without_ack.py
```

Ожидаемый смысл вывода:

- сообщение получено первый раз без ACK;
- скрипт ждёт timeout;
- то же сообщение приходит снова;
- после ACK оно больше не висит в очереди.

## Пример SDK

```python
import asyncio
from sdk import ExchangeType, SquirrelClient


async def main():
    client = SquirrelClient()
    await client.connect()

    await client.declare_exchange("events", ExchangeType.FANOUT)
    await client.declare_queue("audit")
    await client.bind_queue("audit", "events", "user.created")

    message_id = await client.publish("events", "user.created", "user-1")
    print(message_id)

    await client.close()


asyncio.run(main())
```

## Тесты

Запуск unit-тестов:

```bash
cd message_broker
../venv/bin/python -m unittest discover -s tests
```

Проверяется:

- роутинг `FANOUT`;
- роутинг `TOPIC`;
- что ACK убирает сообщение из дальнейшей выдачи;
- что NACK/неподтверждённое сообщение можно вернуть в доставку.
