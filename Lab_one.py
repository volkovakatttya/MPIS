def function(x,z):
        inputs = ["внесение денег", "нажатие кнопки выбора продукта", "нажатие кнопки отмены", "таймер(2мин)"]
        output = ["выдан продукт", "сброс суммы", "показать сумму", "отказ от денег","таймер истек"]
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
        next = matrix_one[x][z]
        output_sigma = matrix_two[x][z]
        z_next = states[next]
        y = output[output_sigma]

        print(f"Входной сигнал: {x}")
        print(f"Текущее состояние: {z}")
        print(f"Следующее состояние: {z_next}")
        print(f"Выходной сигнал: {y}")
        return  matrix_one[x][z]

z2 = 1
number = 0
while True:
    x = 0
    z = 0
    if z2 == 1:
        z = int(input("Введите начальное состояние сигнала: ")) - 1
        x = int(input("Введите номер входного сигнала: ")) - 1
        number = function(x,z)
    z2 += 1
    input_solve = input("Введите stop чтобы остановить программу ничего чтобы дальше: ")
    if input_solve == "stop":
        break
    else:
        x = int(input("Введите номер входного сигнала: ")) - 1
        number = function(x,number)
