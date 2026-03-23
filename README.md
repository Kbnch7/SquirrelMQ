# Разработка брокера сообщений (Protobuf Over TCP)
## Обзор проекта
Цель проекта — разработка легковесного брокера сообщений для организации асинхронного взаимодействия между микросервисами. Система реализует классическую модель маршрутизации через точки обмена (Exchanges) и очереди (Queues).

## Архитектура системы
Networking Layer (TCP Server): Принимает входящие соединения, отвечает за хендшейк и чтение байтов из сокета.

Protocol Parser (Protobuf): Десериализует байты в типизированные объекты (Frame).

Exchange Router: «Мозги» системы. Принимает сообщение и, согласно таблице маршрутизации (Bindings), определяет, в какие очереди его направить.

Queue Manager: Управляет жизненным циклом очередей в оперативной памяти и порядком выдачи сообщений (FIFO).

Persistence Layer (PostgreSQL): Отвечает за транзакционную запись сообщений и хранение конфигурации (топики, привязки).

Delivery Service: Следит за отправкой сообщений активным подписчикам и ожидает подтверждения (ACK).

## Схема архитектуры
```mermaid
graph TB
subgraph Network_IO [1. Сетевой Слой]
    TCPServer[TCP/gRPC Сервер]
    Auth[Аутентификация]
end

subgraph Core_Engine [2. Ядро Брокера]
    direction TB
    ReqParser["Десериализатор (Proto)"]
    Router{Роутер}
end

subgraph State_Management [3. Состояние и Хранение]
    direction LR
    subgraph Memory_Layer [RAM]
        InMemQueues[[Очереди в памяти]]
        ConnDB[[Таблица подключений]]
    end

    subgraph Persistent_Layer [Disk]
        WAL[(Postgres)]
    end
end

TCPServer --> Auth
Auth --> ReqParser
ReqParser --> Router
Router --> InMemQueues
InMemQueues --> WAL
InMemQueues --> ConnDB
ConnDB --> TCPServer
```


## Формат сообщения
``` proto
syntax = "proto3";

message Message {
  string id = 1;          
  string routing_key = 2;
  bytes payload = 3;      
  int64 timestamp = 4;  
  map<string, string> metadata = 5;
}
```

## Структура БД
```mermaid
erDiagram
    MESSAGES {
        string id PK
        string exchange_id FK
        blob payload
        string routing_key
        string status
        string idempotency_key
        string metadata
        int64 timestamp
    }
    QUEUES {
        string id PK
        string name
        boolean is_durable
    }
    EXCHANGES {
        string id PK
        string name
        string type
    }
    BINDINGS {
        string exchange_id FK
        string queue_id FK
        string routing_key
    }

    EXCHANGES ||--o{ BINDINGS : "routes_to"
    QUEUES ||--o{ BINDINGS : "bound_via"
    EXCHANGES ||--o{ MESSAGES : "manages"
```

## Технический стек
| Технология | Выбор | Обоснование |
| ---------- | ------| ------------|
| Язык | Python 3.12 | Высокая скорость разработки логики брокера и отличная поддержка asyncio.|
| Сетевой слой | Asyncio Streams | Позволяет эффективно обрабатывать тысячи конкурентных TCP-соединений на одном ядре. |
| Протокол | Protobuf | Бинарный формат быстрее и компактнее JSON. Легко генерировать SDK для разных ЯП. |
| База данных | PostgreSQL | Поддержка транзакций (ACID) критична для гарантии доставки. Инструменты типа SKIP LOCKED упрощают работу с очередями. |

## План разработки

### Протокол и Транспорт:

- Описание всех .proto фреймов (Connect, Publish, Subscribe, Ack).

- Создание базового TCP-сервера, который "эхом" отвечает на Protobuf-сообщения.

### Маршрутизация и Память:

- Реализация Exchange и Queue в оперативной памяти.

- Логика распределения сообщений между подписчиками (Round Robin).

### Персистентность:

- Интеграция Postgres.

- Реализация записи сообщения в БД перед отправкой ACK паблишеру.

- Механизм восстановления очереди из БД при старте сервера.

### Клиентское SDK и Тесты:

- Написание Python-библиотеки для удобной работы с брокером.

- Создание Docker-compose окружения с тремя тестовыми сервисами.
