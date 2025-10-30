import math
import sys
import threading
import random
import simpy
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QPushButton, QGroupBox, QDoubleSpinBox, QProgressBar
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt


class Cashier:
    def __init__(self, id):
        self.id = id
        self.busy = False
        self.served_count = 0
        # Фиксированное время для каждой кассы
        service_times = [3, 4, 5, 6]  # касса0=3мин, касса1=4мин, касса2=5мин, касса3=6мин
        self.service_time = service_times[id]

    def __repr__(self):
        return f"Касса{self.id + 1}({self.service_time}мин):{self.served_count}клиентов"


class EnhancedQueueSimulation(threading.Thread):
    def __init__(self, arrival_rate, num_runs=1):
        super().__init__()
        self.params = {
            'arrival_rate': arrival_rate,  # скорость прибытия
            'sim_time': 720,
            'num_runs': num_runs  # количество прогонов
        }
        self.stop_event = threading.Event()
        self.run_results = []
        self.current_run = 0
        self.progress = 0

        self.random_generator = random.Random()
        self.cashier_stats = []

    def expovariate(self, lambd=1.0):
        if lambd == 0:
            raise ValueError("lambda должен быть не нулевым")
        return -math.log(1.0 - self.random_generator.random()) * 1 / lambd

    def get_arrival_interval(self):
        """Генерация времени между прибытиями клиентов"""
        return self.expovariate(self.params['arrival_rate'])

    def customer(self, env, cashiers, customer_id):
        # Пытаемся найти свободную кассу в порядке от 0 до 3
        free_cashier = None
        for cashier in cashiers:
            if not cashier.busy:
                free_cashier = cashier
                break

        if free_cashier:
            free_cashier.busy = True

            # Используем фиксированное время кассы
            service_time = free_cashier.service_time
            yield env.timeout(service_time)

            free_cashier.busy = False
            free_cashier.served_count += 1
            self.served_customers += 1

            print(f"Клиент {customer_id} обслужен на {free_cashier}")
        else:
            self.abandoned += 1

            print(f"Клиент {customer_id} ушел - все кассы заняты")

    def setup(self, env, cashiers):
        customer_id = 0
        while not self.stop_event.is_set() and env.now < self.params['sim_time']:
            yield env.timeout(self.get_arrival_interval())
            customer_id += 1
            env.process(self.customer(env, cashiers, customer_id))

    def run_single_simulation(self):
        env = simpy.Environment()
        # Создаем 4 кассы с фиксированным временем
        cashiers = [Cashier(i) for i in range(4)]
        self.served_customers = 0
        self.abandoned = 0
        env.process(self.setup(env, cashiers))
        env.run(until=self.params['sim_time']) #мэджик

        total_customers = self.served_customers + self.abandoned
        refusal_rate = (self.abandoned / total_customers * 100) if total_customers else 0

        # статистика по кассам
        self.cashier_stats = []
        for cashier in cashiers:
            self.cashier_stats.append({
                'id': cashier.id,
                'served_count': cashier.served_count,
                'service_time': cashier.service_time,
                'utilization': (cashier.served_count * cashier.service_time) / self.params['sim_time'] * 100
            })

        return {
            'served': self.served_customers,
            'abandoned': self.abandoned,
            'total_customers': total_customers,
            'refusal_rate': refusal_rate,
            'cashier_stats': self.cashier_stats  # ДОБАВЛЯЕМ СТАТИСТИКУ КАСС
        }

    def run(self):
        for i in range(self.params['num_runs']):
            if self.stop_event.is_set():
                break
            self.current_run = i + 1
            result = self.run_single_simulation()
            self.run_results.append(result)
            self.progress = (i + 1) / self.params['num_runs'] * 100

    def stop(self):
        self.stop_event.set()

    def get_results(self):
        if not self.run_results:
            return None

        avg_served = np.mean([r['served'] for r in self.run_results])
        avg_abandoned = np.mean([r['abandoned'] for r in self.run_results])
        avg_total = np.mean([r['total_customers'] for r in self.run_results])
        avg_refusal_rate = np.mean([r['refusal_rate'] for r in self.run_results])

        # расчет статистики касс
        cashier_stats_all = []
        if self.run_results and 'cashier_stats' in self.run_results[0]:
            num_cashiers = len(self.run_results[0]['cashier_stats'])
            for i in range(num_cashiers):
                cashier_served = [run['cashier_stats'][i]['served_count'] for run in self.run_results]
                cashier_utilization = [run['cashier_stats'][i]['utilization'] for run in self.run_results]
                cashier_stats_all.append({
                    'id': i,
                    'avg_served': np.mean(cashier_served),
                    'avg_utilization': np.mean(cashier_utilization)
                })

        return {
            'avg_served': avg_served,
            'avg_abandoned': avg_abandoned,
            'avg_total': avg_total,
            'avg_refusal_rate': avg_refusal_rate,
            'num_runs': self.params['num_runs'],
            'current_run': self.current_run,
            'progress': self.progress,
            'all_results': self.run_results,
            'avg_cashier_stats': cashier_stats_all
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("СМО: Модель магазина")
        self.setGeometry(100, 100, 1200, 800)

        # Основное размещение
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Панель управления
        control_panel = self.create_control_panel()
        layout.addLayout(control_panel, stretch=1)

        self.figure = plt.figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)
        self.ax_stats = self.figure.add_subplot(211)  # первый график сверху
        self.ax_cashiers = self.figure.add_subplot(212)  # второй график снизу

        self.ax_stats.set_title("Результаты моделирования")
        self.ax_cashiers.set_title("Загрузка касс")

        layout.addWidget(self.canvas, stretch=3, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Таймер обновления
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_plots)

    def create_control_panel(self):
        panel = QVBoxLayout()

        # Параметр
        params_box = QGroupBox("Параметры")
        params_layout = QVBoxLayout()
        self._add_double_spin(params_layout, "Клиентов в минуту:", 0.001, 20.0, 0.5, 'arrival_rate')
        self._add_spin(params_layout, "Количество прогонов:", 1, 10000, 100, 'num_runs')
        params_box.setLayout(params_layout)
        panel.addWidget(params_box)

        # Кнопки
        self.btn_start = QPushButton("Запустить симуляцию")
        self.btn_stop = QPushButton("Остановить")
        panel.addWidget(self.btn_start)
        panel.addWidget(self.btn_stop)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        panel.addWidget(self.progress_bar)

        # Результаты
        self.results_label = QLabel("Результаты появятся после симуляции")
        panel.addWidget(self.results_label)
        panel.addStretch()

        self.btn_start.clicked.connect(self.start_simulation)
        self.btn_stop.clicked.connect(self.stop_simulation)
        return panel

    def _add_spin(self, layout, label, minv, maxv, val, attr):
        layout.addWidget(QLabel(label))
        spin = QSpinBox()
        spin.setRange(minv, maxv)
        spin.setValue(val)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def _add_double_spin(self, layout, label, minv, maxv, val, attr):
        layout.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setRange(minv, maxv)
        spin.setValue(val)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def start_simulation(self):
        if hasattr(self, 'sim_thread') and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()

        params = {
            'arrival_rate': self.arrival_rate_spin.value(),
            'num_runs': self.num_runs_spin.value()
        }
        self.sim_thread = EnhancedQueueSimulation(**params)
        self.sim_thread.start()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.update_timer.start(500)

    def stop_simulation(self):
        if hasattr(self, 'sim_thread') and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()
        self.update_timer.stop()
        self.progress_bar.setVisible(False)

    def update_plots(self):
        if not self.sim_thread or not self.sim_thread.is_alive():
            results = self.sim_thread.get_results()
            if results:
                self.display_results(results)
                self.update_plot_data(results)
            self.progress_bar.setVisible(False)
            self.update_timer.stop()
            return
        self.progress_bar.setValue(int(self.sim_thread.progress))

    def display_results(self, results):
        text = (
            f"Прогон: {results['current_run']}/{results['num_runs']}\n"
            f"Среднее обслужено: {results['avg_served']:.1f}\n"
            f"Среднее ушло: {results['avg_abandoned']:.1f}\n"
            f"Отказы: {results['avg_refusal_rate']:.1f}%\n"
            f"Всего клиентов: {results['avg_total']:.1f}"
        )

        if 'avg_cashier_stats' in results:
            text += "\n\n--- Статистика касс ---"
            for cashier in results['avg_cashier_stats']:
                text += f"\nКасса {cashier['id'] + 1}: {cashier['avg_served']:.1f} клиентов"

        self.results_label.setText(text)

    def update_plot_data(self, results):

        self.ax_stats.clear()
        self.ax_cashiers.clear()

        self.ax_stats.set_title("Статистика по прогонам")
        self.ax_stats.set_xlabel("Прогоны")
        self.ax_stats.set_ylabel("Количество клиентов")

        runs = list(range(1, len(results['all_results']) + 1))
        served = [r['served'] for r in results['all_results']]
        abandoned = [r['abandoned'] for r in results['all_results']]
        total = [r['total_customers'] for r in results['all_results']]

        self.ax_stats.plot(runs, served, 'g-', label='Обслужено')
        self.ax_stats.plot(runs, abandoned, 'r-', label='Ушли')
        self.ax_stats.plot(runs, total, 'b--', label='Всего клиентов')
        self.ax_stats.legend()
        self.ax_stats.grid(True, linestyle='--', alpha=0.3)

        self.ax_cashiers.set_title("Загрузка касс")
        self.ax_cashiers.set_xlabel("Кассы")
        self.ax_cashiers.set_ylabel("Количество обслуженных клиентов")

        if 'avg_cashier_stats' in results and results['avg_cashier_stats']:
            cashier_ids = [f"Касса {c['id'] + 1}" for c in results['avg_cashier_stats']]
            served_counts = [c['avg_served'] for c in results['avg_cashier_stats']]

            bars = self.ax_cashiers.bar(cashier_ids, served_counts, color=['blue', 'green', 'orange', 'red'])

            for bar, count in zip(bars, served_counts):
                self.ax_cashiers.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                                      f'{count:.1f}', ha='center', va='bottom')

        self.ax_cashiers.grid(True, linestyle='--', alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()