-- non repeatable read
-- это когда в одной транзакции читаем одну строку 2 раза а значение меняется
-- запускать в двух окнах psql

-- session a
begin transaction isolation level read committed;
select balance from accounts where id = 1;
-- должно быть 1000

-- session b
begin transaction isolation level read committed;
update accounts set balance = 700 where id = 1;
commit;

-- session a
select balance from accounts where id = 1;
-- теперь будет 700
commit;

-- возвращаем обратно чтобы можно было запускать дальше
update accounts set balance = 1000 where id = 1;
