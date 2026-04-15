from pydantic import BaseModel

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_id: int
    items_data: list[OrderItemCreate]

class ProductCreate(BaseModel):
    name: str
    price: float

class EmailUpdate(BaseModel):
    new_email: str
