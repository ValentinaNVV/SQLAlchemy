from sqlalchemy import create_engine, String, Integer, Float
from sqlalchemy.orm import sessionmaker, DeclarativeBase, mapped_column, Mapped


class Connection:

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.engine = create_engine(self.connection_string)
        self.session =  sessionmaker(bind=self.engine)()


class BaseModel(DeclarativeBase):
    pass

class Category(BaseModel):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    def __init__(self, data: dict):
        self.name = data["name"]

class Brand(BaseModel):
    __tablename__ = 'brands'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    def __init__(self, data: dict):
        self.name = data["name"]

class Product(BaseModel):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    brand: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)

    def __init__(self, data: dict):
        self.title = data["title"]
        self.description = data["description"]
        self.price = data["price"]
        self.brand = data.get("brand", "")
        self.category = data["category"]

if __name__ == "__main__":
    # Подключаемся к базе
    conn = Connection("sqlite:///my_database.db")
    
    # Создаём все таблицы в базе
    BaseModel.metadata.create_all(conn.engine)
    
    print("Таблицы созданы успешно!")