from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import bcrypt
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI(
    title="HealthSync API",
    description="Единый центр здоровья и хороших привычек",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Pydantic модели
class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    activity_level: str = "moderate"

class DailyDataCreate(BaseModel):
    user_id: int
    date: Optional[str] = None
    steps: Optional[int] = 0
    water_ml: Optional[int] = 0
    mood: Optional[str] = None
    sleep_hours: Optional[float] = None
    breakfast: Optional[bool] = False
    lunch: Optional[bool] = False
    dinner: Optional[bool] = False
    notes: Optional[str] = None

class HabitCreate(BaseModel):
    user_id: int
    template_id: Optional[int] = None
    custom_name: Optional[str] = None
    target_value: Optional[int] = None
    reminder_time: Optional[str] = None

class GoalCreate(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None
    category: str
    target_value: float
    unit: str
    end_date: str

class HabitCompletion(BaseModel):
    user_id: int
    habit_id: int
    completed_value: Optional[int] = None

# Функция для подключения к БД
def get_db_connection():
    """Создает соединение с PostgreSQL"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'healthsync'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'password')
    )
    return conn

# Основные эндпоинты
@app.get("/")
def read_root():
    return {
        "message": "Welcome to HealthSync API",
        "version": "1.0.0",
        "database": "PostgreSQL",
        "status": "running"
    }

# Работа с пользователями
@app.post("/users")
def create_user(user: UserCreate):
    """Создание нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute(
            "SELECT * FROM users WHERE email = %s OR username = %s", 
            (user.email, user.username)
        )
        existing_user = cursor.fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Email or username already registered")
        
        # Хешируем пароль
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt)
        
        # Создаем пользователя
        cursor.execute('''
        INSERT INTO users 
        (email, username, hashed_password, full_name, date_of_birth, gender, height, weight, activity_level)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, email, username, full_name, created_at
        ''', (
            user.email, user.username, hashed_password.decode('utf-8'), user.full_name,
            user.date_of_birth, user.gender, user.height, user.weight, user.activity_level
        ))
        
        new_user = cursor.fetchone()
        user_id = new_user['id']
        
        # Создаем стартовые привычки
        cursor.execute(
            "SELECT id FROM habit_templates WHERE category IN ('water', 'activity', 'sleep') LIMIT 3"
        )
        starter_templates = cursor.fetchall()
        
        for template in starter_templates:
            cursor.execute('''
            INSERT INTO user_habits (user_id, template_id, is_active)
            VALUES (%s, %s, TRUE)
            ''', (user_id, template['id']))
        
        conn.commit()
        
        return {"message": "User created successfully", "user": new_user}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Получение информации о пользователе"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(
            "SELECT id, email, username, full_name, created_at FROM users WHERE id = %s", 
            (user_id,)
        )
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return dict(user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Ежедневные данные
@app.post("/daily")
def update_daily_data(data: DailyDataCreate):
    """Обновление ежедневных данных"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM users WHERE id = %s", (data.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        today = data.date or date.today().isoformat()
        
        # Проверяем существование записи
        cursor.execute(
            "SELECT id FROM daily_data WHERE user_id = %s AND date = %s",
            (data.user_id, today)
        )
        
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            update_fields = []
            values = []
            
            if data.steps is not None:
                update_fields.append("steps = %s")
                values.append(data.steps)
            if data.water_ml is not None:
                update_fields.append("water_ml = %s")
                values.append(data.water_ml)
            if data.mood is not None:
                update_fields.append("mood = %s")
                values.append(data.mood)
            if data.sleep_hours is not None:
                update_fields.append("sleep_hours = %s")
                values.append(data.sleep_hours)
            if data.breakfast is not None:
                update_fields.append("breakfast = %s")
                values.append(data.breakfast)
            if data.lunch is not None:
                update_fields.append("lunch = %s")
                values.append(data.lunch)
            if data.dinner is not None:
                update_fields.append("dinner = %s")
                values.append(data.dinner)
            if data.notes is not None:
                update_fields.append("notes = %s")
                values.append(data.notes)
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(existing['id'])
                values.append(data.user_id)
                values.append(today)
                
                sql = f'''
                UPDATE daily_data 
                SET {', '.join(update_fields)}
                WHERE id = %s
                '''
                cursor.execute(sql, values)
        else:
            # Создаем новую запись
            cursor.execute('''
            INSERT INTO daily_data 
            (user_id, date, steps, water_ml, mood, sleep_hours, breakfast, lunch, dinner, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                data.user_id, today, data.steps or 0, data.water_ml or 0,
                data.mood, data.sleep_hours, data.breakfast or False,
                data.lunch or False, data.dinner or False, data.notes
            ))
        
        # Пересчитываем энергию
        update_energy_level(data.user_id, today, cursor)
        
        conn.commit()
        
        return {"message": "Daily data updated successfully", "date": today}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/daily/{user_id}")
def get_daily_data(user_id: int, date_str: Optional[str] = None):
    """Получение ежедневных данных"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        target_date = date_str or date.today().isoformat()
        
        cursor.execute(
            "SELECT * FROM daily_data WHERE user_id = %s AND date = %s",
            (user_id, target_date)
        )
        
        daily_data = cursor.fetchone()
        
        if not daily_data:
            # Создаем пустую запись
            cursor.execute(
                "INSERT INTO daily_data (user_id, date) VALUES (%s, %s) RETURNING *",
                (user_id, target_date)
            )
            daily_data = cursor.fetchone()
            conn.commit()
        
        return dict(daily_data)
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Привычки
@app.post("/habits")
def create_habit(habit: HabitCreate):
    """Создание новой привычки"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM users WHERE id = %s", (habit.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Если указан template_id, берем данные из шаблона
        if habit.template_id:
            cursor.execute("SELECT * FROM habit_templates WHERE id = %s", (habit.template_id,))
            template = cursor.fetchone()
            
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            
            name = habit.custom_name or template['name']
            target_value = habit.target_value or template['default_target_value']
            unit = template['default_unit']
            icon = template['icon']
        else:
            if not habit.custom_name:
                raise HTTPException(status_code=400, detail="Custom name is required when no template is provided")
            name = habit.custom_name
            target_value = habit.target_value or 1
            unit = "times"
            icon = "✅"
        
        cursor.execute('''
        INSERT INTO user_habits 
        (user_id, template_id, custom_name, target_value, unit, reminder_time, custom_icon, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING *
        ''', (
            habit.user_id, habit.template_id, name,
            target_value, unit, habit.reminder_time, icon
        ))
        
        new_habit = cursor.fetchone()
        conn.commit()
        
        return {"message": "Habit created successfully", "habit": new_habit}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/habits/{user_id}")
def get_user_habits(user_id: int):
    """Получение привычек пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        today = date.today().isoformat()
        
        cursor.execute('''
        SELECT 
            h.*,
            ht.name as template_name,
            ht.icon as template_icon,
            c.is_completed,
            c.completed_value
        FROM user_habits h
        LEFT JOIN habit_templates ht ON h.template_id = ht.id
        LEFT JOIN habit_completions c ON h.id = c.habit_id AND c.date = %s
        WHERE h.user_id = %s AND h.is_active = TRUE
        ''', (today, user_id))
        
        habits = cursor.fetchall()
        
        return [dict(row) for row in habits]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.post("/habits/complete")
def complete_habit(completion: HabitCompletion):
    """Отметка привычки как выполненной"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование привычки
        cursor.execute(
            "SELECT * FROM user_habits WHERE id = %s AND user_id = %s",
            (completion.habit_id, completion.user_id)
        )
        
        habit = cursor.fetchone()
        
        if not habit:
            raise HTTPException(status_code=404, detail="Habit not found")
        
        today = date.today().isoformat()
        
        # Проверяем, была ли уже выполнена сегодня
        cursor.execute(
            "SELECT * FROM habit_completions WHERE habit_id = %s AND date = %s",
            (completion.habit_id, today)
        )
        
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
            UPDATE habit_completions 
            SET is_completed = TRUE, completed_value = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            ''', (completion.completed_value or habit['target_value'], existing['id']))
        else:
            cursor.execute('''
            INSERT INTO habit_completions 
            (habit_id, date, completed_value, is_completed)
            VALUES (%s, %s, %s, TRUE)
            ''', (completion.habit_id, today, completion.completed_value or habit['target_value']))
        
        # Обновляем streak
        update_habit_streak(completion.habit_id, today, cursor)
        
        # Начисляем энергию и монеты
        award_for_habit_completion(completion.user_id, completion.habit_id, cursor)
        
        conn.commit()
        
        return {"message": "Habit completed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Цели
@app.post("/goals")
def create_goal(goal: GoalCreate):
    """Создание новой цели"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM users WHERE id = %s", (goal.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        cursor.execute('''
        INSERT INTO goals 
        (user_id, title, description, category, target_value, unit, start_date, end_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        ''', (
            goal.user_id, goal.title, goal.description, goal.category,
            goal.target_value, goal.unit, date.today().isoformat(), goal.end_date
        ))
        
        new_goal = cursor.fetchone()
        conn.commit()
        
        return {"message": "Goal created successfully", "goal": new_goal}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@app.get("/goals/{user_id}")
def get_user_goals(user_id: int):
    """Получение целей пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        today = date.today().isoformat()
        
        cursor.execute('''
        SELECT * FROM goals 
        WHERE user_id = %s AND is_completed = FALSE AND end_date >= %s
        ORDER BY end_date ASC
        ''', (user_id, today))
        
        active_goals = cursor.fetchall()
        
        cursor.execute('''
        SELECT * FROM goals 
        WHERE user_id = %s AND is_completed = TRUE
        ORDER BY completed_at DESC
        LIMIT 10
        ''', (user_id,))
        
        completed_goals = cursor.fetchall()
        
        return {
            "active": [dict(row) for row in active_goals],
            "completed": [dict(row) for row in completed_goals]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Аналитика
@app.get("/analytics/{user_id}")
def get_analytics(user_id: int, start_date: str, end_date: str):
    """Получение аналитики за период"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем данные за период
        cursor.execute('''
        SELECT 
            date,
            steps,
            water_ml,
            sleep_hours,
            mood,
            overall_balance,
            activity_score,
            recovery_score,
            nutrition_score,
            mental_score
        FROM daily_data 
        WHERE user_id = %s AND date BETWEEN %s AND %s
        ORDER BY date
        ''', (user_id, start_date, end_date))
        
        daily_data = cursor.fetchall()
        
        # Статистика
        cursor.execute('''
        SELECT 
            COALESCE(AVG(steps), 0) as avg_steps,
            COALESCE(AVG(water_ml), 0) as avg_water,
            COALESCE(AVG(sleep_hours), 0) as avg_sleep,
            COALESCE(AVG(overall_balance), 0) as avg_balance,
            COUNT(*) as days_tracked
        FROM daily_data 
        WHERE user_id = %s AND date BETWEEN %s AND %s
        ''', (user_id, start_date, end_date))
        
        stats = cursor.fetchone()
        
        # Привычки за период
        cursor.execute('''
        SELECT 
            h.id,
            h.custom_name,
            COALESCE(ht.name, h.custom_name) as name,
            COUNT(c.id) as completed_days,
            COALESCE(AVG(c.completed_value), 0) as avg_value,
            h.target_value
        FROM user_habits h
        LEFT JOIN habit_templates ht ON h.template_id = ht.id
        LEFT JOIN habit_completions c ON h.id = c.habit_id AND c.date BETWEEN %s AND %s AND c.is_completed = TRUE
        WHERE h.user_id = %s AND h.is_active = TRUE
        GROUP BY h.id, ht.name
        ''', (start_date, end_date, user_id))
        
        habits_stats = cursor.fetchall()
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": len(daily_data)
            },
            "daily_data": [dict(row) for row in daily_data],
            "statistics": dict(stats) if stats else {},
            "habits": [dict(row) for row in habits_stats]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Шаблоны привычек
@app.get("/templates")
def get_habit_templates(category: Optional[str] = None):
    """Получение шаблонов привычек"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if category:
            cursor.execute('''
            SELECT * FROM habit_templates 
            WHERE is_public = TRUE AND category = %s
            ORDER BY category, name
            ''', (category,))
        else:
            cursor.execute('''
            SELECT * FROM habit_templates 
            WHERE is_public = TRUE
            ORDER BY category, name
            ''')
        
        templates = cursor.fetchall()
        
        return [dict(row) for row in templates]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Дашборд
@app.get("/dashboard/{user_id}")
def get_dashboard(user_id: int):
    """Получение данных для главного экрана"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Проверяем существование пользователя
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        today = date.today().isoformat()
        
        # Получаем данные за сегодня
        cursor.execute(
            "SELECT * FROM daily_data WHERE user_id = %s AND date = %s",
            (user_id, today)
        )
        
        daily_data = cursor.fetchone()
        
        # Если нет данных за сегодня, создаем
        if not daily_data:
            cursor.execute(
                "INSERT INTO daily_data (user_id, date) VALUES (%s, %s) RETURNING *",
                (user_id, today)
            )
            daily_data = cursor.fetchone()
            conn.commit()
        
        # Привычки на сегодня
        cursor.execute('''
        SELECT 
            h.*,
            ht.name as template_name,
            ht.icon as template_icon,
            c.is_completed,
            c.completed_value
        FROM user_habits h
        LEFT JOIN habit_templates ht ON h.template_id = ht.id
        LEFT JOIN habit_completions c ON h.id = c.habit_id AND c.date = %s
        WHERE h.user_id = %s AND h.is_active = TRUE
        ''', (today, user_id))
        
        habits = cursor.fetchall()
        
        # Активные цели
        cursor.execute('''
        SELECT * FROM goals 
        WHERE user_id = %s AND is_completed = FALSE AND end_date >= %s
        ORDER BY end_date ASC
        ''', (user_id, today))
        
        goals = cursor.fetchall()
        
        # Достижения
        cursor.execute('''
        SELECT a.*, ua.unlocked_at 
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = %s AND ua.is_unlocked = TRUE
        ORDER BY ua.unlocked_at DESC LIMIT 5
        ''', (user_id,))
        
        achievements = cursor.fetchall()
        
        # Рассчитываем прогресс
        completed_habits = sum(1 for h in habits if h['is_completed'])
        total_habits = len(habits)
        daily_progress = (completed_habits / total_habits * 100) if total_habits > 0 else 0
        
        return {
            "user": dict(user),
            "daily_data": dict(daily_data) if daily_data else {},
            "today_habits": [dict(row) for row in habits],
            "active_goals": [dict(row) for row in goals],
            "achievements": [dict(row) for row in achievements],
            "stats": {
                "daily_progress": round(daily_progress, 1),
                "completed_habits": completed_habits,
                "total_habits": total_habits,
                "active_goals_count": len(goals),
                "achievements_count": len(achievements)
            },
            "today": today
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Вспомогательные функции для бизнес-логики
def update_energy_level(user_id: int, date_str: str, cursor):
    """Пересчет уровня энергии пользователя"""
    cursor.execute('''
    SELECT 
        COALESCE(steps, 0) as steps,
        COALESCE(water_ml, 0) as water,
        COALESCE(sleep_hours, 0) as sleep,
        COALESCE(breakfast, FALSE) as breakfast,
        COALESCE(lunch, FALSE) as lunch,
        COALESCE(dinner, FALSE) as dinner,
        COALESCE(mood, 'neutral') as mood
    FROM daily_data 
    WHERE user_id = %s AND date = %s
    ''', (user_id, date_str))
    
    data = cursor.fetchone()
    
    if not data:
        return
    
    # Формула расчета энергии
    steps_score = min(data['steps'] / 10000 * 25, 25) if data['steps'] > 0 else 0
    water_score = min(data['water'] / 2000 * 25, 25) if data['water'] > 0 else 0
    sleep_score = min(data['sleep'] / 8 * 25, 25) if data['sleep'] > 0 else 0
    
    meals_count = sum([data['breakfast'], data['lunch'], data['dinner']])
    meals_score = (meals_count / 3) * 25 if meals_count > 0 else 0
    
    mood_scores = {
        'excellent': 25,
        'good': 20,
        'neutral': 15,
        'bad': 5,
        'terrible': 0
    }
    mood_score = mood_scores.get(data['mood'], 15)
    
    overall_balance = steps_score + water_score + sleep_score + meals_score + mood_score
    
    # Обновляем баллы
    cursor.execute('''
    UPDATE daily_data 
    SET 
        activity_score = %s,
        nutrition_score = %s,
        recovery_score = %s,
        mental_score = %s,
        overall_balance = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = %s AND date = %s
    ''', (steps_score, meals_score, sleep_score, mood_score, overall_balance, user_id, date_str))
    
    # Обновляем общий уровень энергии
    cursor.execute('''
    SELECT AVG(overall_balance) as avg_energy
    FROM daily_data 
    WHERE user_id = %s AND date >= %s::date - INTERVAL '7 days'
    ''', (user_id, date_str))
    
    result = cursor.fetchone()
    new_energy = result['avg_energy'] if result and result['avg_energy'] else 50.0
    
    cursor.execute('''
    UPDATE users 
    SET energy_level = %s
    WHERE id = %s
    ''', (float(new_energy), user_id))

def update_habit_streak(habit_id: int, date_str: str, cursor):
    """Обновление серии выполнения привычки"""
    current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    cursor.execute('''
    SELECT date FROM habit_completions 
    WHERE habit_id = %s AND is_completed = TRUE
    ORDER BY date DESC
    LIMIT 7
    ''', (habit_id,))
    
    completions = [row['date'] for row in cursor.fetchall()]
    
    current_streak = 0
    
    for i, comp_date in enumerate(completions):
        expected_date = current_date - timedelta(days=i)
        if comp_date == expected_date:
            current_streak += 1
        else:
            break
    
    cursor.execute('''
    UPDATE user_habits 
    SET 
        current_streak = %s,
        longest_streak = GREATEST(longest_streak, %s)
    WHERE id = %s
    ''', (current_streak, current_streak, habit_id))

def award_for_habit_completion(user_id: int, habit_id: int, cursor):
    """Награждение за выполнение привычки"""
    cursor.execute('''
    UPDATE users 
    SET sync_coins = sync_coins + 2
    WHERE id = %s
    ''', (user_id,))
    
    cursor.execute('''
    UPDATE users 
    SET energy_level = LEAST(energy_level + 3, 100)
    WHERE id = %s
    ''', (user_id,))

# Запуск приложения
if __name__ == "__main__":

    print("/---------------------------------------------------------------------------/")
    print("HealthSync API Server (PostgreSQL)")
    print("/---------------------------------------------------------------------------/")
    print(f"Database: {os.getenv('DB_NAME', 'healthsync')}")
    print(f"Host: {os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}")
    print(f"User: {os.getenv('DB_USER', 'postgres')}")
    print("/---------------------------------------------------------------------------/")
    print("API Documentation: http://localhost:8080/docs")
    print("/---------------------------------------------------------------------------/")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)