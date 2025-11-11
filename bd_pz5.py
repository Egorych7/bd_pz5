# file: simple_calorie_finder.py
import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QTextEdit, QTabWidget, QProgressBar, QMessageBox, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class FoodDatabase:
    def __init__(self):
        self.cache = {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FoodCalorieFinder/2.0"
        })

    def get_product_by_barcode(self, barcode: str) -> dict:
        if barcode in self.cache:
            return self.cache[barcode]

        try:
            url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
            response = self.session.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 1 and data.get('product'):
                    self.cache[barcode] = data
                    return data
            return {"status": 0, "product": None}

        except Exception as e:
            raise Exception(f"Ошибка: {str(e)}")

    def search_products(self, query: str, page_size=20) -> dict:
        try:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": query,
                "json": 1,
                "page_size": page_size,
            }

            response = self.session.get(url, params=params, timeout=10)
            data = response.json()

            valid_products = []
            for product in data.get('products', []):
                if product.get('product_name') or product.get('brands'):
                    valid_products.append(product)

            return {'products': valid_products}

        except Exception as e:
            raise Exception(f"Ошибка поиска: {str(e)}")

    def extract_nutrition(self, nutriments: dict) -> dict:
        if not nutriments:
            return {}

        nutrition_data = {}

        if nutriments.get('energy-kcal_100g'):
            nutrition_data['kcal_100g'] = nutriments['energy-kcal_100g']
        if nutriments.get('proteins_100g'):
            nutrition_data['protein_100g'] = nutriments['proteins_100g']
        if nutriments.get('fat_100g'):
            nutrition_data['fat_100g'] = nutriments['fat_100g']
        if nutriments.get('carbohydrates_100g'):
            nutrition_data['carbs_100g'] = nutriments['carbohydrates_100g']

        return nutrition_data

    def clean_product_data(self, product):
        if not product:
            return {}

        name = product.get('product_name', '').strip()
        if not name or name == 'null':
            name = 'Неизвестный продукт'

        brand = product.get('brands', '').strip()
        if not brand or brand == 'null':
            brand = '—'

        return {
            'name': name,
            'brand': brand,
            'barcode': product.get('code') or '—',
            'quantity': product.get('quantity') or '—',
            'nutriments': product.get('nutriments', {})
        }


class SearchThread(QThread):
    search_complete = pyqtSignal(dict)
    search_error = pyqtSignal(str)

    def __init__(self, db, query):
        super().__init__()
        self.db = db
        self.query = query

    def run(self):
        try:
            query = self.query.strip()
            if not query:
                self.search_error.emit("Введите запрос")
                return

            if query.isdigit() and len(query) >= 8:
                result = self.db.get_product_by_barcode(query)
                if result.get("status") == 1 and result.get("product"):
                    products = [result["product"]]
                else:
                    products = []
            else:
                result = self.db.search_products(query, 25)
                products = result.get('products', [])

            cleaned_products = []
            for product in products:
                cleaned = self.db.clean_product_data(product)
                if cleaned['name'] != 'Неизвестный продукт':
                    cleaned_products.append(cleaned)

            self.search_complete.emit({'products': cleaned_products})

        except Exception as e:
            self.search_error.emit(str(e))


