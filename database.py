import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения

class Database:
    def __init__(self):
        self.init_database()
    
    def get_connection(self):
        """Создает соединение с PostgreSQL"""
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'healthsync'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        conn.autocommit = False
        return conn
    
    def init_database(self):
        """Инициализация всех таблиц в PostgreSQL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Таблица пользователей
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(100) UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                date_of_birth DATE,
                gender VARCHAR(20) CHECK(gender IN ('male', 'female', 'other')),
                height DECIMAL(5,2),
                weight DECIMAL(5,2),
                activity_level VARCHAR(20) CHECK(activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')),
                avatar_type VARCHAR(50) DEFAULT 'default',
                theme VARCHAR(50) DEFAULT 'light',
                sync_coins INTEGER DEFAULT 0,
                energy_level DECIMAL(5,2) DEFAULT 50.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
            ''')
            
            # Таблица ежедневных данных
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_data (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                steps INTEGER DEFAULT 0,
                distance DECIMAL(10,2) DEFAULT 0.0,
                calories_burned DECIMAL(10,2) DEFAULT 0.0,
                active_minutes INTEGER DEFAULT 0,
                sleep_hours DECIMAL(5,2) DEFAULT 0.0,
                sleep_quality INTEGER,
                bedtime TIMESTAMP,
                wakeup_time TIMESTAMP,
                water_ml INTEGER DEFAULT 0,
                breakfast BOOLEAN DEFAULT FALSE,
                lunch BOOLEAN DEFAULT FALSE,
                dinner BOOLEAN DEFAULT FALSE,
                snacks BOOLEAN DEFAULT FALSE,
                mood VARCHAR(20) CHECK(mood IN ('excellent', 'good', 'neutral', 'bad', 'terrible')),
                stress_level INTEGER,
                meditation_minutes INTEGER DEFAULT 0,
                notes TEXT,
                activity_score DECIMAL(5,2) DEFAULT 0.0,
                recovery_score DECIMAL(5,2) DEFAULT 0.0,
                nutrition_score DECIMAL(5,2) DEFAULT 0.0,
                mental_score DECIMAL(5,2) DEFAULT 0.0,
                overall_balance DECIMAL(5,2) DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date)
            )
            ''')
            
            # Шаблоны привычек
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS habit_templates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                icon VARCHAR(50),
                default_frequency VARCHAR(20) DEFAULT 'daily',
                default_target_value INTEGER,
                default_unit VARCHAR(50),
                is_public BOOLEAN DEFAULT TRUE
            )
            ''')
            
            # Пользовательские привычки
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_habits (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                template_id INTEGER REFERENCES habit_templates(id) ON DELETE SET NULL,
                custom_name VARCHAR(255),
                custom_description TEXT,
                custom_icon VARCHAR(50),
                frequency VARCHAR(20) DEFAULT 'daily',
                target_value INTEGER,
                unit VARCHAR(50),
                reminder_time VARCHAR(10),
                is_reminder_enabled BOOLEAN DEFAULT TRUE,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Выполнение привычек
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS habit_completions (
                id SERIAL PRIMARY KEY,
                habit_id INTEGER NOT NULL REFERENCES user_habits(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                completed_value INTEGER,
                is_completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Цели
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                target_value DECIMAL(10,2),
                current_value DECIMAL(10,2) DEFAULT 0.0,
                unit VARCHAR(50),
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                progress_percentage DECIMAL(5,2) DEFAULT 0.0,
                is_completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP,
                reward_coins INTEGER DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Достижения
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                icon VARCHAR(50),
                category VARCHAR(50),
                requirement_type VARCHAR(50),
                requirement_value INTEGER,
                reward_coins INTEGER DEFAULT 5
            )
            ''')
            
            # Пользовательские достижения
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_achievements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                achievement_id INTEGER NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress INTEGER DEFAULT 0,
                is_unlocked BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, achievement_id)
            )
            ''')
            
            # Уведомления
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                message TEXT,
                type VARCHAR(50),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_time TIMESTAMP
            )
            ''')
            
            conn.commit()
            print("Таблицы успешно созданы в PostgreSQL")
            
            # Добавляем стартовые данные
            self.add_starter_data()
            
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при создании таблиц: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def add_starter_data(self):
        """Добавление стартовых шаблонов привычек и достижений"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Проверяем, есть ли уже шаблоны
            cursor.execute("SELECT COUNT(*) as count FROM habit_templates")
            if cursor.fetchone()[0] == 0:
                # Добавляем шаблоны привычек
                starter_habits = [
                    ('Пить воду', 'Выпивать достаточное количество воды ежедневно', 'water', '💧', 'daily', 2000, 'ml'),
                    ('10,000 шагов', 'Проходить 10,000 шагов в день', 'activity', '👣', 'daily', 10000, 'steps'),
                    ('Ложиться до 23:00', 'Отходить ко сну до 23:00', 'sleep', '🌙', 'daily', 1, 'time'),
                    ('Утренняя зарядка', '10 минут утренней зарядки', 'activity', '🏃', 'daily', 10, 'minutes'),
                    ('Медитация', '5 минут медитации', 'mental', '🧘', 'daily', 5, 'minutes'),
                    ('Фрукты и овощи', 'Съедать 5 порций фруктов и овощей', 'nutrition', '🥗', 'daily', 5, 'portions'),
                    ('Без кофе после 18:00', 'Не пить кофе после 18:00', 'nutrition', '☕', 'daily', 1, 'times'),
                ]
                
                for habit in starter_habits:
                    cursor.execute('''
                    INSERT INTO habit_templates 
                    (name, description, category, icon, default_frequency, default_target_value, default_unit)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', habit)
            
            # Проверяем, есть ли уже достижения
            cursor.execute("SELECT COUNT(*) as count FROM achievements")
            if cursor.fetchone()[0] == 0:
                # Добавляем достижения
                achievements = [
                    ('Первый день', 'Вы начали свой путь к здоровью!', '🎉', 'system', 'one_time', 1, 10),
                    ('Неделя дисциплины', '7 дней подряд выполнения привычек', '🏆', 'streak', 'streak', 7, 25),
                    ('Гидробаланс', 'Выпить 2 литра воды за день', '💦', 'water', 'total', 2000, 15),
                    ('Мастер шагов', 'Пройти 10,000 шагов 5 дней подряд', '👟', 'activity', 'streak', 5, 20),
                    ('Хороший сон', '7+ часов сна 3 ночи подряд', '😴', 'sleep', 'streak', 3, 15),
                    ('Энерджайзер', '100% энергии за день', '⚡', 'energy', 'one_time', 100, 30),
                    ('Месяц здоровья', '30 дней использования приложения', '📅', 'system', 'streak', 30, 50),
                ]
                
                for achievement in achievements:
                    cursor.execute('''
                    INSERT INTO achievements 
                    (name, description, icon, category, requirement_type, requirement_value, reward_coins)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', achievement)
            
            conn.commit()
            print("Стартовые данные добавлены")
            
        except Exception as e:
            conn.rollback()
            print(f"Ошибка при добавлении стартовых данных: {e}")
        finally:
            cursor.close()
            conn.close()

# Создаем глобальный экземпляр БД
db_instance = Database()