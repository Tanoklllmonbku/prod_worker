import os
import json
import re
from pathlib import Path
import keyring
from gigachat import GigaChat
import requests

files_url = "https://gigachat.devices.sberbank.ru/api/v1/files"

def get_access_token() -> str:
    """Retrieve GigaChat access token from keyring"""
    access_token = keyring.get_password('myapp', 'gigachat_token')
    if not access_token:
        raise ValueError("GigaChat token not found in keyring. Set it first with: keyring.set_password('myapp', 'gigachat_token', 'your_token')")
    return access_token

def get_headers() -> dict:
    """Generate authorization headers with actual token"""
    access_token = get_access_token()
    return {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }

def get_giga_obj() -> GigaChat:
    """Initialize GigaChat client with credentials"""
    access_token = get_access_token()
    return GigaChat(
        credentials=access_token,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
        model="GigaChat-Max",
    )

def upload_file(giga: GigaChat, file_name: str) -> str:
    """Upload a file and return its ID"""
    with open(file_name, "rb") as f:
        file_obj = giga.upload_file(f)
    return file_obj.id_

def chat_with_file(giga: GigaChat, prompt: str, file_id: str) -> str:
    """Send a prompt with an attached file to GigaChat"""
    result = giga.chat(
        {
            "function_call": "auto",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [file_id]  # Should be a list
                }
            ],
            "temperature": 0.1
        }
    )
    return result.choices[0].message.content

def extract_json_from_text(text):
    """Извлечь JSON из текста"""
    try:
        # Пробуем распарсить весь текст как JSON
        return json.loads(text)
    except json.JSONDecodeError:
        # Ищем JSON блок в тексте
        matches = re.findall(r'(\{.*\})', text, re.DOTALL)
        if matches:
            # Берем самый длинный найденный блок
            longest_match = max(matches, key=len)
            try:
                return json.loads(longest_match)
            except json.JSONDecodeError:
                pass

        # Пробуем найти JSON в квадратных скобках
        matches = re.findall(r'(\[.*\])', text, re.DOTALL)
        if matches:
            longest_match = max(matches, key=len)
            try:
                return json.loads(longest_match)
            except json.JSONDecodeError:
                pass

        return None

def find_mp3_files(directory):
    """Найти все MP3 файлы в директории и её поддиректориях"""
    mp3_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))
    return mp3_files

def process_audio_files():
    """Обработка аудиофайлов"""
    # Инициализация GigaChat
    giga = get_giga_obj()

    # Папка с аудиофайлами
    file_path = "/home/progger/proj/prod_worker/test/1/2"

    # Найти все MP3 файлы
    mp3_files = find_mp3_files(file_path)
    
    print(f"Найдено {len(mp3_files)} аудиофайлов")
    
    # Создаем пустой JSON для результатов
    results = []
    
    # Промпт для анализа аудио
    prompt2 = """ЗАДАЧА - оценка профессиональных навыков и умений, приведших к успешной продаже автомобиля.
Контекст: разговор продажника с клиентом, который привёл к успешной продаже автомобиля.
На основе предоставленной аудиозаписи, выяви действующие стороны диалога (Продавец-покупатель).
Определи, какие профессиональные навыки и умения привели к успешной продаже автомобиля продавцом на основе анализа психосоматики покупателя.
Выведи 10 навыков и умений в формате json, каждый критерий - отдельная категория с своими подкритериями, Weihgt (Вес, влияние на результат) в процентах.
Ответ: только итоговый json.
"""
    
    # Обрабатываем каждый файл
    for i, file_path in enumerate(mp3_files):
        print(f"Обработка файла {i+1}/{len(mp3_files)}: {os.path.basename(file_path)}")
        try:
            # Загружаем файл
            with open(file_path, "rb") as f:
                file_id = giga.upload_file(f).id_
            print("sent")
            # Отправляем запрос
            response_text = giga.chat(
    {
        "function_call": "auto",
        "messages": [
            {
                "role": "user",
                "content": prompt2,
                "attachments": [file_id]
            }
        ],
        "temperature": 0.1
    },
)
            
            # Извлекаем JSON из ответа
            json_data = extract_json_from_text(response_text)
            
            if json_data:
                # Добавляем результат в список
                result = {
                    "file": os.path.basename(file_path),
                    "skills": json_data
                }
                results.append(result)
                
                # Удаляем файл после обработки
                giga.delete_file(file_id)
                
                print(f"  ✓ Успешно обработан")
            else:
                print(f"  ✗ Не удалось извлечь JSON")
                
        except Exception as e:
            print(f"  ✗ Ошибка при обработке {file_path}: {str(e)}")
    
    # Сохраняем промежуточные результаты
    json_file_path = "/home/progger/proj/prod_worker/test/results.json"
    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Результаты сохранены в {json_file_path}")
    giga.close()
    return results

def analyze_results():
    """Анализ результатов с помощью промпта 3"""
    # Загружаем результаты
    json_file_path = "/home/progger/proj/prod_worker/test/results.json"
    with open(json_file_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    if not results:
        print("Нет данных для анализа")
        return
    
    # Инициализация GigaChat
    giga = get_giga_obj()
    
    # Загружаем JSON файл
    file_id = upload_file(giga, json_file_path)
    
    prompt3 = """ЗАДАЧА - оценка профессиональных навыков и умений, приведших к успешной продаже автомобиля.
Контекст: навыки и их веса, полученные при анализе успешных разговоров наиболее результативных продажников с клиентами, которые привели к продаже автомобиля.
На основе предоставленного файла в формате JSON, выяви наиболее значимые критерии оценки лучших работников, которые привели к успеху.
Выведи навыки, которые встречаются в большинстве случаев - более 50 процентов записей, а так же сформулируй для них веса по их значимости и частоте появленияв.
Ответ: только итоговый json.
"""
    
    # Отправляем запрос
    response_text = giga.chat(
    {
        "function_call": "auto",
        "messages": [
            {
                "role": "user",
                "content": prompt3,
                "attachments": [file_id]
            }
        ],
        "temperature": 0.1
    },
)
    
    # Извлекаем JSON из ответа
    analysis_data = extract_json_from_text(response_text)
    
    if analysis_data:
        # Сохраняем финальный анализ
        final_file_path = "/home/progger/proj/prod_worker/test/final_analysis.json"
        with open(final_file_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "analyzed_records": len(results),
                    "date": "2024-01-25"  # можно заменить на datetime.now().isoformat()
                },
                "analysis": analysis_data
            }, f, ensure_ascii=False, indent=2)
        
        print(f"Финальный анализ сохранен в {final_file_path}")
        
        # Удаляем временный файл
        giga.delete_file(file_id)
        
        return analysis_data
    else:
        print("Не удалось получить анализ")
        return None

def main():
    """Основная функция"""
    print("=" * 60)
    print("СИСТЕМА АНАЛИЗА НАВЫКОВ ПРОДАЖ")
    print("=" * 60)
    
    # Обрабатываем аудиофайлы
    results = process_audio_files()
    
    if not results:
        print("Не удалось обработать аудиофайлы")
        return
    
    # Анализируем результаты
    final_analysis = analyze_results()
    
    if final_analysis:
        print("\n" + "="*60)
        print("✓ РАБОТА ЗАВЕРШЕНА УСПЕШНО!")
        print("="*60)
    else:
        print("\n✗ Не удалось завершить анализ")

if __name__ == "__main__":
    main()