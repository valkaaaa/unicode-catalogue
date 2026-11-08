# Unicode Catalogue

Графический просмотрщик таблицы Unicode с фильтрами, поиском, экспортом
и проверкой наличия глифов в системных шрифтах. Написан на чистом Python
с использованием Tkinter.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Возможности

- Сетка символов по выбранному диапазону или блоку Unicode.
- Цветовое кодирование категорий (`Cc`, `Cf`, `Mn`, `Zs`, …).
- Невидимые символы (управляющие, форматирующие, комбинирующие)
  показываются бинарным представлением кода.
- Поиск по имени символа и фильтрация по группам категорий
  (буквы / цифры / пунктуация / символы / метки / разделители / прочие).
- Панель «Детали»: код, имя, категория, блок, bidi, combining,
  East Asian Width, UTF-8, UTF-16, Python- и HTML-эскейпы,
  наличие глифа в подходящем шрифте.
- Отрисовка цветных эмодзи через Pillow (если установлен).
- Копирование символа, кода, Python-escape, HTML-entity, имени, UTF-8
  через контекстное меню.
- Экспорт в TXT, CSV, HTML (сетка).
- Светлая и тёмная темы.
- Выбор шрифта для отображения.
- Навигация с клавиатуры.

## Требования

- Python 3.8+
- Tkinter (входит в стандартную поставку Python на Windows и macOS;
  на Linux — `sudo apt install python3-tk`).
- Pillow (опционально, но настоятельно рекомендуется):
  `pip install pillow`.

## Установка и запуск

```bash
git clone https://github.com/USER/unicode-catalogue.git
cd unicode-catalogue
pip install pillow       # опционально
python main.py