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
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt

class Customer:
    def __init__(self, service_time):
        self.required_service_time = service_time #время обслуживания

class EnhancedQueueSimulation(threading.Thread):
    def __init__(self, arrival_rate, service_time, num_cashiers, num_runs=1):
        super().__init__()
        # Фиксированное время моделирования - 720 минут (12 часов)
        self.params = {
            'arrival_rate': arrival_rate,    # Интенсивность прибытия клиентов
            'service_time': service_time,     # Среднее время обслуживания
            'num_cashiers': num_cashiers,    # Количество касс
            'sim_time': 720,                 # Фиксированное время моделирования
            'num_runs': num_runs            # Количество прогонов
        }
        # Статистические данные для одного прогона
        self.wait_times = []      # В данном случае всегда 0
        self.queue_lengths = []   # Всегда 0 или 1 (только обслуживаемый клиент)
        self.system_load = []     # Загрузка системы (сколько касс занято)
        self.serv_times = []      # Времена обслуживания
        self.abandoned = 0        # Клиенты, которые ушли когда все кассы заняты
        self.served_customers = 0 # Количество обслуженных клиентов
        self.timestamps = []      # Временные метки
        
        # Статистика по кассам для множественных прогонов
        self.cashier_stats = []   # Статистика по каждой кассе
        self.run_results = []     # Результаты всех прогонов
        
        # Механизмы управления потоком
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.current_run = 0
        self.progress = 0

    def get_arrival_interval(self):
        # Генерирует случайный интервал между прибытиями клиентов f(x; λ) = λ * e^(-λ*x)
        return random.expovariate(self.params['arrival_rate'])

    def customer(self, env, cashiers):
        # Создаем нового клиента
        customer = Customer(self.params['service_time'])
        
        # Клиент ищет свободную кассу
        free_cashier = None
        for i, cashier in enumerate(cashiers):
            if not cashier.busy:  # Если касса свободна
                free_cashier = (i, cashier)
                break
        
        if free_cashier is not None:
            # Нашлась свободная касса - занимаем ее
            cashier_idx, cashier = free_cashier
            cashier.busy = True
            with self.lock:
                self.served_customers += 1
                self.serv_times.append(customer.required_service_time)
            
            # Обслуживание клиента
            yield env.timeout(customer.required_service_time)
            
            # Освобождаем кассу
            cashier.busy = False
        else:
            # Все кассы заняты - клиент уходит
            with self.lock:
                self.abandoned += 1

    def setup(self, env, cashiers):
        # Основной процесс генерации клиентов
        while not self.stop_event.is_set() and env.now < self.params['sim_time']:
            # Ждем случайный интервал до следующего клиента
            interval = self.get_arrival_interval()
            yield env.timeout(interval)
            
            # Запускаем процесс для нового клиента
            env.process(self.customer(env, cashiers))
            
            # Собираем статистику
            with self.lock:
                # Считаем количество занятых касс
                busy_cashiers = sum(1 for cashier in cashiers if cashier.busy)
                self.system_load.append(busy_cashiers)
                self.timestamps.append(env.now)
                # В данной модели очереди нет - только занятые кассы
                self.queue_lengths.append(0)

    def run_single_simulation(self):
        # Выполняет одну симуляцию
        env = simpy.Environment()
        
        # Создаем кассы как простые объекты с состоянием занятости
        cashiers = [type('Cashier', (), {'busy': False, 'id': i})() 
                   for i in range(self.params['num_cashiers'])]
        
        # Запускаем процесс генерации клиентов
        env.process(self.setup(env, cashiers))
        
        # Запускаем симуляцию
        env.run(until=self.params['sim_time'])
        
        # Собираем результаты одного прогона (N_abandoned / N_total) × 100%
        total_customers = self.served_customers + self.abandoned
        refusal_rate = (self.abandoned / total_customers * 100) if total_customers > 0 else 0
        
        # Собираем статистику по занятости касс
        if self.system_load:
            avg_load = np.mean(self.system_load)
            utilization = avg_load / self.params['num_cashiers'] * 100
        else:
            avg_load = 0
            utilization = 0
            
        return {
            'served': self.served_customers,
            'abandoned': self.abandoned,
            'refusal_rate': refusal_rate,
            'avg_load': avg_load,
            'utilization': utilization,
            'total_customers': total_customers
        }

    def run(self):
        # Основной метод выполнения множественных прогонов
        all_results = []
        
        for run_idx in range(self.params['num_runs']):
            if self.stop_event.is_set():
                break
                
            # Сбрасываем статистику для нового прогона
            with self.lock:
                self.wait_times = []
                self.queue_lengths = []
                self.system_load = []
                self.serv_times = []
                self.abandoned = 0
                self.served_customers = 0
                self.timestamps = []
                self.current_run = run_idx + 1
                self.progress = (run_idx + 1) / self.params['num_runs'] * 100
            
            # Выполняем один прогон
            result = self.run_single_simulation()
            all_results.append(result)
            
            # Обновляем прогресс
            self.run_results = all_results

    def stop(self):
        # Останавливает симуляцию
        self.stop_event.set()

    def get_results(self):
        # Возвращает усредненные результаты по всем прогонам
        with self.lock:
            if not self.run_results:
                return None
                
            # Вычисляем средние значения по всем прогонам (x1 + x2 + ... + xn) / n
            avg_served = np.mean([r['served'] for r in self.run_results])
            avg_abandoned = np.mean([r['abandoned'] for r in self.run_results])
            avg_refusal_rate = np.mean([r['refusal_rate'] for r in self.run_results])
            avg_utilization = np.mean([r['utilization'] for r in self.run_results])
            avg_total_customers = np.mean([r['total_customers'] for r in self.run_results])
            
            return {
                'avg_served': avg_served,
                'avg_abandoned': avg_abandoned,
                'avg_refusal_rate': avg_refusal_rate,
                'avg_utilization': avg_utilization,
                'avg_total_customers': avg_total_customers,
                'num_runs': self.params['num_runs'],
                'current_run': self.current_run,
                'progress': self.progress,
                'all_results': self.run_results,
                'params': self.params
            }








