from abc import ABC, abstractmethod
import requests
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine, String, Integer, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase, mapped_column, Mapped

# Абстрактный класс — задаёт обязательные методы для загрузчика данных
class Model(ABC):
    url = 'https://dummyjson.com/products'
    
    @abstractmethod
    def download(self, categories):
        # Загружает данные по указанным категориям
        pass
    
    @abstractmethod
    def to_dict(self, data):
        # Преобразует данные в словарь
        pass

# Singleton-загрузчик данных из DummyJSON (разные способы загрузки: sync/async/threaded)
class Loader(Model):
    _instance = None

    def __new__(cls):
        # гарантируем что Loader существует в одном экземпляре
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def download(self, categories):
        # синхронная загрузка — по очереди, категория за категорией
        all_products = []
        for category in categories:
            url = f'{self.url}/category/{category}'   # динамический url
            response = requests.get(url)
            data = response.json()
            all_products.extend(data['products'])  # добавляем к общему списку
        return all_products

    async def async_download(self, categories):
        # асинхронная загрузка — все категории параллельно
        all_products = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for category in categories:
                url = f'{self.url}/category/{category}'   # динамический url
                tasks.append(session.get(url))
            responses = await asyncio.gather(*tasks)
            for response in responses:
                data = await response.json()
                all_products.extend(data['products'])  # добавляем к общему списку
        return all_products
    
    async def async_download_batches(self, categories, batch_size=2):
        # асинхронная загрузка пакетами — чтобы не перегружать сервер
        all_products = []
        # делим на пакеты — обычным способом
        batches = [categories[i:i+batch_size] for i in range(0, len(categories), batch_size)]
    
        async with aiohttp.ClientSession() as session:
            for batch in batches:
                tasks = []
                for category in batch:
                    url = f'{self.url}/category/{category}'
                    tasks.append(session.get(url))
                responses = await asyncio.gather(*tasks)
                for response in responses:
                    data = await response.json()
                    all_products.extend(data['products'])  # добавляем к общему списку
        return all_products    

    def threaded_download(self, categories, batch_size=2):
        # многопоточная загрузка через ThreadPoolExecutor
        all_products = []

        # метод для загрузки одной категории
        def fetch_category(category):
            url = f'{self.url}/category/{category}'
            response = requests.get(url)
            return response.json()['products']

        # делим на пакеты — обычным способом
        batches = [categories[i:i+batch_size] for i in range(0, len(categories), batch_size)]
        for batch in batches:   
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(fetch_category, batch))
                # results — список списков, нужно объединить
                for products in results:
                    all_products.extend(products)

        return all_products


    def to_dict(self, data):
        # превращает список товаров в словарь {название: товар}
        return {item['title']: item for item in data}

# Класс подключения к базе данных — создаёт engine и сессию    
class Connection:

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.engine = create_engine(self.connection_string)
        self.session =  sessionmaker(bind=self.engine)()

# Базовый класс для всех таблиц (SQLAlchemy ORM)
class BaseModel(DeclarativeBase):
    pass

# Таблица "категории" — например beauty, smartphones
class Category(BaseModel):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    def __init__(self, data: dict):
        self.name = data["name"]

# Таблица "бренды" — например Apple, Samsung
class Brand(BaseModel):
    __tablename__ = 'brands'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)

    def __init__(self, data: dict):
        self.name = data["name"]

# Таблица "товары" — связана с Brand и Category через Foreign Key
class Product(BaseModel):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    def __init__(self, data: dict):
        self.title = data["title"]
        self.description = data["description"]
        self.price = data["price"]
        self.brand_id = data.get("brand_id", None)
        self.category_id = data.get("category_id", None)

# DTO (Data Transfer Object) — облегчённая версия Product для вывода/передачи данных
# не привязан к базе, просто хранит нужные поля в удобном виде
class ProductDTO:
    def __init__(self, product: Product, brand_name: str, category_name: str):
        self.title = product.title
        self.price = product.price
        self.brand = brand_name
        self.category = category_name

    def __repr__(self):
        return f"{self.title} | {self.price}$ | {self.brand} | {self.category}"

# Находит категорию по имени в базе, либо создаёт новую если её нет
def get_or_create_category(session, category_name):
    category = session.query(Category).filter_by(name=category_name).first()
    if not category:
        category = Category({"name": category_name})
        session.add(category)
        session.commit()
    return category

# Находит бренд по имени в базе, либо создаёт новый если его нет
def get_or_create_brand(session, brand_name):
    brand = session.query(Brand).filter_by(name=brand_name).first()
    if not brand:
        brand = Brand({"name": brand_name})
        session.add(brand)
        session.commit()
    return brand

# Сохраняет один товар в базу, подставляя id связанных категории и бренда
def save_product(session, product_data):
    category = get_or_create_category(session, product_data["category"])
    brand = get_or_create_brand(session, product_data.get("brand", "Unknown"))
    
    product = Product(product_data)
    product.category_id = category.id
    product.brand_id = brand.id
    
    session.add(product)
    session.commit()


if __name__ == "__main__":
    # Подключаемся к базе (SQLite, хранится в файле my_database.db)
    conn = Connection("sqlite:///my_database.db")

    # Создаём таблицы в базе, если их ещё нет
    BaseModel.metadata.create_all(conn.engine)
    
    # Загружаем товары из DummyJSON по нужным категориям
    loader = Loader()
    products_data = loader.download(["beauty", "smartphones"])
    
    # Сохраняем каждый товар в базу
    for product_data in products_data:
        save_product(conn.session, product_data)
    
    print(f"Сохранено товаров: {len(products_data)}")

    # Получаем все товары из базы и выводим
    all_products = conn.session.query(Product).all()
    for product in all_products:
        print(f"{product.title} — {product.price}$")

    # Преобразуем товары в DTO (с подгрузкой названий бренда и категории) и выводим
    print("\n--- DTO ---")
    for product in all_products:
        brand = conn.session.query(Brand).filter_by(id=product.brand_id).first()
        category = conn.session.query(Category).filter_by(id=product.category_id).first()
        
        dto = ProductDTO(product, brand.name, category.name)
        print(dto)
