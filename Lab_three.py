import sys
import threading
import random
import simpy
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QPushButton, QGroupBox, QDoubleSpinBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt

class Customer:
    def __init__(self, service_time):
        self.patience = 8  # Универсальное терпение для всех клиентов
        self.required_service_time = service_time


class EnhancedQueueSimulation(threading.Thread):
    def __init__(self, arrival_rate, service_time, num_cashiers, sim_time):
        super().__init__()
        self.params = {
            'arrival_rate': arrival_rate,
            'service_time': service_time,
            'num_cashiers': num_cashiers,
            'sim_time': sim_time,
            'max_queue': 1,  # Фиксированная максимальная очередь
        }
        self.wait_times = []
        self.queue_lengths = []
        self.system_load = []
        self.serv_times = []
        self.abandoned = 0
        self.hourly_load = []
        self.timestamps = []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.emergency = False
        self.served_customers = 0 #доб

    def get_arrival_interval(self):
        return random.expovariate(self.params['arrival_rate'])

    def customer(self, env, cashiers):
        customer = Customer(self.params['service_time'])
        arrival = env.now
        with cashiers.request() as req:
            results = yield req | env.timeout(customer.patience)
            if req in results:
                wait = env.now - arrival
                with self.lock:
                    self.wait_times.append(wait)
                    self.serv_times.append(customer.required_service_time)
                    self.served_customers += 1
                yield env.timeout(customer.required_service_time)
            else:  # Клиент ушел
                with self.lock:
                    self.abandoned += 1

    def setup(self, env, cashiers):
        while not self.stop_event.is_set() and env.now < self.params['sim_time']:
            interval = self.get_arrival_interval()
            yield env.timeout(interval)
            env.process(self.customer(env, cashiers))
            with self.lock:
                self.queue_lengths.append(len(cashiers.queue))
                self.system_load.append(cashiers.count)
                self.timestamps.append(env.now)
                hour = int(env.now / 60)
                while len(self.hourly_load) <= hour:
                    self.hourly_load.append(0)
                self.hourly_load[hour] = cashiers.count / self.params['num_cashiers']

    def run(self):
        random.seed(42)
        env = simpy.Environment()
        cashiers = simpy.Resource(env, capacity=self.params['num_cashiers'])
        env.process(self.setup(env, cashiers))
        env.run(until=self.params['sim_time'])

    def stop(self):
        self.stop_event.set()

    def get_results(self):
        with self.lock:
            filtered_waits = [w for w in self.wait_times if w is not None]
            avg_wait = np.mean(filtered_waits) if filtered_waits else 0
            refusal_rate = self.abandoned / (len(self.wait_times) + self.abandoned) * 100
            return {
                'wait_times': self.wait_times,
                'queue_lengths': self.queue_lengths,
                'system_load': self.system_load,
                'serv_times': self.serv_times,
                'hourly_load': self.hourly_load,
                'timestamps': self.timestamps,
                'avg_wait': avg_wait,
                'refusal_rate': refusal_rate,
                'abandoned': self.abandoned,
                'served_customers': self.served_customers,  # ← ДОБАВИТЬ ЭТУ СТРОКУ
                'total_customers': self.served_customers + self.abandoned,  # ← И ЭТУ
                'params': self.params
            }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("СМО: Продвинутая модель магазина")
        self.setGeometry(100, 100, 1400, 1000)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        control_panel = QVBoxLayout()
        control_panel.setContentsMargins(0, 0, 10, 0)
        control_panel.setSpacing(10)
        main_layout.addLayout(control_panel, stretch=1)

        main_params = QGroupBox("Основные параметры")
        main_layout_params = QVBoxLayout()
        self._add_double_spin(main_layout_params, "Интенсивность прихода (клиенты/мин):", 0.1, 20.0, 5.0, 'arrival_rate')
        self._add_spin(main_layout_params, "Среднее время обслуживания (мин):", 1, 10, 1, 'service_time')
        self._add_spin(main_layout_params, "Число касс:", 1, 20, 4, 'num_cashiers')
        self._add_spin(main_layout_params, "Время моделирования (мин):", 60, 1440, 480, 'sim_time')
        main_params.setLayout(main_layout_params)
        control_panel.addWidget(main_params)

        control_group = QGroupBox("Управление симуляцией")
        control_layout = QVBoxLayout()
        self.btn_start = QPushButton("Запустить симуляцию")
        self.btn_stop = QPushButton("Остановить")
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        control_group.setLayout(control_layout)
        control_panel.addWidget(control_group)

        results_group = QGroupBox("Результаты")
        results_layout = QVBoxLayout()
        self.results_label = QLabel("Ожидание: - \nОтказы: - \nУшли: -")
        self.rec_label = QLabel("Рекомендации: -")
        results_layout.addWidget(self.results_label)
        results_layout.addWidget(self.rec_label)
        results_layout.addStretch()
        results_group.setLayout(results_layout)
        control_panel.addWidget(results_group)

        self.figure = plt.figure(figsize=(12, 10), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas, stretch=3)
        self.setup_plots()
        self.btn_start.clicked.connect(self.start_simulation)
        self.btn_stop.clicked.connect(self.stop_simulation)
        self.sim_thread = None
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_plots)

    def _add_spin(self, layout, label_text, minimum, maximum, value, attr):
        layout.addWidget(QLabel(label_text))
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def _add_double_spin(self, layout, label_text, minimum, maximum, value, attr):
        layout.addWidget(QLabel(label_text))
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def setup_plots(self):
        self.figure.subplots_adjust(left=0.1, right=0.95, bottom=0.08, top=0.95,
                                    hspace=0.5, wspace=0.3)
        gs = GridSpec(3, 2, figure=self.figure)

        # 1. Распределение времени ожидания
        self.ax_wait = self.figure.add_subplot(gs[0, 0])
        self.ax_wait.set_title("1. Распределение времени ожидания", pad=15)
        self.ax_wait.set_xlabel("Минуты", labelpad=10)
        self.ax_wait.set_ylabel("Клиенты", labelpad=10)
        self.ax_wait.grid(True, linestyle='--', alpha=0.3)

        # 2. Длина очереди
        self.ax_queue = self.figure.add_subplot(gs[0, 1])
        self.ax_queue.set_title("2. Динамика длины очереди", pad=15)
        self.ax_queue.set_xlabel("Время (мин)", labelpad=10)
        self.ax_queue.set_ylabel("Длина очереди", labelpad=10)
        self.ax_queue.grid(True, linestyle='--', alpha=0.3)

        # 3. Загрузка касс
        self.ax_load = self.figure.add_subplot(gs[1, 0])
        self.ax_load.set_title("3. Загрузка касс", pad=15)
        self.ax_load.set_xlabel("Время (мин)", labelpad=10)
        self.ax_load.set_ylabel("Занято касс", labelpad=10)
        self.ax_load.grid(True, linestyle='--', alpha=0.3)

        # 4. Время обслуживания
        self.ax_serv = self.figure.add_subplot(gs[1, 1])
        self.ax_serv.set_title("4. Время обслуживания", pad=15)
        self.ax_serv.set_xlabel("Минуты", labelpad=10)
        self.ax_serv.set_ylabel("Частота", labelpad=10)
        self.ax_serv.grid(True, linestyle='--', alpha=0.3)

        # 5. Почасовая загрузка
        self.ax_hourly = self.figure.add_subplot(gs[2, 0])
        self.ax_hourly.set_title("5. Почасовая загрузка", pad=15)
        self.ax_hourly.set_xlabel("Час дня", labelpad=10)
        self.ax_hourly.set_ylabel("Загрузка (%)", labelpad=10)
        self.ax_hourly.grid(True, linestyle='--', alpha=0.3)


    def start_simulation(self):
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()

        params = {
            'arrival_rate': self.arrival_rate_spin.value(),
            'service_time': self.service_time_spin.value(),
            'num_cashiers': self.num_cashiers_spin.value(),
            'sim_time': self.sim_time_spin.value(),
        }

        self.sim_thread = EnhancedQueueSimulation(**params)
        self.sim_thread.start()
        self.update_timer.start(500)

    def stop_simulation(self):
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()
        self.update_timer.stop()
        self.update_plots(final=True)

    def update_plots(self, final=False):
        if not self.sim_thread:
            return

        results = self.sim_thread.get_results() if hasattr(self.sim_thread, 'get_results') else None
        if not results:
            return

        self.results_label.setText(
            f"Среднее ожидание: {results['avg_wait']:.1f} мин\n"
            f"Отказов: {results['refusal_rate']:.1f}%\n"
            f"Ушли не дождавшись: {results['abandoned']}\n"
            f"Обслужено: {results['served_customers']}\n"
            f"Всего клиентов: {results['total_customers']}"
        )

        for ax in [self.ax_wait, self.ax_queue, self.ax_load,
                   self.ax_serv, self.ax_hourly]:
            ax.clear()

        self.ax_wait.set_title("1. Распределение времени ожидания", pad=15)
        self.ax_wait.set_xlabel("Минуты", labelpad=10)
        self.ax_wait.set_ylabel("Клиенты", labelpad=10)

        self.ax_queue.set_title("2. Динамика длины очереди", pad=15)
        self.ax_queue.set_xlabel("Время (мин)", labelpad=10)
        self.ax_queue.set_ylabel("Длина очереди", labelpad=10)

        self.ax_load.set_title("3. Загрузка касс", pad=15)
        self.ax_load.set_xlabel("Время (мин)", labelpad=10)
        self.ax_load.set_ylabel("Занято касс", labelpad=10)

        self.ax_serv.set_title("4. Время обслуживания", pad=15)
        self.ax_serv.set_xlabel("Минуты", labelpad=10)
        self.ax_serv.set_ylabel("Частота", labelpad=10)

        self.ax_hourly.set_title("5. Почасовая загрузка", pad=15)
        self.ax_hourly.set_xlabel("Час дня", labelpad=10)
        self.ax_hourly.set_ylabel("Загрузка (%)", labelpad=10)


        filtered_waits = [w for w in results['wait_times'] if w is not None]
        if filtered_waits:
            self.ax_wait.hist(filtered_waits, bins=30, color='skyblue', edgecolor='black')

        if results['queue_lengths'] and results['timestamps']:
            self.ax_queue.plot(results['timestamps'], results['queue_lengths'], color='salmon')
            self.ax_queue.axhline(y=results['params']['max_queue'], color='r', linestyle='--')
            self.ax_queue.set_xlim(0, results['params']['sim_time'])

        if results['system_load'] and results['timestamps']:
            self.ax_load.plot(results['timestamps'], results['system_load'], color='lightgreen')
            self.ax_load.axhline(y=results['params']['num_cashiers'], color='g', linestyle=':')
            self.ax_load.set_xlim(0, results['params']['sim_time'])

        if results['serv_times']:
            self.ax_serv.hist(results['serv_times'], bins=20, color='purple')
            self.ax_serv.axvline(x=results['params']['service_time'], color='k', linestyle='--')

        if results['hourly_load']:
            hours = list(range(1, len(results['hourly_load']) + 1))
            self.ax_hourly.bar(hours, [x * 100 for x in results['hourly_load']], color='orange')
            step = max(1, len(hours) // 12)
            self.ax_hourly.set_xticks(range(1, len(hours) + 1, step))

        for ax in [self.ax_wait, self.ax_queue, self.ax_load, self.ax_serv, self.ax_hourly]:
            ax.grid(True, linestyle='--', alpha=0.3)

        self.canvas.draw()

        if final:
            self.generate_recommendations(results)

    def generate_recommendations(self, results):
        rec = []
        params = results['params']

        if results['refusal_rate'] > 10:  # >10% отказов
            rec.append("Увеличьте количество касс на 1-2")
        elif results['refusal_rate'] < 1 and params['num_cashiers'] > 1:  # <1% отказов
            rec.append("Можно сократить 1 кассу")

        avg_util = np.mean(results['system_load']) / params['num_cashiers'] if params['num_cashiers'] > 0 else 0
        if avg_util < 0.5:
            rec.append("Низкая загрузка касс - возможно сокращение")
        elif avg_util > 0.9:
            rec.append("Очень высокая загрузка - риски сбоев")

        if not rec:
            rec.append("Система сбалансирована - хорошая работа!")

        self.rec_label.setText("Рекомендации:\n- " + "\n- ".join(rec))

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()