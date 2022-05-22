# Домашнее задание к лекции «Flask»

1) запускаем docker для ДБ сервера:
```bash
    docker-compose up -d --build
```
2) устанавливаем нужные библиотеки:
```bash
    pip install -r requirements.txt
``` 
3) запускаем само приложение через gunicorn:
```bash
    PYTHONUNBUFFERED=TRUE gunicorn -b 0.0.0.0:5000 application:application --capture-output
``` 

## Запросы:
 примеры запросов для работы с api в файле requests-examples.http