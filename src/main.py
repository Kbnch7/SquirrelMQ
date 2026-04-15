from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from .database import get_async_session, init_db
from .models import Order, Product, OrderItem, Customer
from .schemas import OrderCreate, ProductCreate, EmailUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing database...")
    await init_db()
    print("Database tables created.")
    yield
    print("Shutting down...")

app = FastAPI(title="Online Store API", lifespan=lifespan)


@app.post("/orders/")
async def create_order(order: OrderCreate, session: AsyncSession = Depends(get_async_session)):
    async with session.begin():
        new_order = Order(customer_id=order.customer_id, total_amount=0.0)
        session.add(new_order)
        await session.flush()

        total_sum = 0.0
        for item in order.items_data:
            res = await session.execute(select(Product).where(Product.product_id == item.product_id))
            product = res.scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

            subtotal = product.price * item.quantity
            total_sum += subtotal

            order_item = OrderItem(
                order_id=new_order.order_id,
                product_id=product.product_id,
                quantity=item.quantity,
                subtotal=subtotal
            )
            session.add(order_item)

        new_order.total_amount = total_sum
        
    return {"status": "Order created", "order_id": new_order.order_id, "total": total_sum}

@app.put("/customers/{customer_id}/email")
async def update_customer_email(customer_id: int, new_email: EmailUpdate, session: AsyncSession = Depends(get_async_session)):
    async with session.begin():
        res = await session.execute(select(Customer).where(Customer.customer_id == customer_id))
        customer = res.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        customer.email = new_email.new_email
    return {"status": "Email updated"}

@app.post("/products/")
async def add_product(product: ProductCreate, session: AsyncSession = Depends(get_async_session)):
    async with session.begin():
        new_product = Product(product_name=product.name, price=product.price)
        session.add(new_product)
    return {"status": "Product added", "product_id": new_product.product_id}
