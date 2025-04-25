from datetime import datetime
from fastapi.templating import Jinja2Templates

# 创建Jinja2模板实例
templates = Jinja2Templates(directory="templates")

# 添加自定义过滤器
def datetime_format(value):
    """将datetime格式化为年月日时分秒格式，不显示毫秒"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return value

# 注册过滤器到模板环境中
templates.env.filters["datetime_format"] = datetime_format 