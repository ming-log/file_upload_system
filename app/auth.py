from datetime import datetime, timedelta
from typing import Optional, Union
import importlib.metadata
import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# 密钥和加密算法配置
SECRET_KEY = "c9eb501bead94f349608af6d3a7e2733a83fc02f7d9342b3bba61c793e66a26c"  # 更安全的密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 天

# 使用更直接的方式处理密码哈希，避免passlib与bcrypt版本兼容问题
def get_password_hash(password):
    """哈希密码"""
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    """验证密码"""
    try:
        if isinstance(plain_password, str):
            plain_password = plain_password.encode('utf-8')
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        print(f"验证密码: 明文密码长度={len(plain_password)}, 哈希密码长度={len(hashed_password)}")
        
        # 检查哈希是否是有效的bcrypt格式
        if not hashed_password.startswith(b'$2'):
            print("哈希密码格式无效，不是bcrypt格式")
            return False
            
        result = bcrypt.checkpw(plain_password, hashed_password)
        print(f"密码验证结果: {result}")
        return result
    except Exception as e:
        print(f"密码验证错误: {e}")
        return False

# 为向后兼容保留CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 修改OAuth2PasswordBearer以处理Cookie认证
class CookieOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # 先尝试从cookie中获取token
        token = request.cookies.get("access_token")
        if token:
            scheme, param = get_authorization_scheme_param(token)
            if scheme.lower() == "bearer":
                return param
        
        # 如果cookie中没有，则尝试从Authorization头获取
        return await super().__call__(request)

oauth2_scheme = CookieOAuth2PasswordBearer(tokenUrl="login")

def authenticate_user(db: Session, username: str, password: str):
    """认证用户"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 从请求上下文中获取token，独立的函数以便复用
async def get_token_from_request(request: Request):
    # 尝试从cookie中获取token
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token[7:]  # 去掉"Bearer "前缀
    
    # 如果cookie中没有，则尝试从Authorization头获取
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    # 调试日志
    print(f"获取到的Token: {token}")
    
    return token

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """获取当前用户，支持从cookie和authorization header获取token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的身份认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = await get_token_from_request(request)
    
    if not token:
        print("未找到token")
        raise credentials_exception
    
    try:
        # 调试解码过程
        print(f"尝试解码Token: {token[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        print(f"解码Token成功, username: {username}")
        
        if username is None:
            print("Token中没有username")
            raise credentials_exception
    except JWTError as e:
        print(f"解码Token失败: {str(e)}")
        raise credentials_exception
    
    # 查找用户
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        print(f"数据库中未找到用户: {username}")
        raise credentials_exception
    
    print(f"认证成功: {username}, 角色: {user.role}")
    return user

# 完全重写这个函数以避免Request依赖注入问题
async def get_current_user_from_depends(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """使用标准OAuth2方式获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的身份认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
        
    return user

# 角色权限装饰器
def admin_required(current_user: User = Depends(get_current_user_from_depends)):
    """检查用户是否为管理员"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )
    return current_user

def teacher_required(current_user: User = Depends(get_current_user_from_depends)):
    """检查用户是否为教师"""
    if current_user.role != "teacher" and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要教师权限",
        )
    return current_user 