import numpy as np


class StateMachine:
    def __init__(self):
        # Данные с Листа2
        self.states = {'z1': 'Исправен', 'z2': 'Сломан'}
        self.inputs = {
            'x1': 'внесение денег',
            'x2': 'нажатие кнопки выбора продукта',
            'x3': 'нажатие кнопки отмены',
            'x4': 'таймер(2мин)'
        }
        self.outputs = {'y1': 'правильный', 'y2': 'ошибочный'}

        # Таблица вероятностей
        self.prob_matrix = {
            ('внесение денег', 'Исправен'): [0.65, 0.05, 0.05, 0.25],
            ('внесение денег', 'Сломан'): [0.05, 0.0, 0.05, 0.9],
            ('нажатие кнопки выбора продукта', 'Исправен'): [0.65, 0.05, 0.05, 0.25],
            ('нажатие кнопки выбора продукта', 'Сломан'): [0.05, 0.0, 0.05, 0.9],
            ('нажатие кнопки отмены', 'Исправен'): [0.65, 0.05, 0.05, 0.25],
            ('нажатие кнопки отмены', 'Сломан'): [0.05, 0.0, 0.05, 0.9],
            ('таймер(2мин)', 'Исправен'): [0.65, 0.05, 0.05, 0.25],
            ('таймер(2мин)', 'Сломан'): [0.05, 0.0, 0.05, 0.9]
        }

        # Возможные исходы (новое состояние, выход)
        self.outcomes = [
            ('Исправен', 'правильный'),
            ('Исправен', 'ошибочный'),
            ('Сломан', 'правильный'),
            ('Сломан', 'ошибочный')
        ]

    def get_transition(self, current_state, input_signal, random_value):
        # Получаем вероятности для текущей комбинации
        probs = self.prob_matrix[(input_signal, current_state)]

        # Создаем кумулятивные вероятности
        cum_probs = np.cumsum(probs)

        # Находим индекс исхода по случайному числу (векторизовано)
        outcome_idx = np.searchsorted(cum_probs, random_value, side='right')

        # Возвращаем соответствующий исход
        return self.outcomes[outcome_idx]

    def simulate(self):
        # Начальное состояние всегда "Исправен"
        current_state = "Исправен"
        print(f"Начальное состояние установлено: {current_state}")

        while True:
            print("\n" + "=" * 50)
            print("Автомат состояний (торговый аппарат)")
            print("=" * 50)

            # Отображаем текущее состояние
            print(f"Текущее состояние: {current_state}")

            print("\nДоступные входные сигналы:")
            for key, value in self.inputs.items():
                print(f" - {value}")

            input_signal = input("Введите входной сигнал (или 'выход' для завершения): ")

            if input_signal.lower() == 'выход':
                print("Работа программы завершена.")
                break

            # Проверка корректности входного сигнала
            valid_signals = list(self.inputs.values())
            if input_signal not in valid_signals:
                print("Ошибка: неверный входной сигнал")
                continue

            # Генерация случайного числа
            random_value = round(np.random.uniform(0, 1), 2)
            print(f"\nСгенерированное случайное число: {random_value}")

            # Определение перехода
            new_state, output = self.get_transition(current_state, input_signal, random_value)

            print(f"\nРезультат:")
            print(f"Новое состояние: {new_state}")
            print(f"Выходной сигнал: {output}")

            # Обновляем текущее состояние для следующей итерации
            current_state = new_state

            # Предложение продолжить или выйти
            continue_choice = input("\nПродолжить работу? (да/нет): ")
            if continue_choice.lower() in ['нет', 'н', 'no', 'n']:
                print("Работа программы завершена.")
                break


# Запуск автомата
if __name__ == "__main__":
    machine = StateMachine()
    machine.simulate()