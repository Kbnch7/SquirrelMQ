-- dirty read в postgres не получается сделать
-- даже если написать read uncommitted он все равно работает как read committed
-- запускать в двух окнах psql

-- session a
begin transaction isolation level read uncommitted;
select balance from accounts where id = 1;
-- должно быть 1000

-- session b
begin transaction isolation level read uncommitted;
update accounts set balance = 500 where id = 1;
-- commit не делаем

-- session a
select balance from accounts where id = 1;
-- будет 1000 а не 500 потому что изменение еще не сохранено

-- session b
rollback;

-- session a
select balance from accounts where id = 1;
-- опять 1000
commit;