class SimpleCalorieFinder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = FoodDatabase()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Поиск калорийности продуктов")
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Поиск
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название продукта или штрихкод")
        self.search_input.returnPressed.connect(self.search_products)

        self.search_btn = QPushButton("Найти")
        self.search_btn.clicked.connect(self.search_products)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)

        layout.addLayout(search_layout)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Табы
        self.tabs = QTabWidget()

        # Результаты
        self.results_tab = QWidget()
        self.setup_results_tab()
        self.tabs.addTab(self.results_tab, "Результаты")

        # Детали
        self.details_tab = QWidget()
        self.setup_details_tab()
        self.tabs.addTab(self.details_tab, "Детали")

        layout.addWidget(self.tabs)

        # Статус
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готов")

        self.search_input.setFocus()

    def setup_results_tab(self):
        layout = QVBoxLayout(self.results_tab)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Название", "Бренд", "Штрихкод", "Ккал", "Белки", "Жиры", "Углеводы"
        ])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for i in range(3, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.results_table.doubleClicked.connect(self.on_product_selected)
        layout.addWidget(self.results_table)

    def setup_details_tab(self):
        layout = QVBoxLayout(self.details_tab)

        # Информация
        info_label = QLabel("Информация о продукте:")
        layout.addWidget(info_label)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        layout.addWidget(self.info_text)

        # Пищевая ценность
        nutrition_label = QLabel("Пищевая ценность:")
        layout.addWidget(nutrition_label)

        self.nutrition_text = QTextEdit()
        self.nutrition_text.setReadOnly(True)
        layout.addWidget(self.nutrition_text)

    def search_products(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Ошибка", "Введите запрос")
            return

        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Поиск...")

        self.search_thread = SearchThread(self.db, query)
        self.search_thread.search_complete.connect(self.on_search_complete)
        self.search_thread.search_error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_complete(self, result):
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)

        products = result.get('products', [])
        self.results_table.setRowCount(0)

        if not products:
            self.status_bar.showMessage("Не найдено")
            QMessageBox.information(self, "Результат", "Ничего не найдено")
            return

        self.results_table.setRowCount(len(products))

        for row, product in enumerate(products):
            nutrition = self.db.extract_nutrition(product.get('nutriments', {}))

            kcal = nutrition.get('kcal_100g', '—')
            protein = nutrition.get('protein_100g', '—')
            fat = nutrition.get('fat_100g', '—')
            carbs = nutrition.get('carbs_100g', '—')

            if isinstance(kcal, (int, float)):
                kcal = f"{kcal:.0f}"
            if isinstance(protein, (int, float)):
                protein = f"{protein:.1f}"
            if isinstance(fat, (int, float)):
                fat = f"{fat:.1f}"
            if isinstance(carbs, (int, float)):
                carbs = f"{carbs:.1f}"

            items = [
                product['name'],
                product['brand'],
                product['barcode'],
                kcal,
                protein,
                fat,
                carbs
            ]

            for col, value in enumerate(items):
                self.results_table.setItem(row, col, QTableWidgetItem(str(value)))

        self.status_bar.showMessage(f"Найдено: {len(products)}")
        self.tabs.setCurrentIndex(0)

    def on_search_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)
        self.status_bar.showMessage("Ошибка")
        QMessageBox.critical(self, "Ошибка", error_msg)

    def on_product_selected(self, index):
        row = index.row()
        barcode_item = self.results_table.item(row, 2)

        if barcode_item and barcode_item.text() != '—':
            barcode = barcode_item.text()
            self.load_product_details(barcode)

    def load_product_details(self, barcode):
        try:
            result = self.db.get_product_by_barcode(barcode)
            self.show_product_details(result)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {str(e)}")

    def show_product_details(self, result):
        if not result or result.get('status') != 1 or not result.get('product'):
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить информацию")
            return

        product = result['product']
        cleaned = self.db.clean_product_data(product)
        nutrition = self.db.extract_nutrition(product.get('nutriments', {}))

        # Основная информация
        info_text = f"""Название: {cleaned['name']}
Бренд: {cleaned['brand']}
Штрихкод: {cleaned['barcode']}
Упаковка: {cleaned['quantity']}"""

        # Пищевая ценность
        nutrition_text = "Пищевая ценность на 100г:\n\n"

        if nutrition:
            if nutrition.get('kcal_100g'):
                nutrition_text += f"Энергия: {nutrition['kcal_100g']} ккал\n"
            if nutrition.get('protein_100g'):
                nutrition_text += f"Белки: {nutrition['protein_100g']} г\n"
            if nutrition.get('fat_100g'):
                nutrition_text += f"Жиры: {nutrition['fat_100g']} г\n"
            if nutrition.get('carbs_100g'):
                nutrition_text += f"Углеводы: {nutrition['carbs_100g']} г\n"
        else:
            nutrition_text += "Информация отсутствует"

        self.info_text.setText(info_text)
        self.nutrition_text.setText(nutrition_text)
        self.tabs.setCurrentIndex(1)
        self.status_bar.showMessage("Информация загружена")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleCalorieFinder()
    window.show()
    sys.exit(app.exec_())