from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 使用SQLite作为数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./file_upload_system.db"

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 确保数据库文件存在
db_file = "./file_upload_system.db"
if not os.path.exists(db_file):
    print(f"数据库文件不存在: {db_file}")
    # 这将触发SQLAlchemy创建数据库
    with engine.connect() as conn:
        pass
    print(f"已创建新数据库文件: {db_file}")

# 创建数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础类
Base = declarative_base()

# 获取数据库会话的函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        print(f"数据库会话出错: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close() 