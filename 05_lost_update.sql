-- lost update
-- это когда две транзакции читают одно значение и потом одна запись затирает другую
-- запускать в двух окнах psql

-- session a
begin transaction isolation level read committed;
select balance from accounts where id = 1;
-- было 1000 считаем что надо списать 100 и записать 900

-- session b
begin transaction isolation level read committed;
select balance from accounts where id = 1;
-- тут тоже видим 1000 и тоже считаем 900

-- session a
update accounts set balance = 900 where id = 1;
commit;

-- session b
update accounts set balance = 900 where id = 1;
commit;

-- проверка
select balance from accounts where id = 1;
-- будет 900 хотя если списали два раза должно быть 800

-- возвращаем обратно
update accounts set balance = 1000 where id = 1;
