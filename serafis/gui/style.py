PRIMARY = "#1f4e8c"
ACCENT = "#2f7de1"

QSS = """
* { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; font-size: 10.5pt; color: #1d2433; }
QMainWindow, #Content { background: #f4f6fb; }
#Sidebar { background: #0f2747; }
#Sidebar QLabel { color: #e8eef9; }
#Brand { font-size: 20pt; font-weight: 700; color: #ffffff; letter-spacing: 3px; }
#BrandSub { color: #9fb6d8; font-size: 9pt; }
#NavButton { text-align: left; padding: 10px 14px; border: none; border-radius: 8px; color: #d6e2f5; background: transparent; font-size: 10.5pt; }
#NavButton:hover { background: #1b3a66; }
#NavButton:checked { background: #2f7de1; color: white; font-weight: 600; }
#LangButton { color: #d6e2f5; background: #1b3a66; border: none; border-radius: 6px; padding: 6px 10px; }
#LangButton:hover { background: #2a4f86; }
#PageTitle { font-size: 18pt; font-weight: 700; color: #173a6b; }
#PageIntro { color: #4a5470; font-size: 10.5pt; }
#StepLabel { color: #66708a; font-size: 9pt; font-weight: 600; text-transform: uppercase; }
#Card { background: white; border: 1px solid #dfe6f2; border-radius: 12px; }
#CardTitle { font-size: 12pt; font-weight: 600; color: #173a6b; }
#Muted { color: #66708a; font-size: 9pt; }
#BigNumber { font-size: 22pt; font-weight: 700; color: #173a6b; }
#Warning { background: #fff4e0; border: 1px solid #f0c36d; border-radius: 10px; }
#Danger { background: #fdecea; border: 1px solid #f1a39b; border-radius: 10px; }
#Success { background: #e8f6ec; border: 1px solid #93d1a7; border-radius: 10px; }
#Info { background: #e9f1fd; border: 1px solid #a9c8f2; border-radius: 10px; }
#NoDecryptor { font-size: 14pt; font-weight: 700; color: #8a3b00; }
QPushButton { background: white; border: 1px solid #c5d1e6; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { background: #eef3fb; }
QPushButton:disabled { color: #9aa3b5; background: #f2f4f8; border-color: #e1e6ef; }
QPushButton#Primary { background: #2f7de1; color: white; border: none; font-weight: 600; }
QPushButton#Primary:hover { background: #2569c2; }
QPushButton#Primary:disabled { background: #a9c3e8; color: #eef3fb; }
QPushButton#DangerButton { background: #c0392b; color: white; border: none; font-weight: 600; }
QProgressBar { border: 1px solid #c5d1e6; border-radius: 6px; background: white; text-align: center; height: 18px; }
QProgressBar::chunk { background: #2f7de1; border-radius: 6px; }
QTableWidget, QListWidget, QPlainTextEdit, QLineEdit, QComboBox { background: white; border: 1px solid #c5d1e6; border-radius: 6px; }
QHeaderView::section { background: #f2f5fb; border: none; border-bottom: 1px solid #dfe6f2; padding: 6px; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QCheckBox { spacing: 8px; }
#LangCard { background: white; border: 2px solid #dfe6f2; border-radius: 16px; font-size: 16pt; padding: 24px 40px; }
#LangCard:hover { border-color: #2f7de1; background: #f3f8ff; }
"""

LEVEL_COLORS = {"strong": "#17803d", "probable": "#b26a00", "possible": "#66708a"}
STATUS_ICONS = {"pass": "✅", "fail": "❌", "warning": "⚠️", "unavailable": "➖"}
