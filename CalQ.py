import sys
import re
import winreg
import threading
import time
import math
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QTextEdit, 
                             QLabel, QDialog, QHBoxLayout, QSpinBox, QScrollArea, QComboBox, QBoxLayout, QMainWindow)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QKeySequence
from sympy import symbols, Eq, solve, sympify
from sympy.parsing.sympy_parser import parse_expr
from scipy import constants


class ThemeWatcher(QObject):
    theme_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.last_theme = self.is_light_mode_enabled()

    def watch_theme(self):
        while True:
            current_theme = self.is_light_mode_enabled()
            if current_theme != self.last_theme:
                self.last_theme = current_theme
                self.theme_changed.emit(current_theme)
            time.sleep(1)  # Check every second

    def is_light_mode_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 1
        except FileNotFoundError:
            return False


class PhysicsFormulaSolver(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('PhysicsFormulaSolver', 'App')
        self.theme_watcher = ThemeWatcher()
        self.theme_watcher.theme_changed.connect(self.on_system_theme_change)
        self.watcher_thread = threading.Thread(target=self.theme_watcher.watch_theme, daemon=True)
        self.watcher_thread.start()
        self.variable_memory = {}  # Dictionary to store variables like V1, V2, etc.

        # Initialize theme based on settings or system theme
        self.initialize_theme()
        self.initUI()
    def initialize_theme(self):
        theme = self.settings.value('theme', 'System')
        if theme == 'System':
            self.dark_mode = not self.theme_watcher.is_light_mode_enabled()
        else:
            self.dark_mode = (theme == 'Dark')
        self.settings.setValue('dark_mode', self.dark_mode)

    def initUI(self):
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.setWindowTitle('CalQ')

        self.apply_theme()
        self.setMinimumSize(900, 700)  # Sets minimum size to 200x200
        self.last_windowed_size = self.size()  # Store the last windowed size
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add some padding to the main layout


        # Top bar with legend and settings buttons
        top_bar = QHBoxLayout()
        top_bar.addStretch()

        legend_button = QPushButton('Ω')
        legend_button.setFont(QFont('Arial', 16))
        legend_button.setFixedSize(40, 40)
        legend_button.clicked.connect(self.show_legend)
        top_bar.addWidget(legend_button)

        settings_button = QPushButton('Θ')
        settings_button.setFont(QFont('CMU Serif', 20))
        settings_button.setFixedSize(40, 40)
        settings_button.clicked.connect(self.show_settings)
        top_bar.addWidget(settings_button)

        layout.addLayout(top_bar)

        layout.addStretch()

        self.formula_input = QLineEdit()
        self.formula_input.setFont(QFont('Cascadia Mono', 16))
        self.formula_input.setPlaceholderText('_')
        self.formula_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formula_input.returnPressed.connect(self.solve_formula)
        layout.addWidget(self.formula_input)

        self.clear_memory_action = QAction(self)
        self.clear_memory_action.setShortcut('Ctrl+Q')
        self.clear_memory_action.triggered.connect(self.clear_variable_memory)
        self.addAction(self.clear_memory_action)


        self.results_area = QTextEdit()
        self.results_area.setFont(QFont('Cascadia Mono', 14))
        self.results_area.setReadOnly(True)
        self.results_area.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Changed to left alignment
        self.results_area.setStyleSheet("padding-left: 20px;")  # Add left padding
        layout.addWidget(self.results_area)


        layout.addStretch()

        self.setLayout(layout)

        self.constant_list = {name: (name, getattr(constants, name)) for name in dir(constants) if isinstance(getattr(constants, name), float)}

        self.constant_list['euler'] = ('euler', float(math.e))

        self.fullscreen_action = QAction(self)
        self.fullscreen_action.setShortcut('F11')
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fullscreen_action)

        self.close_action = QAction(self)
        self.close_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))  # Bind Escape key
        self.close_action.triggered.connect(self.close)
        self.addAction(self.close_action)


        self.settings_action = QAction(self)
        self.settings_action.setShortcut('Ctrl+I')
        self.settings_action.triggered.connect(self.show_settings)
        self.addAction(self.settings_action)

        self.memory_label = QLabel("Memory:")
        self.memory_label.setStyleSheet("color: #4D4D4D; padding-left: 20px;")  # Add left padding
        self.memory_label.setFont(QFont('Cascadia Mono', 14))
        self.memory_display = QTextEdit()
        self.memory_display.setFont(QFont('Cascadia Mono', 14))
        self.memory_display.setReadOnly(True)
        self.memory_display.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.memory_display.setStyleSheet("padding-left: 20px;")  # Add left padding


        layout.addWidget(self.memory_label)
        layout.addWidget(self.memory_display)

        self.save_to_memory_action = QAction(self)
        self.save_to_memory_action.setShortcut('Ctrl+S')
        self.save_to_memory_action.triggered.connect(self.save_to_memory)
        self.addAction(self.save_to_memory_action)


        self.legend_action = QAction(self)
        self.legend_action.setShortcut('Ctrl+O')
        self.legend_action.triggered.connect(self.show_legend)
        self.addAction(self.legend_action)

        self.formula_input.setFocus()

    def save_to_memory(self):
        """Saves the current result to the variable memory."""
        current_solution = self.results_area.toPlainText().strip()

        if current_solution:
            try:
                var_index = len(self.variable_memory) + 1
                var_name = f"V{var_index}"
                
                value = current_solution.split('=')[1].strip()
                
                float(value)
                
                self.variable_memory[var_name] = value
                
                print(f"Saved to memory: {var_name} = {value}")
                
                self.update_memory_display()
                
            except ValueError:
                self.results_area.setText("Error: Unable to save. Make sure the result is a number.")
            except IndexError:
                self.results_area.setText("Error: Invalid solution format. Unable to save.")
        else:
            self.results_area.setText("No solution to save!")

    def clear_variable_memory(self):
        """Clears all variables saved in the variable memory."""
        self.variable_memory.clear()
        self.update_memory_display()
        self.results_area.setText("Variable memory cleared.")
        print("Variable memory cleared.")

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QWidget { background-color: #2b2b2b; color: white; }
                QLineEdit, QTextEdit { background-color: #2b2b2b; border: none; }
                QPushButton {
                    background-color: #3b3b3b; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QSpinBox { background-color: #3b3b3b; color: white; }
                QCheckBox { color: white; }
                QScrollBar:vertical {
                    border: none;
                    background: #2b2b2b;
                    width: 10px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:vertical {
                    background: #5a5a5a;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #6a6a6a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)
            
        else:
            self.setStyleSheet("""
                QWidget { background-color: white; color: black; }
                QLineEdit, QTextEdit { background-color: white; border: none; color: #4D4D4D; }
                QPushButton {
                    background-color: #e0e0e0; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QSpinBox { background-color: #f0f0f0; color: black; }
                QCheckBox { color: black; }
                QScrollBar:vertical {
                    border: none;
                    background: white;
                    width: 10px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:vertical {
                    background: #c0c0c0;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #a0a0a0;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }        
                   """)
            
    def update_memory_display(self):
        memory_text = "\n".join([f"{var}: {val}" for var, val in self.variable_memory.items()])
        self.memory_display.setText(memory_text)

    def solve_formula(self):
        formula = self.formula_input.text()
        try:
            print(f"Original formula: {formula}")
            print(f"Variable memory: {self.variable_memory}")

            for var, value in self.variable_memory.items():
                formula = re.sub(r'\\' + var + r'\b', value, formula)

            print(f"Formula after variable substitution: {formula}")

            for symbol, (name, value) in self.constant_list.items():
                formula = re.sub(r'\\' + name + r'\b', str(value), formula)

            formula = formula.replace('^', '**')

            # Debug print
            print(f"Final formula for solving: {formula}")

            if '=' not in formula:
                formula = " a = " + formula
                print(f"Modified formula: {formula}")

            left_side, right_side = formula.split('=')
            eq = Eq(parse_expr(left_side), parse_expr(right_side))

            local_dict = {k: v[1] for k, v in self.constant_list.items()}

            syms = list(eq.free_symbols)

            results = []
            for sym in syms:
                solution = solve(eq, sym, dict=True)
                evaluated_solution = [sol[sym].evalf(subs=local_dict) for sol in solution]
                decimal_places = self.settings.value('decimal_places', 6, type=int)
                formatted_solution = [f"{float(sol):.{decimal_places}f}" for sol in evaluated_solution]
                results.append(f"{sym} = {', '.join(formatted_solution)}")

            self.results_area.setText('\n'.join(results))
        except ValueError as ve:
            self.results_area.setText(f"Error: {str(ve)}")
        except Exception as e:
            self.results_area.setText(f"Error: {str(e)}")

    def show_legend(self):
        legend_dialog = QDialog(self)
        legend_dialog.setWindowTitle("Physics and Engineering Constants")
        legend_dialog.setFont(QFont('Cascadia Mono', 12))

        layout = QVBoxLayout()

        search_bar = QLineEdit()
        search_bar.setFont(QFont('Cascadia Mono', 12))
        search_bar.setPlaceholderText('')
        layout.addWidget(search_bar)
        
        search_bar.setFocus()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)

        self.populate_constants()

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

 
        legend_dialog.setLayout(layout)
        legend_dialog.setFixedSize(800, 600)

        search_bar.textChanged.connect(self.filter_constants)

        legend_dialog.exec()

    def populate_constants(self):
        for symbol, (name, value) in self.constant_list.items():
            label = QLabel(f'{name} ({symbol}): {value:.6e}')
            label.setFont(QFont('Cascadia Mono', 10))
            self.scroll_layout.addWidget(label)

    def filter_constants(self, query):
        query = query.lower()
        for i in reversed(range(self.scroll_layout.count())):
            self.scroll_layout.itemAt(i).widget().deleteLater()

        for symbol, (name, value) in self.constant_list.items():
            if query in name.lower() or query in f"{value:.6e}":
                label = QLabel(f'{name} ({symbol}): {value:.6e}')
                label.setFont(QFont('Cascadia Mono', 10))
                self.scroll_layout.addWidget(label)

    def show_settings(self):
        settings_dialog = QDialog(self)
        settings_dialog.setWindowTitle("Settings")
        settings_dialog.setFont(QFont('Cascadia Mono', 12))

        layout = QVBoxLayout()
        layout.setContentsMargins(60, 60, 60, 60) 

        decimal_layout = QHBoxLayout()
        decimal_label = QLabel("Decimals:")
        decimal_label.setFont(QFont('Cascadia Mono', 12))
        decimal_layout.addWidget(decimal_label)

        self.decimal_spinbox = QSpinBox()
        self.decimal_spinbox.setRange(0, 10)
        self.decimal_spinbox.setValue(self.settings.value('decimal_places', 6, type=int))
        self.decimal_spinbox.setFont(QFont('Cascadia Mono', 12))
        self.decimal_spinbox.setMinimumSize(50, 30)
        decimal_layout.addWidget(self.decimal_spinbox)

        layout.addLayout(decimal_layout)

        dark_mode_layout = QHBoxLayout()
        dark_mode_label = QLabel("Theme:")
        dark_mode_label.setFont(QFont('Cascadia Mono', 12))
        dark_mode_layout.addWidget(dark_mode_label)

        self.dark_mode_combobox = QComboBox()
        self.dark_mode_combobox.addItems(["Light", "Dark", "System"])
        current_theme = self.settings.value('theme', 'System')
        self.dark_mode_combobox.setCurrentText(current_theme)
        self.dark_mode_combobox.setFont(QFont('Cascadia Mono', 12))
        self.dark_mode_combobox.setFixedHeight(40)
        self.dark_mode_combobox.setFixedWidth(150)
        self.dark_mode_combobox.currentIndexChanged.connect(self.toggle_dark_mode)
        dark_mode_layout.addWidget(self.dark_mode_combobox)

        layout.addLayout(dark_mode_layout)

        settings_dialog.setLayout(layout)
        settings_dialog.setFixedSize(800, 600)

        self.decimal_spinbox.valueChanged.connect(self.save_settings)

        settings_dialog.exec()

    def save_settings(self):
        self.settings.setValue('decimal_places', self.decimal_spinbox.value())
        self.settings.sync()

    def toggle_dark_mode(self, index):
        theme = self.dark_mode_combobox.currentText()
        self.settings.setValue('theme', theme)

        if theme == "System":
            self.dark_mode = not self.theme_watcher.is_light_mode_enabled()
        else:
            self.dark_mode = (theme == "Dark")

        self.settings.setValue('dark_mode', self.dark_mode)
        self.settings.sync()
        self.apply_theme()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def on_system_theme_change(self, is_light):
        if self.settings.value('theme', 'System') == 'System':
            self.dark_mode = not is_light
            self.apply_theme()

    def is_light_mode_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 1
        except FileNotFoundError:
            return False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PhysicsFormulaSolver()
    ex.show()
    sys.exit(app.exec())

