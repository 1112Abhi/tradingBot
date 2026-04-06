# 📄 `PROJECT_SETUP.md`

```md
# Trading Bot — Phase 1 Setup

## 🎯 Goal (Phase 1)
Build a minimal working pipeline:
- Fetch dummy data
- Generate a signal
- Send a Telegram alert

---

## 🧱 Project Structure

```

trading_bot/
│
├── main.py
├── config.py
├── data_fetch.py
├── strategy.py
├── telegram_bot.py
│
├── tests/
│   ├── test_data_fetch.py
│   ├── test_strategy.py
│   ├── test_telegram.py
│
├── PROJECT.md
├── TASKS.md
└── requirements.txt

````

---

## ⚙️ Environment Setup

### 1. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
````

### 2. Install dependencies

```bash
pip install requests pytest
```

### 3. Freeze requirements

```bash
pip freeze > requirements.txt
```

---

## 🧠 Design Principles

* Keep modules **small and independent**
* Avoid hardcoding (use config.py)
* Build **incrementally**
* Always ensure **code runs end-to-end**

---

## 🧪 Testing (VERY IMPORTANT)

We will follow **basic test-driven development (TDD-lite)**:

### Rules:

* Every module should have at least **1 test**
* Tests should validate:

  * Output correctness
  * Basic behavior
* Keep tests simple (don’t over-engineer)

---

## 📦 Module Responsibilities

### `data_fetch.py`

* Function: `fetch_price()`
* Returns: dummy price (e.g., 100)

---

### `strategy.py`

* Function: `generate_signal(price)`
* Logic:

  * If price > 90 → "BUY"
  * Else → "NO_TRADE"

---

### `telegram_bot.py`

* Function: `send_message(text)`
* Sends message using Telegram Bot API

---

### `main.py`

* Orchestrates:

  * Fetch data
  * Run strategy
  * Send alert

---

## 🧪 Test Expectations

### `test_data_fetch.py`

* fetch_price returns a number

### `test_strategy.py`

* price > 90 → BUY
* price <= 90 → NO_TRADE

### `test_telegram.py`

* Mock API call (no real message required)

---

## 🔁 Development Workflow

1. Define module responsibility
2. Write minimal implementation
3. Write test
4. Run test
5. Integrate into main.py

---

## 🚀 Current Phase Tasks

* [ ] Setup environment
* [ ] Create folder structure
* [ ] Implement telegram_bot.py
* [ ] Write test for telegram
* [ ] Implement data_fetch.py
* [ ] Write test for data_fetch
* [ ] Implement strategy.py
* [ ] Write test for strategy
* [ ] Connect all in main.py

---

## 🧠 Notes for AI Assistants (Claude / Copilot)

* Keep code minimal and modular
* Avoid over-engineering
* Prefer clarity over optimization
* Ensure testability of each function
* Use simple logic for Phase 1

---

## ⚠️ Constraints

* No Docker
* No database
* No real trading API yet
* No complex strategy

---

## ✅ Success Criteria

* Running `main.py` sends a Telegram message
* All tests pass using:

```bash
pytest
```

---

````

---

# 🧠 Claude Context Prompt (Improved — Step 6)

Use this when you go to Claude:

```text
I am building a Python trading bot.

Here is my setup:

[paste PROJECT_SETUP.md]

Goal:
Implement Phase 1 modules:
- telegram_bot.py
- data_fetch.py
- strategy.py
- main.py

Requirements:
- Keep code minimal and modular
- Include basic tests for each module (pytest)
- Follow structure defined above

Start with telegram_bot.py + test file.
````

---

# 💻 How You Use Copilot (Step 7)

Inside VS Code:

* Open file → start typing:

  ```python
  def send_message(text):
  ```
* Let Copilot complete

For tests:

```python
def test_fetch_price():
```

👉 Copilot is VERY good at test scaffolding

---

# 🔥 Why This Setup is Powerful

You now have:

* ✅ Structured system
* ✅ Built-in testing habit
* ✅ AI-friendly context
* ✅ Scalable foundation

---

# 🚀 Your Next Steps

1. Create `PROJECT_SETUP.md`
2. Setup environment
3. Do **Step 5 (Telegram bot)**
4. Use Claude prompt → generate first module

---

# 📤 When you come back

Send:

```text
Progress:
- Telegram bot created
- Code generated

Issue:
[paste error or confusion]

Next goal:
[what you want to build]
```
