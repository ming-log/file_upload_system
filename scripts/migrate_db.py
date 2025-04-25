import sys
import os
import sqlite3

# 将父目录添加到模块搜索路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 获取数据库路径
db_path = "file_upload_system.db"

def migrate_db():
    # 建立数据库连接
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查allowed_file_types列是否已存在
        cursor.execute("PRAGMA table_info(assignments)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 如果字段不存在，则添加
        if "allowed_file_types" not in column_names:
            print("在Assignment表中添加allowed_file_types列...")
            # SQLite不支持直接添加带默认值的列，所以必须使用PRAGMA foreign_keys
            cursor.execute("PRAGMA foreign_keys=off")
            
            # 添加新列
            cursor.execute("ALTER TABLE assignments ADD COLUMN allowed_file_types TEXT")
            
            # 更新所有现有记录，设置默认值
            cursor.execute("UPDATE assignments SET allowed_file_types='.pdf,.docx'")
            
            cursor.execute("PRAGMA foreign_keys=on")
            
            print("迁移成功完成")
        else:
            print("allowed_file_types列已存在，无需迁移")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db() 