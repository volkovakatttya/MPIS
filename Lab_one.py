def function(x, z):
    inputs = ["внесение денег", "нажатие кнопки выбора продукта", "нажатие кнопки отмены", "таймер(2мин)"]
    output = ["выдан продукт", "сброс суммы", "показать сумму", "отказ от денег", "таймер истек"]
    states = ["выдача продукта", "ожидание выбора", "продукт выбран"]
    matrix_one = [
        [0, 1, 0],  # x1: z1=0, z2=1, z1=0
        [0, 2, 2],  # x2: z1=0, z3=2, z3=2
        [1, 1, 1],  # x3: z2=1, z2=1, z2=1
        [1, 1, 1]  # x4: z2=1, z2=1, z2=1
    ]
    matrix_two = [
        [3, 3, 2],  # x1: y4=3, y4=3, y3=2
        [0, 2, 1],  # x2: y1=0, y3=2, y2=1
        [0, 1, 1],  # x3: y1=0, y2=1, y2=1
        [4, 4, 4]  # x4: y5=4, y5=4, y5=4
    ]

    print("Входные сигналы:")
    for i, signal in enumerate(inputs, 1):
        print(f"{i}. {signal}")

    print("Доступные состояния:")
    for i, state in enumerate(states, 1):
        print(f"{i}. {state}")

    next_state = matrix_one[x][z]
    output_sigma = matrix_two[x][z]
    z_next = states[next_state]
    y = output[output_sigma]

    print(f"Входной сигнал: {inputs[x]}")
    print(f"Текущее состояние: {states[z]}")
    print(f"Следующее состояние: {z_next}")
    print(f"Выходной сигнал: {y}")
    return next_state


def show_available_inputs():
    inputs = ["внесение денег", "нажатие кнопки выбора продукта", "нажатие кнопки отмены", "таймер(2мин)"]
    print("\nДоступные входные сигналы:")
    for i, signal in enumerate(inputs, 1):
        print(f"{i}. {signal}")


current_state = 1
states = ["выдача продукта", "ожидание выбора", "продукт выбран"]

while True:
    print(f"\nТекущее состояние: {states[current_state]}")
    show_available_inputs()

    x = int(input("Введите номер входного сигнала: ")) - 1

    if x < 0 or x > 3:
        print("Ошибка: неверный номер сигнала. Введите число от 1 до 4.")
        continue

    current_state = function(x, current_state)

    input_solve = input("\nВведите 'stop' чтобы остановить программу или нажмите Enter чтобы продолжить: ")
    if input_solve.lower() == "stop":
        break
    print()