#       !!!!!!!!!!!!!!!                 ГРАФИКИ               !!!!!!!!!!!!!!!           #





class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Настройка главного окна
        self.setWindowTitle("СМО: Модель магазина с выбором кассы")
        self.setGeometry(100, 100, 1400, 1000)

        # Создание центрального виджета и основного layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Создание панели управления слева
        control_panel = self.create_control_panel()
        main_layout.addLayout(control_panel, stretch=1)

        # Создание области с графиками справа
        self.figure = plt.figure(figsize=(12, 10), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas, stretch=3)
        
        # Настройка графиков и соединение сигналов
        self.setup_plots()
        self.connect_signals()
        
        # Инициализация переменных
        self.sim_thread = None
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_plots)

    def create_control_panel(self):
        # Создает панель управления с элементами ввода
        control_panel = QVBoxLayout()
        control_panel.setContentsMargins(0, 0, 10, 0)
        control_panel.setSpacing(10)

        # Группа основных параметров
        main_params = QGroupBox("Основные параметры")
        main_layout_params = QVBoxLayout()
        self._add_double_spin(main_layout_params, "Интенсивность прихода (клиенты/мин):", 0.1, 20.0, 0.5, 'arrival_rate')
        self._add_spin(main_layout_params, "Среднее время обслуживания (мин):", 1, 10, 3, 'service_time')
        self._add_spin(main_layout_params, "Число касс:", 1, 20, 4, 'num_cashiers')
        self._add_spin(main_layout_params, "Количество прогонов:", 1, 100000, 100, 'num_runs')
        
        # Информация о времени моделирования
        time_label = QLabel("Время моделирования: 720 минут (фиксировано)")
        main_layout_params.addWidget(time_label)
        
        main_params.setLayout(main_layout_params)
        control_panel.addWidget(main_params)

        # Группа управления симуляцией
        control_group = QGroupBox("Управление симуляцией")
        control_layout = QVBoxLayout()
        self.btn_start = QPushButton("Запустить симуляцию")
        self.btn_stop = QPushButton("Остановить")
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        control_group.setLayout(control_layout)
        control_panel.addWidget(control_group)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        control_panel.addWidget(self.progress_bar)

        # Группа результатов
        results_group = QGroupBox("Результаты")
        results_layout = QVBoxLayout()
        self.results_label = QLabel("Запустите симуляцию для получения результатов")
        self.rec_label = QLabel("Рекомендации появятся после симуляции")
        results_layout.addWidget(self.results_label)
        results_layout.addWidget(self.rec_label)
        results_layout.addStretch()
        results_group.setLayout(results_layout)
        control_panel.addWidget(results_group)

        return control_panel

    def _add_spin(self, layout, label_text, minimum, maximum, value, attr):
        # Создает спин-бокс для целочисленных значений
        layout.addWidget(QLabel(label_text))
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def _add_double_spin(self, layout, label_text, minimum, maximum, value, attr):
        # Создает спин-бокс для вещественных значений
        layout.addWidget(QLabel(label_text))
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        setattr(self, attr + '_spin', spin)
        layout.addWidget(spin)

    def setup_plots(self):
        # Настраивает макет графиков - оставляем только 2 графика
        self.figure.subplots_adjust(left=0.1, right=0.95, bottom=0.08, top=0.95,
                                    hspace=0.5, wspace=0.3)
        gs = GridSpec(2, 1, figure=self.figure)  # Теперь 2 строки, 1 столбец

        # 1. График загрузки касс во времени (только для последнего прогона)
        self.ax_load = self.figure.add_subplot(gs[0, 0])
        self.ax_load.set_title("1. Загрузка касс во времени", pad=15)
        self.ax_load.set_xlabel("Время (мин)", labelpad=10)
        self.ax_load.set_ylabel("Занято касс", labelpad=10)
        self.ax_load.grid(True, linestyle='--', alpha=0.3)

        # 2. График статистики по прогонам
        self.ax_stats = self.figure.add_subplot(gs[1, 0])
        self.ax_stats.set_title("2. Статистика по множественным прогонам", pad=15)
        self.ax_stats.set_xlabel("Прогоны", labelpad=10)
        self.ax_stats.set_ylabel("Количество", labelpad=10)
        self.ax_stats.grid(True, linestyle='--', alpha=0.3)

        # График распределения времени обслуживания убран

    def connect_signals(self):
        # Соединяет кнопки с соответствующими методами
        self.btn_start.clicked.connect(self.start_simulation)
        self.btn_stop.clicked.connect(self.stop_simulation)

    def start_simulation(self):
        # Запускает симуляцию в отдельном потоке
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()

        # Собираем параметры из интерфейса
        params = {
            'arrival_rate': self.arrival_rate_spin.value(),
            'service_time': self.service_time_spin.value(),
            'num_cashiers': self.num_cashiers_spin.value(),
            'num_runs': self.num_runs_spin.value(),
        }

        # Создаем и запускаем поток симуляции
        self.sim_thread = EnhancedQueueSimulation(**params)
        self.sim_thread.start()
        
        # Показываем прогресс-бар
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Запускаем таймер для обновления графиков
        self.update_timer.start(500)

    def stop_simulation(self):
        # Останавливает симуляцию
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.stop()
            self.sim_thread.join()
        self.update_timer.stop()
        self.progress_bar.setVisible(False)

    def update_plots(self):
        # Обновляет графики и отображает результаты
        if not self.sim_thread or not self.sim_thread.is_alive():
            # Симуляция завершена - финальное обновление
            if hasattr(self.sim_thread, 'get_results'):
                results = self.sim_thread.get_results()
                if results:
                    self.display_results(results)
                    self.update_plot_data(results)
                    self.generate_recommendations(results)
            self.progress_bar.setVisible(False)
            return
        
        # Симуляция还在运行 - обновляем прогресс и промежуточные результаты
        if hasattr(self.sim_thread, 'get_results'):
            results = self.sim_thread.get_results()
            if results:
                self.display_results(results)
                self.update_plot_data(results)
                # Обновляем прогресс-бар
                self.progress_bar.setValue(int(results.get('progress', 0)))

    def display_results(self, results):
        # Отображает текстовые результаты
        if not results:
            return
            
        self.results_label.setText(
            f"Прогон: {results.get('current_run', 0)}/{results['num_runs']}\n"
            f"Среднее обслужено: {results['avg_served']:.1f} клиентов\n"
            f"Среднее ушло: {results['avg_abandoned']:.1f} клиентов\n"
            f"Процент отказов: {results['avg_refusal_rate']:.1f}%\n"
            f"Загрузка системы: {results['avg_utilization']:.1f}%\n"
            f"Всего клиентов: {results['avg_total_customers']:.1f}"
        )

    def update_plot_data(self, results):
        # Обновляет данные на графиках
        if not results:
            return

        # Очищаем все графики
        for ax in [self.ax_load, self.ax_stats]:
            if ax:
                ax.clear()

        # Восстанавливаем заголовки и подписи
        self.ax_load.set_title("1. Загрузка касс во времени", pad=15)
        self.ax_load.set_xlabel("Время (мин)", labelpad=10)
        self.ax_load.set_ylabel("Занято касс", labelpad=10)

        self.ax_stats.set_title("2. Статистика по множественным прогонам", pad=15)
        self.ax_stats.set_xlabel("Прогоны", labelpad=10)
        self.ax_stats.set_ylabel("Количество", labelpad=10)

        # 1. График загрузки касс (только если есть данные)
        if hasattr(self.sim_thread, 'system_load') and self.sim_thread.system_load and hasattr(self.sim_thread, 'timestamps'):
            self.ax_load.plot(self.sim_thread.timestamps, self.sim_thread.system_load, 
                             color='lightgreen', alpha=0.7)
            self.ax_load.axhline(y=results['params']['num_cashiers'], color='g', 
                               linestyle=':', label='Всего касс')
            self.ax_load.set_xlim(0, 720)
            self.ax_load.legend()

        # 2. График статистики по прогонам
        if results.get('all_results'):
            runs = list(range(1, len(results['all_results']) + 1))
            served = [r['served'] for r in results['all_results']]
            abandoned = [r['abandoned'] for r in results['all_results']]
            
            self.ax_stats.plot(runs, served, 'g-', label='Обслужено', alpha=0.7)
            self.ax_stats.plot(runs, abandoned, 'r-', label='Ушли', alpha=0.7)
            
            # Линии средних значений
            if len(served) > 0:
                self.ax_stats.axhline(y=results['avg_served'], color='g', 
                                    linestyle='--', label=f'Ср. обслужено: {results["avg_served"]:.1f}')
            if len(abandoned) > 0:
                self.ax_stats.axhline(y=results['avg_abandoned'], color='r', 
                                    linestyle='--', label=f'Ср. ушли: {results["avg_abandoned"]:.1f}')
            
            self.ax_stats.legend()
            self.ax_stats.set_xlim(1, len(runs))

        # Добавляем сетку на все графики
        for ax in [self.ax_load, self.ax_stats]:
            if ax:
                ax.grid(True, linestyle='--', alpha=0.3)

        # Обновляем canvas
        self.canvas.draw()

    def generate_recommendations(self, results):
        # Генерирует рекомендации на основе результатов симуляции
        rec = []
        params = results['params']

        # Анализируем процент отказов
        if results['avg_refusal_rate'] > 10:
            rec.append("Увеличьте количество касс - высокий процент отказов")
        elif results['avg_refusal_rate'] < 2 and params['num_cashiers'] > 1:
            rec.append("Можно сократить количество касс - низкий процент отказов")

        # Анализируем загрузку системы
        if results['avg_utilization'] < 40:
            rec.append("Низкая загрузка касс - возможно сокращение")
        elif results['avg_utilization'] > 90:
            rec.append("Очень высокая загрузка - риски при пиковых нагрузках")

        # Анализируем эффективность
        efficiency = results['avg_served'] / 720  # Клиентов в минуту
        if efficiency < 0.5:
            rec.append("Низкая пропускная способность - оптимизируйте процесс")

        # Если нет конкретных рекомендаций
        if not rec:
            rec.append("Система сбалансирована - хорошая работа!")

        # Обновляем текст рекомендаций
        self.rec_label.setText("Рекомендации:\n- " + "\n- ".join(rec))

def main():
    # Основная функция приложения
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()