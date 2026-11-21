# BumFinance

Трекер особистих фінансів і спільних витрат. Веди свої доходи й витрати, став ліміти, відкладай на цілі, а з друзями ділися чеками: застосунок сам рахує, хто кому винен, і підказує мінімальну кількість переказів.

**Сайт:** https://bumfinance.onrender.com

Під час завантаження сайту, будь ласка, зачекайте приблизно 1-2 хвилини для повного завантаження. 

## Можливості

- Дашборд з балансом, витратами за категоріями і останніми транзакціями
- Транзакції з фільтрами та категоріями
- Ліміти на місяць із попередженнями
- Цілі накопичення з рекомендацією
- Спільний чек: групи, чат, спільні витрати, баланси і переказ «Сплачено»
- Друзі та запити на дружбу
- Сповіщення про ліміти і досягнення цілей
- Прогноз витрат на місяць
- Експорт у CSV, Excel і PDF
- Відновлення пароля

## Скріншоти

<img width="1535" height="727" alt="image" src="https://github.com/user-attachments/assets/99a449aa-077d-4122-9131-09c18599fd68" />


<img width="1280" height="607" alt="Дашборд" src="https://github.com/user-attachments/assets/cef5442c-733b-49fc-ab4e-7f4eefa95081" />

<img width="1535" height="730" alt="image" src="https://github.com/user-attachments/assets/de090777-3aef-4752-b65c-1f19a6f2b5ac" />

<img width="1535" height="726" alt="image" src="https://github.com/user-attachments/assets/a2a72661-9465-411d-9590-e9adfebc2273" />

<img width="1535" height="726" alt="image" src="https://github.com/user-attachments/assets/88722b1b-35d1-4395-8cd4-711630566aaa" />

<img width="1535" height="726" alt="image" src="https://github.com/user-attachments/assets/e7e11b7c-32d5-4bd4-954d-f2ca8a2d95a1" />

<img width="1535" height="728" alt="image" src="https://github.com/user-attachments/assets/95442ee7-4cfb-4129-bcf3-fa689f2a4bf4" />

## Як зайти

1. Відкрий https://bumfinance.onrender.com
2. Зареєструйся або увійди
3. Почни з «Транзакцій» або створи групу в «Спільному чеку»

Сайт на безкоштовному хостингу, тому перший відкриття може займати до хвилини.

## Запуск локально

```bash
git clone https://github.com/NIKILFNJELO/bumfinance.git
cd bumfinance
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Відкрий http://127.0.0.1:8000

## Технології

Python, Django, SQLite (локально), Tailwind CSS, WhiteNoise, Gunicorn, хостинг Render.
