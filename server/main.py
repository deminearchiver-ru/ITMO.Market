from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATABASE_URL = f"sqlite:///{BASE_DIR / 'rustore.db'}"

APPS_DIR = BASE_DIR / "apps"

engine = create_engine(
  DATABASE_URL,
  connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
  pass


class Category(Base):
  __tablename__ = "categories"

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
  slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

  apps: Mapped[list["App"]] = relationship(back_populates="category")


class App(Base):
  __tablename__ = "apps"

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(128), nullable=False)
  developer: Mapped[str] = mapped_column(String(128), nullable=False)
  description_short: Mapped[str] = mapped_column(String(512), nullable=False)
  description_full: Mapped[str] = mapped_column(Text, nullable=False)
  age_rating: Mapped[int] = mapped_column(nullable=False)
  category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
  package_name: Mapped[str] = mapped_column(String(128), nullable=False)
  version: Mapped[str] = mapped_column(String(128), nullable=False)
  version_code: Mapped[int] = mapped_column(nullable=False)
  category: Mapped[Category] = relationship(back_populates="apps")


class CategoryOut(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  slug: str


class CategoryWithCount(CategoryOut):
  apps_count: int


class AppPreview(BaseModel):
  id: int
  name: str
  description: str
  category: CategoryOut


class AppDetail(AppPreview):
  developer: str
  description_full: str
  age_rating: int
  screenshot_count: int
  version: str
  version_code: int
  size_kb: int



class AppList(BaseModel):
  items: list[AppPreview]
  total: int
  limit: int
  offset: int


def get_db() -> Generator[Session, None, None]:
  with SessionLocal() as db:
    yield db

def app_dir(app_id:int)->Path:
  return APPS_DIR / str(app_id)

def app_preview(app: App) -> AppPreview:
  return AppPreview(
    id=app.id,
    name=app.name,
    description=app.description_short,
    category=app.category,
  )

def seed_demo_data() -> None:
  with SessionLocal() as db:
    if db.scalar(select(func.count(Category.id))):
      return

    categories = [
      Category(name="Финансы", slug="finance"),
      Category(name="Инструменты", slug="tools"),
      Category(name="Игры", slug="games"),
      Category(name="Государственные", slug="government"),
      Category(name="Транспорт", slug="transport")
    ]
    db.add_all(categories)
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
  (BASE_DIR / "apps").mkdir(exist_ok=True)
  Base.metadata.create_all(engine)
  seed_demo_data()
  yield


app = FastAPI(
  title="RuStore Showcase API",
  version="1.0.0",
  description="API MVPшного каталога приложений",
  lifespan=lifespan
)

#app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/v1/health")
def health():
  return {"status": "ok"}


@app.get("/api/v1/categories", response_model=list[CategoryWithCount])
def get_categories(db: Session = Depends(get_db)):
  categories = db.scalars(select(Category).order_by(Category.name)).all()
  result = []
  for category in categories:
    count = db.scalar(
      select(func.count(App.id)).where(App.category_id == category.id)
    )
    result.append({
      "id": category.id,
      "name": category.name,
      "slug": category.slug,
      "apps_count": count
    })
  return result


@app.get("/api/v1/apps", response_model=AppList)
def get_apps(
  category: str | None = None,
  limit: int = Query(default=20, ge=1, le=100),
  offset: int = Query(default=0, ge=0),
  db: Session = Depends(get_db)
):
  query = select(App).join(Category)
  count_query = select(func.count(App.id)).join(Category)

  if category is not None:
    query = query.where(Category.slug == category)
    count_query = count_query.where(Category.slug == category)

  total = db.scalar(count_query) or 0
  apps = db.scalars(
    query
    .order_by(App.id)
    .offset(offset)
    .limit(limit)
  ).all()

  return AppList(
    items=[app_preview(item) for item in apps],
    total=total,
    limit=limit,
    offset=offset
  )

def get_screenshots(app_id:int)->list[Path]:
  directory = app_dir(app_id) / "screenshots"
  if not directory.is_dir():
    return []
  return sorted(
    (
      path for path in directory.glob('*.png')
      if path.stem.isdigit()
    ),
    key=lambda path: int(path.stem)
  )

@app.get("/api/v1/apps/{app_id}", response_model=AppDetail)
def get_app(app_id: int, db: Session = Depends(get_db)):
  item = db.get(App, app_id)
  if item is None:
    raise HTTPException(status_code=404, detail="App not found")

  preview = app_preview(item)
  size=Path(APPS_DIR/str(app_id)/'release.apk').stat().st_size//1024

  return AppDetail(
    **preview.model_dump(),
    developer=item.developer,
    description_full=item.description_full,
    age_rating=item.age_rating,
    screenshot_count=len(get_screenshots(app_id)),
    version=item.version,
    version_code=item.version_code,
    size_kb=size,
  )

@app.get("/api/v1/apps/{app_id}/icon")
def get_app_icon(app_id: int, db: Session = Depends(get_db)):
  item = db.get(App, app_id)

  if item is None:
    raise HTTPException(status_code=404, detail="App not found")

  path = app_dir(app_id) / "icon.png"

  if not path.is_file():
    raise HTTPException(status_code=404, detail="Icon not found")

  return FileResponse(path, media_type="image/png")


@app.get("/api/v1/apps/{app_id}/apk")
def get_app_apk(app_id: int, db: Session = Depends(get_db)):
  item = db.get(App, app_id)

  if item is None:
    raise HTTPException(status_code=404, detail="App not found")

  path = app_dir(app_id) / "release.apk"

  if not path.is_file():
    raise HTTPException(status_code=404, detail="APK not found")

  return FileResponse(
    path,
    media_type="application/vnd.android.package-archive",
    filename="app.apk"
  )

@app.get("/api/v1/apps/{app_id}/screenshots/{screenshot_id}")
def get_screenshot(
  app_id: int,
  screenshot_id: int,
  db: Session = Depends(get_db)
):
  if db.get(App, app_id) is None:
    raise HTTPException(status_code=404, detail="App not found")

  screenshots=get_screenshots(app_id)

  if not 0<=screenshot_id<len(screenshots):
    raise HTTPException(status_code=404, detail="Invalid screenshot id")


  path = app_dir(app_id) / "screenshots" / f"{screenshots[screenshot_id]}"

  if not path.is_file():
    raise HTTPException(status_code=404, detail="Screenshot not found")

  return FileResponse(path, media_type="image/png")
