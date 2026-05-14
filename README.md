# SquirrelMQ

SquirrelMQ - мой учебный брокер сообщений. Я делал его как небольшой аналог RabbitMQ: есть exchange, queue, binding, publisher, consumer, подтверждение доставки и хранение состояния в PostgreSQL.

Проект написан на Python, сетевой протокол сделан через gRPC/Protobuf, для клиента есть простой SDK.

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
OK: after ACK message was not delivered again
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
