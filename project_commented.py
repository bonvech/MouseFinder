# =============================================================================
# ПРОГРАММНЫЙ ИНТЕРФЕЙС «АНАЛИЗ ДВИЖЕНИЙ МЫШИ»
# Школа № 192, 2026 г. (Сухинин Ю. Д., Китаев Н. И.; рук. Бонвеч Е. А.)
#
# ЗАЧЕМ: в эксперименте ИППИ РАН мыши предлагают два образца запаха. Нужно
# измерить, сколько времени мышь обнюхивает каждый образец. Вручную это делать
# долго и неточно — программа считает время по видео автоматически.
#
# КАК РАБОТАЕТ (коротко):
#   1) PyQt6 показывает окно: выбрать видеофайл, включить/выключить запись
#      кадров, нажать «Начать анализ».
#   2) OpenCV покадрово читает видео, находит тёмный силуэт мыши (порог
#      яркости -> контур) и определяет две крайние точки контура — nose/tail.
#   3) Пользователь двойным кликом задаёт две круговые области вокруг образцов
#      и ползунками подбирает их радиусы и порог выделения мыши.
#   4) Если какая-то из точек мыши оказалась внутри круга — кадр добавляется
#      к счётчику времени соответствующего образца. Время = число кадров,
#      делённое на частоту кадров (выражается в миллисекундах).
#   5) Итог предлагается сохранить в result.txt (строка с разделителем ';'),
#      а при включённой записи все обработанные кадры складываются в папку
#      «Анализ_ДАТА_ВРЕМЯ».
#
# ЗАПУСК: python3 project.py  (или start.bat, который берёт Python из
#         виртуального окружения /home/alena/SIT/env).
#         Требуются: Python 3, PyQt6, opencv-python, numpy.
#
# ВАЖНО: этот файл — КОПИЯ project.py, в которую добавлены только комментарии.
#         Исполняемый код побайтно совпадает с оригиналом.
# =============================================================================
import sys
import os
# Стандартная библиотека:
#   sys      — аргументы командной строки и sys.exit();
#   os       — пути, проверка файлов, создание папок;
#   datetime — метка времени в имени папки с кадрами;
#   copy     — копия кадра, чтобы пересчитывать контур на паузе.
# Сторонние библиотеки (см. следующий блок): PyQt6, OpenCV, NumPy, math.
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
# PyQt6  — окна, кнопки, диалоги выбора файла и цикл событий QApplication.
# cv2    — чтение видео, обработка изображений, свои окна/ползунки/кнопки.
# numpy  — массивы пикселей и маски.
# math   — atan2/hypot/degrees/sqrt: геометрия при поиске «носа» и «хвоста».
import cv2
import numpy as np
import math as m
import datetime
import copy

# Единственный класс программы — главное окно (QMainWindow).
# Отвечает за интерфейс и «оркестрацию»:
#   выбор файла -> проверка -> запуск анализа -> сохранение результата.
# Вся математика и работа с видео находятся в методе analyze_video().
class VideoAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        # Создаём окно 800x400 с заголовком. Дальше в QVBoxLayout по порядку
        # добавляются: заголовок, описание, панель файла, панель записи,
        # кнопки управления. Строка состояния (QStatusBar) — внизу окна.
        self.setWindowTitle("Анализатор видео поведения мыши")
        self.setGeometry(100, 100, 800, 400)
        
        # Флаг для завершения программы
        # Заготовка флага завершения. В этой версии он нигде не читается:
        # выход делается кнопкой «Отмена» (self.close) или кнопкой EXIT в OpenCV.
        self.should_close = False
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Заголовок
        title_label = QLabel("Анализатор поведения мыши в видео")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin: 20px;")
        layout.addWidget(title_label)
        
        # Описание
        desc_label = QLabel(
            "Эта программа анализирует видео с мышью, отслеживая её движение\n"
            "и подсчитывая время нахождения в заданных областях."
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("font-size: 14px; margin: 10px; color: #555;")
        layout.addWidget(desc_label)
        
        # Панель выбора файла
        file_panel = QGroupBox("Выбор видеофайла")
        file_layout = QVBoxLayout()
        
        # Поле для пути к файлу
        path_layout = QHBoxLayout()
        self.path_label = QLabel("Путь к видео:")
        path_layout.addWidget(self.path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Выберите видеофайл...")
        # Поле пути доступно только для чтения: заполняется исключительно через
        # диалог «Обзор...», чтобы пользователь не вбил несуществующий путь.
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit, 1)
        
        # Сигнал clicked «присоединяется» к слоту browse_video_file — типичный
        # механизм сигнал/слот Qt: нажатие кнопки вызывает метод класса.
        self.browse_button = QPushButton("Обзор...")
        self.browse_button.clicked.connect(self.browse_video_file)
        path_layout.addWidget(self.browse_button)
        
        file_layout.addLayout(path_layout)
        
        # Информация о поддерживаемых форматах
        format_label = QLabel("Поддерживаемые форматы: MP4, AVI, MKV, MOV, WMV, FLV и другие")
        format_label.setStyleSheet("font-size: 12px; color: #666; margin-top: 10px;")
        file_layout.addWidget(format_label)
        
        file_panel.setLayout(file_layout)
        layout.addWidget(file_panel)
        
        # Настройки записи
        record_panel = QGroupBox("Настройки записи")
        record_layout = QVBoxLayout()
        
        # Флажок «Сохранять кадры анализа в папку» по умолчанию выключен.
        # Его состояние считывается в start_analysis() перед запуском обработки.
        self.record_checkbox = QCheckBox("Сохранять кадры анализа в папку")
        self.record_checkbox.setChecked(False)
        record_layout.addWidget(self.record_checkbox)
        
        record_info = QLabel("Если включено, каждый кадр будет сохраняться как изображение")
        record_info.setStyleSheet("font-size: 11px; color: #777; font-style: italic;")
        record_layout.addWidget(record_info)
        
        record_panel.setLayout(record_layout)
        layout.addWidget(record_panel)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        
        # Зелёная кнопка старта. Изначально заблокирована (setEnabled(False)) и
        # становится активной только после успешной проверки видеофайла.
        self.start_button = QPushButton("Начать анализ")
        self.start_button.clicked.connect(self.start_analysis)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.start_button)
        
        # Красная кнопка «Отмена» просто закрывает окно (self.close), что
        # завершает приложение, так как других окон у QApplication нет.
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 16px;
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Выберите видеофайл для анализа")
        
        # Переменные для анализа
        # Поля объекта: video_path — путь к выбранному видео (None до выбора);
        # record_video — нужно ли сохранять кадры (обновляется при старте анализа).
        self.video_path = None
        self.record_video = False
        
        # Растягиваем все к центру
        layout.addStretch(1)

    # Слот кнопки «Обзор...». Открывает QFileDialog с фильтром видео-расширений
    # из домашней папки, запоминает путь, показывает его в поле и проверяет
    # файл через check_video_file(). При успехе разблокирует «Начать анализ»,
    # при ошибке — показывает предупреждение и оставляет кнопку неактивной.
    def browse_video_file(self):
        """Открыть диалог выбора видеофайла"""
        filters = "Видео файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.3gp *.ogg);;" \
                 "Все файлы (*.*)"
        
        home_dir = os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите видеофайл для анализа",
            home_dir,
            filters
        )
        
        if file_path:
            self.video_path = file_path
            self.path_edit.setText(file_path)
            
            if self.check_video_file(file_path):
                self.start_button.setEnabled(True)
                self.status_bar.showMessage(f"Выбран файл: {os.path.basename(file_path)}")
            else:
                self.start_button.setEnabled(False)
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Не удалось открыть видеофайл. Проверьте формат и доступность файла."
                )
                self.status_bar.showMessage("Ошибка: неверный видеофайл")

    # Быстрая проверка «а видео точно откроется?»: файл существует,
    # cv2.VideoCapture смог открыть поток и прочитать первый кадр.
    # Возвращает True/False; сам объект захвата сразу освобождается.
    def check_video_file(self, file_path):
        """Проверить, можно ли открыть видеофайл"""
        if not os.path.exists(file_path):
            return False
        
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return False
        
        ret, frame = cap.read()
        cap.release()
        
        return ret and frame is not None

    # Слот кнопки «Начать анализ»: проверяет путь, считывает флажок записи,
    # задаёт подтверждающий вопрос (имя файла, путь, режим записи), затем
    # скрывает окно PyQt, чтобы не мешать окну OpenCV, и запускает анализ.
    # processEvents() нужен, чтобы статус «Запуск анализа...» успел отрисоваться.
    def start_analysis(self):
        """Запустить анализ видео"""
        if not self.video_path or not os.path.exists(self.video_path):
            QMessageBox.warning(self, "Ошибка", "Видеофайл не выбран или не существует!")
            return
        
        self.record_video = self.record_checkbox.isChecked()
        
        reply = QMessageBox.question(
            self,
            "Начать анализ",
            f"Начать анализ видео?\n\n"
            f"Файл: {os.path.basename(self.video_path)}\n"
            f"Путь: {self.video_path}\n"
            f"Сохранение кадров: {'Да' if self.record_video else 'Нет'}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_bar.showMessage("Запуск анализа...")
            QApplication.processEvents()
            
            # Закрываем окно выбора файла
            self.hide()
            
            # Запускаем анализ
            self.run_video_analysis()

    # Обёртка над «тяжёлым» analyze_video(): ловит любые исключения и показывает
    # их в окне QMessageBox. Если результат получен — предлагает его сохранить.
    # Блок finally гарантирует, что главное окно снова появится на экране даже
    # при ошибке, а статус обновится.
    def run_video_analysis(self):
        """Запустить анализ видео"""
        try:
            # Запускаем анализ и получаем результаты
            results = self.analyze_video(self.video_path, self.record_video)
            
            # После завершения анализа спрашиваем о сохранении
            if results:
                self.ask_save_results(results)
                
        except Exception as e:
            QMessageBox.critical(
                None,
                "Ошибка анализа",
                f"Произошла ошибка при анализе видео:\n{str(e)}"
            )
        finally:
            # Возвращаемся к окну выбора файла
            self.show()
            self.status_bar.showMessage("Анализ завершен. Выберите новый файл.")

    # Вопрос «сохранить результаты в result.txt?» после завершения просмотра.
    # При ответе «Да» передаёт словарь результатов в save_results_to_file().
    def ask_save_results(self, results):
        """Спросить пользователя о сохранении результатов"""
        reply = QMessageBox.question(
            self,
            "Сохранение результатов",
            "Хотите сохранить результаты анализа в файл?\n\n"
            f"Результаты будут сохранены в файл result.txt",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Пробуем сохранить в несколько мест
            self.save_results_to_file(results)

    # Запись итогов в текстовый файл result.txt (кодировка UTF-8).
    # Файл открывается в режиме 'a' (добавление): результаты разных видео
    # накапливаются в одной таблице, поэтому шапка пишется только когда файл
    # новый или пустой. Разделитель полей — точка с запятой.
    # Место записи: сначала папка рядом с видео; если нет прав — рабочий стол;
    # если не получилось и там — строка показывается в окне для ручного копирования.
    def save_results_to_file(self, results):
        """Сохранить результаты в текстовый файл"""
        try:
            # Основной путь: <папка с видео>/result.txt. Рядом с исходником удобно
            # искать отчёт, поэтому пробуем его первым.
            # Сначала пробуем сохранить в папку с видео
            video_dir = os.path.dirname(self.video_path) if self.video_path else os.getcwd()
            file_path = os.path.join(video_dir, 'result.txt')
            
            # Пробуем сохранить
            try:
                # Проверяем, существует ли файл
                file_exists = os.path.exists(file_path)
                
                # Открываем файл для добавления (если нет - создается)
                # Режим 'a' не стирает старые строки. Заголовок таблицы добавляется
                # только один раз — для нового/пустого файла.
                # Строка результата: имя видео; время у образца 1 (мс); время у
                # образца 2 (мс); время с первого контакта (мм:сс);
                with open(file_path, 'a', encoding='utf-8') as f:
                    # Если файл новый или пустой, добавляем заголовок
                    if not file_exists or os.path.getsize(file_path) == 0:
                        f.write("название файла;время первое;время второе;время исследования (мм:сс);\n")
                    
                    # Записываем результаты с временем исследования в формате мм:сс
                    line = f"{results['video_file']};{results['time_area1']};{results['time_area2']};{results['research_time_str']};\n"
                    f.write(line)
                
                print(f"✓ Результаты сохранены в: {file_path}")
                
                QMessageBox.information(
                    self,
                    "Результаты сохранены",
                    f"Результаты успешно сохранены в файл:\n{file_path}\n\n"
                    f"Формат: название файла;время первое;время второе;время исследования (мм:сс);"
                )
                
            except (PermissionError, OSError) as e:
                print(f"✗ Не удалось сохранить в папку с видео: {e}")
                
                # Сюда попадаем при PermissionError/OSError (например, видео лежит на
                # диске только для чтения). Папку ~/Desktop при необходимости создаём.
                # Пробуем сохранить на рабочий стол
                desktop_folder = os.path.expanduser("~/Desktop")
                if not os.path.exists(desktop_folder):
                    # Если нет папки Desktop, создаем
                    os.makedirs(desktop_folder, exist_ok=True)
                
                file_path = os.path.join(desktop_folder, 'result.txt')
                file_exists = os.path.exists(file_path)
                
                # Резервный файл имеет ровно тот же формат, что и основной.
                with open(file_path, 'a', encoding='utf-8') as f:
                    # Если файл новый или пустой, добавляем заголовок
                    if not file_exists or os.path.getsize(file_path) == 0:
                        f.write("название файла;время первое;время второе;время исследования (мм:сс);\n")
                    
                    # Записываем результаты с временем исследования в формате мм:сс
                    line = f"{results['video_file']};{results['time_area1']};{results['time_area2']};{results['research_time_str']};\n"
                    f.write(line)
                
                print(f"✓ Результаты сохранены на рабочий стол: {file_path}")
                
                QMessageBox.information(
                    self,
                    "Результаты сохранены",
                    f"Результаты сохранены на рабочий стол:\n{file_path}\n\n"
                    f"Формат: название файла;время первое;время второе;время исследования (мм:сс);"
                )
            
        except Exception as e:
            print(f"✗ Критическая ошибка сохранения: {e}")
            
            # Полный провал записи: показываем готовую строку в окне предупреждения,
            # чтобы данные не потерялись и пользователь скопировал их вручную.
            # Показываем результаты для ручного сохранения
            QMessageBox.warning(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить результаты в файл:\n{str(e)}\n\n"
                f"Скопируйте результаты вручную:\n\n"
                f"{results['video_file']};{results['time_area1']};{results['time_area2']};{results['research_time_str']};"
            )

    # -------------------------------------------------------------------------
    # ЯДРО ПРОГРАММЫ: покадровый разбор видео.
    #
    # Пайплайн для каждого кадра:
    #   contour()  — по порогу яркости выделяет контур мыши (берётся ВТОРОЙ
    #                по площади контур: самый большой считается фоном/ареной);
    #   polar()    — переводит точки контура в полярные координаты и находит
    #                две самые далёкие «конечности» (условно нос и хвост);
    #   minDist*() — из этих двух точек выбирает ближайшую к центру области;
    #   если расстояние < радиус области — увеличиваем счётчик кадров области.
    #
    # Время считается не по секундомеру, а по числу кадров:
    #   FPS в программе = настоящий FPS / 1000 («кадров в миллисекунду»),
    #   поэтому nframe / FPS даёт накопленное время в миллисекундах.
    # Отсчёт «времени исследования» стартует в момент ПЕРВОГО попадания мыши
    # в любую из областей (tstart = текущая позиция видео в мс).
    #
    # Все вспомогательные функции объявлены ВНУТРИ analyze_video: так они
    # через замыкание видят его переменные (nonlocal), а флаг выхода из
    # обработчика мыши передаётся как изменяемый список exit_requested.
    # -------------------------------------------------------------------------
    def analyze_video(self, video_path, record_video):
        """Анализ видео с оригинальной логикой таймера"""
        # Дополняет число ведущими нулями до длины n: zero(7, 5) -> '00007'.
        # Нужно для последовательных имён кадров frame00000.jpg, frame00001.jpg ...
        def zero(s, n):
            s = str(s)
            l = len(s)
            out = ''
            for i in range(n - l):
                out += '0'
            out += s
            return out

        # Используем nonlocal для доступа к переменным из внешней функции
        # Состояние анализа, общее для всех вложенных функций:
        #   Flag1 / Flag2       — заданы ли области 1 и 2;
        #   (x1,y1) / (x2,y2)   — их центры в пикселях кадра;
        #   Pause               — видео на паузе (стартуем именно с паузы!);
        #   img                 — текущий кадр с обводкой (нужен обработчику мыши
        #                        для размеров окна);
        #   exit_requested      — список из одного bool: изменяемый объект,
        #                        через который callback мыши сообщает о выходе;
        #   research_time_str   — время исследования в виде «мм:сс»;
        #   display_img         — кадр со ВСЕЙ отрисовкой, который показываем
        #                        и (при записи) сохраняем на диск;
        #   frames_saved        — счётчик реально записанных кадров;
        #   radius_area1 / 2    — радиусы областей, начальное значение 15.
        # Начальные значения согласованы с положением ползунков (см. ниже).
        Flag1 = False
        Flag2 = False
        x1, y1, x2, y2 = 0, 0, 0, 0
        Pause = True  # Начинаем с паузы - видео не воспроизводится
        img = None
        exit_requested = [False]
        research_time_str = "00:00"
        display_img = None  # Переменная для хранения изображения для отображения
        frames_saved = 0  # Счетчик сохраненных кадров
        radius_area1 = 15  # Начальный радиус области 1
        radius_area2 = 15  # Начальный радиус области 2

        # ПОИСК «НОСА» И «ХВОСТА» по форме контура.
        # M — моменты контура cv2.moments(cnt); центр тяжести равен
        # (m10/m00, m01/m00). Каждую точку контура переводим в пару
        # (угол 0..360°, расстояние до центра). Затем:
        #   j — самая дальняя точка от центра;
        #   k — вторая самая дальняя, но отстоящая от j по углу не меньше
        #       alpha=50° (иначе это просто соседние точки того же «конца»).
        # Получаем два противоположных конца тела мыши. Окно «kek» — отладочный
        # график «угол — расстояние» с отмеченными точками j и k.
        # ВНИМАНИЕ: при пустом контуре m00 = 0 и будет деление на ноль;
        # такой случай здесь не обрабатывается (видео предполагается корректным).
        def polar(cnt, M):
            # Центр тяжести контура (моменты первого порядка / площадь).
            x = int(M['m10']/M['m00'])
            y = int(M['m01']/M['m00'])
            a = []
            for i in cnt:
                X = i[0][0] - x
                Y = i[0][1] - y
                angle = int(m.degrees(m.atan2(Y, X) + m.pi))
                dist = int(m.hypot(Y, X))
                a.append((angle, dist))
            # Холст 360x360 для отладочного полярного профиля: по X — угол,
            # по Y — расстояние. Линии соединяют соседние точки контура.
            kek = np.zeros((360,360,3), np.uint8)
            Max = a[0][1]
            j = 0
            for i in range(1, len(a)):
                cv2.line(kek, (a[i - 1][0], a[i - 1][1]), (a[i][0], a[i][1]),(i%256,255,i%256),1)
                if a[i][1] > Max:
                    j = i
                Max = max(Max, a[i][1])
            # Минимальная угловая разница (в градусах) между двумя «концами»:
            # защита от выбора двух соседних точек одного и того же выступа.
            # Условие учитывает «переход через 0°» (x1_local - x2_local + 360).
            alpha = 50
            k = 0
            Max2 = 0
            for i in range(0, len(a)):
                x1_local = min(a[i][0], a[j][0])
                x2_local = max(a[i][0], a[j][0])
                if not (x2_local - x1_local < alpha or x1_local - x2_local + 360 < alpha):
                    if a[i][1] > Max2:
                        k = i
                    Max2 = max(Max2, a[i][1])
                    
            cv2.circle(kek, (a[j][0], a[j][1]), 15, (0,0,255), 1)
            cv2.circle(kek, (a[k][0], a[k][1]), 15, (0,0,255), 1)        
            # Показываем отладочный график в отдельном окне OpenCV «kek».
            # Возвращаем координаты двух крайних точек уже в пикселях кадра —
            # именно их потом проверяют minDist1/minDist2 на попадание в области.
            cv2.imshow("kek", kek)
            return [(cnt[j][0][0], cnt[j][0][1]), (cnt[k][0][0], cnt[k][0][1])]
            
        # ВЫДЕЛЕНИЕ КОНТУРА МЫШИ на кадре.
        # Ползунок 'Threshold' (0..100) задаёт границу яркости: серый кадр
        # выравнивается по гистограмме (equalizeHist), пиксели в диапазоне
        # [0; th] считаются тёмным объектом (мышью), всё остальное отсекается
        # маской inRange + bitwise_and. Затем findContours ищет границы.
        # Из всех контуров выбирается ВТОРОЙ по площади: предполагается, что
        # первый (самый большой) — это арена/фон, а мышь — следующий за ним.
        # Выбранный контур обводится зелёным прямо на кадре.
        # Возвращает (кадр с обводкой, сам контур).
        def contour(img):
            th = cv2.getTrackbarPos('Threshold','res')
            imgr = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            imge = cv2.equalizeHist(imgr)
            mask = cv2.inRange(imge, np.array([0]), np.array([th]))
            res = cv2.bitwise_and(img, img, mask= mask)
            imgray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)
            ret,thresh = cv2.threshold(imgray,0,100,1)
            contours, hierarchy = cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
            first = second = 0
            a = 0
            b = 0
            for i in range(len(contours)):
                area = cv2.contourArea(contours[i])
                if area >= a:
                    b = a
                    a = area
                    second = first
                    first = i
                elif area >= b:
                    b = area
                    second = i
            cv2.drawContours(img, contours, second, (0,255,0), 1)
            return img, contours[second]

        # Вспомогательная функция: возвращает все пиксели внутри залитого
        # контура. В ТЕКУЩЕЙ ВЕРСИИ НЕ ВЫЗЫВАЕТСЯ — это остаток ранней
        # реализации, оставленный в коде.
        def incontour(cnt, frame):
            img = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            mask = np.zeros(img.shape,np.uint8)
            cv2.drawContours(mask,[cnt],0,255,-1)
            pixelpoints = cv2.findNonZero(mask)
            return pixelpoints

        # Несмотря на имя параметра mask, сюда передаётся coord — список ИЗ ДВУХ
        # точек (нос и хвост), полученный из polar(). Функция перебирает их и
        # возвращает (ближайшая к центру области 1 точка, расстояние до неё).
        # Именно это расстояние в пикселях сравнивается с радиусом области.
        def minDist1(mask):
            nonlocal x1, y1
            d = 10**9
            ID = 0
            for i in mask:
                d1 = (i[0] - x1)**2 + (i[1] - y1)**2
                if d1 <= d:
                    d = d1
                    ID = (i[0], i[1])
            return ID, m.sqrt(d)

        # То же самое для области 2 с центром (x2, y2).
        def minDist2(mask):
            nonlocal x2, y2
            d = 10**9
            ID = 0
            for i in mask:
                d1 = (i[0] - x2)**2 + (i[1] - y2)**2
                if d1 <= d:
                    d = d1
                    ID = (i[0], i[1])
            return ID, m.sqrt(d)
                
        # ОБРАБОТЧИК МЫШИ окна 'res' (регистрируется через setMouseCallback).
        # nonlocal нужен, потому что мы меняем переменные внешней функции.
        # Зоны кнопок заданы с запасом: START/PAUSE рисуется шириной 175 px,
        # а клик принимается при x <= 200; EXIT — при x >= ширина - 200.
        # Проверка «не в зоне кнопки» при двойном клике не даёт случайно
        # поставить область вместо нажатия START.
        def retpos(event, x, y, flags, param):
            nonlocal Flag1, Flag2, x1, y1, x2, y2, Pause, img, radius_area1, radius_area2
            if img is None:
                return
                
            h, w = img.shape[:2]
            
            # Одинарный ЛКМ: левый нижний угол — переключаем паузу/воспроизведение,
            # правый нижний угол — выставляем флаг выхода (EXIT).
            if event == cv2.EVENT_LBUTTONDOWN:
                # Проверяем, кликнули ли на кнопку START/PAUSE (левый нижний угол)
                if x <= 200 and y >= h - 100:
                    Pause = not Pause  # Переключаем состояние
                    # Внутри обработчика мыши: после переключения Pause просто печатаем
                    # в консоль новое состояние (на паузе / воспроизводится). Это НЕ
                    # главный цикл анализа.
                    if Pause:
                        print("Видео на паузе")
                    else:
                        print("Видео воспроизводится")
                # Проверяем, кликнули ли на кнопку EXIT (правый нижний угол)
                elif x >= w - 200 and y >= h - 100:
                    print("Завершение по кнопке EXIT")
                    exit_requested[0] = True
                    
            # Двойной ЛКМ запоминает центр области 1 (синий круг в BGR).
            if event == cv2.EVENT_LBUTTONDBLCLK:
                if not (x <= 175 and y >= h - 90):
                    Flag1 = True
                    x1, y1 = x, y
                    print(f"Установлена область 1 в ({x1}, {y1}) с радиусом {radius_area1}")
                    
            # Двойной ПКМ запоминает центр области 2 (зелёный круг в BGR).
            if event == cv2.EVENT_RBUTTONDBLCLK:
                if not (x <= 175 and y >= h - 90):
                    Flag2 = True
                    x2, y2 = x, y
                    print(f"Установлена область 2 в ({x2}, {y2}) с радиусом {radius_area2}")

        # Пустая функция-обработчик для ползунка 'Threshold': его значение
        # не сохраняем, код сам опрашивает cv2.getTrackbarPos() в цикле.
        def nothing(x):
            pass

        # Ползунок «Radius Area 1» (0..100) сразу меняет радиус области 1.
        def update_radius_area1(x):
            """Обработчик изменения радиуса области 1"""
            nonlocal radius_area1
            radius_area1 = x
            print(f"Радиус области 1 изменен на: {radius_area1}")

        # Ползунок «Radius Area 2» (0..100) сразу меняет радиус области 2.
        def update_radius_area2(x):
            """Обработчик изменения радиуса области 2"""
            nonlocal radius_area2
            radius_area2 = x
            print(f"Радиус области 2 изменен на: {radius_area2}")

        # Рисует поверх КОПИИ кадра две «кнопки» (обычные прямоугольники и
        # текст OpenCV) внизу окна: слева START (зелёный, когда на паузе) или
        # PAUSE (жёлтый, когда видео идёт), справа EXIT. Нажатия по этим зонам
        # разбирает retpos(). Используется шрифт font из внешней функции.
        # Все цвета заданы в формате BGR, а не RGB.
        def draw_control_buttons(img, is_paused):
            """Рисуем кнопки управления внизу экрана"""
            h, w = img.shape[:2]
            
            # Создаем временную копию для рисования поверх
            result = img.copy()
            
            # Кнопка START/PAUSE слева
            cv2.rectangle(result, (0, h), (175, h - 90), (30, 30, 30), -1)
            if is_paused:
                text = "START"
                cv2.putText(result, text, (20, h - 35), font, 2, (0, 255, 0), 2)  # Зеленый для START
            else:
                text = "PAUSE"
                cv2.putText(result, text, (20, h - 35), font, 2, (255, 200, 0), 2)  # Желтый для PAUSE
            
            # Кнопка EXIT справа
            cv2.rectangle(result, (w - 175, h), (w, h - 90), (60, 30, 30), -1)
            cv2.putText(result, "EXIT", (w - 160, h - 35), font, 2, (255, 100, 100), 2)
            
            return result

        # Основной код анализа
        # Локальные псевдонимы аргументов и подготовка места для результатов.
        VideoName = video_path
        RECORD = record_video
        
        # Создаем папку для записи если нужно
        output_folder = None
        # Если запись включена: создаём папку «Анализ_ГГГГ-ММ-ДД_ЧЧ-ММ-СС»
        # рядом с видео (имя без двоеточий — безопасно для Windows), проверяем
        # право на запись тестовым файлом и удаляем его. При неудаче пробуем
        # ~/Desktop; если и там не вышло — output_folder = None, кадры не пишем.
        # Без записи output_folder просто указывает на папку видео (нужна только
        # для поля 'folder' в итоговом словаре).
        if RECORD:
            # Создаем безопасное имя папки для Windows
            now = datetime.datetime.now()
            # Формат: YYYY-MM-DD_HH-MM-SS
            Name = now.strftime("%Y-%m-%d_%H-%M-%S")
            
            # Сначала пытаемся писать туда же, где лежит исходное видео.
            # Пробуем создать папку рядом с видеофайлом
            video_dir = os.path.dirname(video_path) if os.path.dirname(video_path) else "."
            output_folder = os.path.join(video_dir, f"Анализ_{Name}")
            
            try:
                os.makedirs(output_folder, exist_ok=True)
                print(f'✓ Папка создана: {output_folder}')
                
                # Проверяем доступ на запись
                test_file = os.path.join(output_folder, "test_write.txt")
                try:
                    with open(test_file, 'w') as f:
                        f.write("Тест записи")
                    os.remove(test_file)
                    print("✓ Доступ на запись есть")
                except Exception as e:
                    print(f"✗ Нет доступа на запись в папку: {e}")
                    # Пробуем создать на рабочем столе
                    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                    output_folder = os.path.join(desktop, f"Анализ_{Name}")
                    try:
                        os.makedirs(output_folder, exist_ok=True)
                        print(f'✓ Папка создана на рабочем столе: {output_folder}')
                    except Exception as e2:
                        print(f'✗ Не удалось создать папку на рабочем столе: {e2}')
                        output_folder = None
            except Exception as e:
                print(f'✗ Не удалось создать папку: {e}')
                output_folder = None
        else:
            # Используем текущую директорию для сохранения результатов
            output_folder = os.path.dirname(video_path) if os.path.dirname(video_path) else "."
        
        # Открываем видеопоток. Если OpenCV не смог — показываем ошибку и
        # возвращаем None (тогда окно сохранения результата не появится).
        cap = cv2.VideoCapture(VideoName)
        if not cap.isOpened():
            QMessageBox.critical(None, "Ошибка", f"Не удалось открыть видеофайл: {VideoName}")
            return None
        
        # F   — всего кадров в видео;
        # FPS — кадров в секунду, НО сразу делится на 1000 и превращается в
        #       «кадров в миллисекунду». Благодаря этому nframe / FPS = мс.
        # Вывод «Длительность видео: F/FPS» фактически даёт МИЛЛИСЕКУНДЫ,
        # хотя подписан как секунды — небольшая неточность только в тексте консоли.
        F = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        FPS = cap.get(cv2.CAP_PROP_FPS)
        if FPS > 0:
            FPS = FPS / 1000  # Конвертируем в миллисекунды
        
        # Главное окно OpenCV 'res'. В него добавляются три ползунка:
        #   Threshold      — порог яркости для выделения мыши (0..100, старт 15);
        #   Radius Area 1  — радиус области 1 (0..100, старт 15);
        #   Radius Area 2  — радиус области 2 (0..100, старт 15).
        cv2.namedWindow('res')
        # Создаем трекбары для порога и радиусов областей
        cv2.createTrackbar('Threshold', 'res', 15, 100, nothing)
        cv2.createTrackbar('Radius Area 1', 'res', 15, 100, update_radius_area1)  # От 0 до 100, начальное 15
        cv2.createTrackbar('Radius Area 2', 'res', 15, 100, update_radius_area2)  # От 0 до 100, начальное 15
        # Привязываем обработчик кликов/двойных кликов к окну 'res'.
        cv2.setMouseCallback('res', retpos)

        print(f"Длительность видео: {F/FPS if FPS > 0 else 0:.2f} секунд")
        # Памятка по управлению печатается в КОНСОЛЬ (в окне её нет): кнопки
        # START/EXIT, двойные клики, ползунки и клавиши p/s/n/r/q/ESC.
        print("\nУправление:")
        print("- ЛКМ на кнопку START (слева): начать/приостановить видео")
        print("- ЛКМ на кнопку EXIT (справа): завершить анализ")
        print("- Двойной ЛКМ: установить область 1 (синий круг)")
        print("- Двойной ПКМ: установить область 2 (зеленый круг)")
        print("- Трекбар 'Threshold': настройка порога обнаружения мыши")
        print("- Трекбар 'Radius Area 1': настройка радиуса области 1 (0-100)")
        print("- Трекбар 'Radius Area 2': настройка радиуса области 2 (0-100)")
        print("- p: пауза")
        print("- s: продолжить (при паузе)")
        print("- n: сбросить области")
        print("- r: показать текущее время в областях")
        print("- q/ESC: выход\n")
        
        # Счётчики и флаги основного цикла:
        #   nframe1 / nframe2 — число кадров, когда мышь была в области 1 / 2
        #                       (далее переводится в миллисекунды);
        #   n                 — порядковый номер кадра для имени файла;
        #   name + font       — префикс 'frame' и шрифт для cv2.putText;
        #   FlagTime          — мышь хотя бы раз зашла в область;
        #   Once              — отсчёт времени исследования ещё НЕ начат;
        #   past / present    — прошлое и текущее значения ползунка Threshold
        #                       (чтобы на паузе пересчитывать контур только
        #                       при реальном изменении);
        #   onlyOne           — чтобы служебная печать «через 3 минуты»
        #                       сработала ровно один раз;
        #   tstart            — позиция видео (мс) в момент первого контакта.
        #   ret               — признак успешного чтения кадра.
        nframe1 = 0
        nframe2 = 0
        n = 0
        name = 'frame'
        font = cv2.FONT_HERSHEY_PLAIN
        FlagTime = False
        Once = True
        ret = True
        past = 15
        present = 15
        onlyOne = 0
        tstart = 0  # Время начала исследования
        
        # До старта цикла читаем и показываем ПЕРВЫЙ кадр: пользователь видит
        # картинку, может настроить порог и расставить области, и лишь затем
        # жмёт START (или клавишу s). Видео при этом не прокручивается.
        # Сначала показываем первый кадр на паузе
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return None
            
        # «Чистая» копия последнего показанного кадра. На паузе, когда меняется
        # Threshold, контур пересчитывается именно по ней, а не по уже
        # разрисованному изображению.
        backframe = copy.copy(frame)
        # contour() вернула кадр с обводкой и контур; cv2.moments(cnt) даёт
        # моменты, а polar() превращает контур в две точки — nose/tail (coord).
        img, cnt = contour(frame)
        coord = polar(cnt, cv2.moments(cnt))
        
        # Создаем изображение для отображения
        display_img = img.copy()
        
        # Отрисовка поверх копии кадра (чтобы не портить исходный img):
        #   красная и синяя точки  — две крайние точки мыши;
        #   синий/зелёный текст    — накопленное время в области 1 / 2 (мс);
        #   жёлтый текст           — таймер исследования;
        #   R1 / R2                — текущие радиусы областей;
        #   кнопки START и EXIT    — прямоугольники внизу окна.
        # Рисуем начальное состояние
        cv2.circle(display_img,coord[0], 2, (0,0,255), 2)
        cv2.circle(display_img,coord[1], 2, (255,0,0), 2)
        display_img = draw_control_buttons(display_img, Pause)
        cv2.putText(display_img,str(int(nframe1/FPS)) + 'ms',(10,100), font, 4,(255,0,0),2)
        cv2.putText(display_img,str(int(nframe2/FPS)) + 'ms',(10,150), font, 4,(0,255,0),2)
        cv2.putText(display_img, "00:00", (400,100), font, 4,(0,255,255),2)  # Сдвинуто влево
        # Отображение текущих радиусов
        cv2.putText(display_img, f"R1:{radius_area1}", (10, 200), font, 2, (255, 0, 0), 2)
        cv2.putText(display_img, f"R2:{radius_area2}", (10, 230), font, 2, (0, 255, 0), 2)
        cv2.imshow('res', display_img)
        
        # Ждем нажатия START
        print("Нажмите кнопку START для начала анализа...")
        
        # ГЛАВНЫЙ ЦИКЛ. Две ветви:
        #   Pause == True  — кадр не меняется, можно настраивать порог, ставить
        #                    области и радиусы (идёт только перерисовка);
        #   Pause == False — читается следующий кадр и ведётся подсчёт времени.
        # Выход из цикла: кнопка EXIT, клавиши q/ESC или конец видео.
        # cv2.waitKey(30) задаёт паузу ~30 мс между кадрами и одновременно
        # принимает нажатия клавиш (реальная скорость показа не равна FPS видео,
        # но время считается по metadata FPS, а не по настенным часам).
        while(cap.isOpened()):
            # Проверяем флаг выхода
            # Флаг выставляется из retpos() при клике по кнопке EXIT.
            # Список используется вместо nonlocal, чтобы изменять значение
            # из вложенной функции-обработчика.
            if exit_requested[0]:
                print("Завершение по кнопке EXIT")
                break
                
            # ---- ВЕТВЬ ПАУЗЫ ГЛАВНОГО ЦИКЛА -------------------------------
            # Видео НЕ перематывается. Если сдвинули ползунок Threshold —
            # пересчитываем контур по backframe; иначе просто перерисовываем
            # графику на копии (например, после двойного клика или смены радиуса).
            if Pause:
                # Режим паузы
                present = cv2.getTrackbarPos('Threshold','res')
                # Порог изменился: повторяем contour()+polar() для того же кадра,
                # затем заново рисуем точки, линии, окружности и запоминаем
                # новое значение (past = present).
                if present != past:
                    # Если изменился трекбар, пересчитываем контуры
                    newframe = copy.copy(backframe)
                    img, cnt = contour(newframe)
                    coord = polar(cnt, cv2.moments(cnt))
                    
                    # Создаем новое изображение для отображения
                    display_img = img.copy()
                    
                    # Восстанавливаем все элементы
                    cv2.circle(display_img,coord[0], 2, (0,0,255), 2)
                    cv2.circle(display_img,coord[1], 2, (255,0,0), 2)
                    
                    if Flag1:
                        position, d1 = minDist1(coord)
                        # Линия от центра области к ближайшей точке мыши + окружность
                        # заданного радиуса. На паузе это только подсказка, счётчик
                        # времени здесь НЕ увеличивается.
                        cv2.line(display_img,(x1,y1), position,(0,0,255),1)
                        cv2.circle(display_img,(x1,y1), radius_area1, (255,0,0), 1)
                    if Flag2:
                        position, d2 = minDist2(coord)
                        cv2.line(display_img,(x2,y2), position,(0,0,255),1)
                        cv2.circle(display_img,(x2,y2), radius_area2, (0,255,0), 1)
                    
                    past = present
                else:
                    # Если трекбар не изменился, создаем копию изображения для рисования
                    display_img = img.copy()
                    
                    # Рисуем текущие элементы поверх
                    cv2.circle(display_img,coord[0], 2, (0,0,255), 2)
                    cv2.circle(display_img,coord[1], 2, (255,0,0), 2)
                    
                    if Flag1:
                        position, d1 = minDist1(coord)
                        cv2.line(display_img,(x1,y1), position,(0,0,255),1)
                        cv2.circle(display_img,(x1,y1), radius_area1, (255,0,0), 1)
                    if Flag2:
                        position, d2 = minDist2(coord)
                        cv2.line(display_img,(x2,y2), position,(0,0,255),1)
                        cv2.circle(display_img,(x2,y2), radius_area2, (0,255,0), 1)
                
                # Общая часть для обеих ветвей паузы: кнопки, счётчики времени,
                # таймер исследования и подписи радиусов.
                # Рисуем кнопки и текст поверх чистой копии
                display_img = draw_control_buttons(display_img, Pause)
                cv2.putText(display_img,str(int(nframe1/FPS)) + 'ms',(10,100), font, 4,(255,0,0),2)
                cv2.putText(display_img,str(int(nframe2/FPS)) + 'ms',(10,150), font, 4,(0,255,0),2)
                
                # cap.get(0) — это CAP_PROP_POS_MSEC: текущая позиция в видео в мс.
                # Разность (позиция - tstart) / 1000 даёт прошедшие секунды/минуты.
                # В ветви паузы формат собирается без ведущих нулей (например 2:7),
                # а в ветви воспроизведения — как мм:сс с ведущими нулями.
                # Таймер исследования (желтый текст справа) - СДВИНУТ ВЛЕВО
                if not Once:
                    research_time_str = str(int((cap.get(0) - tstart)/1000/60%60)) + ":" + str(int((cap.get(0) - tstart)/1000%60))
                    cv2.putText(display_img, research_time_str, (400,100), font, 4,(0,255,255),2)  # Сдвинуто влево
                else:
                    research_time_str = "00:00"
                    cv2.putText(display_img, research_time_str, (400,100), font, 4,(0,255,255),2)  # Сдвинуто влево
                
                # Отображение текущих радиусов
                cv2.putText(display_img, f"R1:{radius_area1}", (10, 200), font, 2, (255, 0, 0), 2)
                cv2.putText(display_img, f"R2:{radius_area2}", (10, 230), font, 2, (0, 255, 0), 2)
                
                cv2.imshow('res', display_img)

                # Клавиши НА ПАУЗЕ: s — продолжить, n — полный сброс областей и
                # счётчиков, r — вывести текущие времена в консоль, q/ESC — выход.
                k = cv2.waitKey(30) & 0xff
                if k == ord('s'):  # клавиша 's' для продолжения
                    Pause = False
                    print("Видео возобновлено (клавиша s)")
                # Полный сброс: области, таймер и накопленные кадры обнуляются,
                # как будто анализ начинается заново на том же видео.
                if k == ord('n'):
                    Flag1 = Flag2 = FlagTime = False
                    Once = True
                    x1 = x2 = y1 = y2 = 0
                    nframe1 = nframe2 = 0
                    onlyOne = 0
                    print("Области сброшены")
                    
                if k == ord('r'):
                    print('Time 1 is ' + str(int(nframe1/FPS)) + 'ms')
                    print('Time 2 is ' + str(int(nframe2/FPS)) + 'ms')
                if k == 27 or k == ord('q'): 
                    print("Выход по запросу пользователя")
                    break
                
            else:
                # ---- ВЕТВЬ ВОСПРОИЗВЕДЕНИЯ --------------------------------------
                # Читаем следующий кадр. ret == False означает конец видео — выход.
                # Затем снова ищем контур и две точки мыши.
                # Режим воспроизведения
                ret, frame = cap.read()
                if not ret:
                    break
                    
                backframe = copy.copy(frame)
                # Тот же пайплайн для очередного кадра при воспроизведении.
                img, cnt = contour(frame)
                coord = polar(cnt, cv2.moments(cnt))
                
                # Создаем изображение для отображения
                display_img = img.copy()
                
                cv2.circle(display_img,coord[0], 2, (0,0,255), 2)
                cv2.circle(display_img,coord[1], 2, (255,0,0), 2)
                
                if Flag1:
                    position, d1 = minDist1(coord)
                    # Для КАЖДОЙ заданной области: находим ближайшую из двух точек
                    # мыши, рисуем линию и окружность радиуса R; если расстояние
                    # меньше радиуса — считаем, что мышь у образца, и добавляем
                    # +1 к счётчику кадров этой области (FlagTime тоже взводится).
                    # Отладочная печать делается раз в 10 кадров, чтобы не засорять консоль.
                    cv2.line(display_img,(x1,y1), position,(0,0,255),1)
                    cv2.circle(display_img,(x1,y1), radius_area1, (255,0,0), 1)
                    if d1 < radius_area1:  # Используем текущий радиус для проверки
                        FlagTime = True
                        nframe1 += 1
                        # Показываем сообщение при попадании (для отладки)
                        if nframe1 % 10 == 0:  # Каждые 10 кадров
                            print(f"Мышь в области 1 (расстояние: {d1:.1f}, радиус: {radius_area1})")
                        
                if Flag2:
                    position, d2 = minDist2(coord)
                    cv2.line(display_img,(x2,y2), position,(0,0,255),1)
                    cv2.circle(display_img,(x2,y2), radius_area2, (0,255,0), 1)
                    if d2 < radius_area2:  # Используем текущий радиус для проверки
                        FlagTime = True
                        nframe2 += 1
                        # Показываем сообщение при попадании (для отладки)
                        if nframe2 % 10 == 0:  # Каждые 10 кадров
                            print(f"Мышь в области 2 (расстояние: {d2:.1f}, радиус: {radius_area2})")
                
                # ПЕРВОЕ попадание в любую область фиксирует tstart — момент
                # начала «исследования». Флаг Once не даёт перезаписать его
                # при последующих попаданиях.
                # Устанавливаем время начала исследования при первом попадании в область
                if FlagTime and Once:
                    tstart = cap.get(0)
                    Once = False
                    print(f"Исследование начато в {tstart} мс")
                
                # Рисуем кнопки управления
                display_img = draw_control_buttons(display_img, Pause)
                     
                cv2.putText(display_img,str(int(nframe1/FPS)) + 'ms',(10,100), font, 4,(255,0,0),2)
                cv2.putText(display_img,str(int(nframe2/FPS)) + 'ms',(10,150), font, 4,(0,255,0),2)
                
                # Таймер мм:сс (с ведущими нулями). Ровно на 180-й секунде один раз
                # (onlyOne) в консоль выводятся промежуточные значения счётчиков —
                # служебная метка, унаследованная от исходного алгоритма.
                # Таймер исследования (желтый текст справа) - СДВИНУТ ВЛЕВО
                if not Once:
                    # Форматирование времени как в оригинальном коде
                    minutes = int((cap.get(0) - tstart)/1000/60%60)
                    seconds = int((cap.get(0) - tstart)/1000%60)
                    research_time_str = f"{minutes:02d}:{seconds:02d}"
                    cv2.putText(display_img, research_time_str, (400,100), font, 4,(0,255,255),2)  # Сдвинуто влево

                    # Автоматический вывод через 3 минуты как в оригинале
                    if int((cap.get(0) - tstart)/1000) == 180 and onlyOne == 0:
                        print('Time 1 after 3 min is =' + str(int(nframe1/FPS)) + 'ms')
                        print('Time 2 after 3 min is =' + str(int(nframe2/FPS)) + 'ms')
                        onlyOne = 1
                else:
                    research_time_str = "00:00"
                    cv2.putText(display_img, research_time_str, (400,100), font, 4,(0,255,255),2)  # Сдвинуто влево
                
                # Отображение текущих радиусов
                cv2.putText(display_img, f"R1:{radius_area1}", (10, 200), font, 2, (255, 0, 0), 2)
                cv2.putText(display_img, f"R2:{radius_area2}", (10, 230), font, 2, (0, 255, 0), 2)
                    
                cv2.imshow('res', display_img)
                
                # Запись кадра: zero(n, 5) даёт frame00000.jpg, frame00001.jpg ...
                # Сохраняется display_img — УЖЕ РАЗРИСОВАННЫЙ кадр (контур, точки,
                # круги, кнопки, таймеры), JPEG с качеством 95. Ошибки записи
                # перехватываются, чтобы не прервать сам анализ.
                # Сохраняем кадр если включена запись и папка создана
                if RECORD and output_folder and os.path.exists(output_folder):
                    try:
                        # Формируем имя файла
                        filename = f"{name}{zero(n, 5)}.jpg"
                        filepath = os.path.join(output_folder, filename)
                        
                        # Проверяем, что изображение валидно
                        if display_img is not None and display_img.size > 0:
                            # Пробуем сохранить с параметрами качества
                            success = cv2.imwrite(filepath, display_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            if success:
                                frames_saved += 1
                                # Выводим сообщение каждые 50 кадров
                                if frames_saved % 50 == 0:
                                    print(f"✓ Сохранен кадр {n} ({frames_saved} всего): {filename}")
                                    print(f"  Размер изображения: {display_img.shape}")
                                    print(f"  Путь: {filepath}")
                            else:
                                print(f"✗ Ошибка: cv2.imwrite вернул False для кадра {n}")
                        else:
                            print(f"✗ Пустое изображение для кадра {n}")
                    except Exception as e:
                        print(f"✗ Исключение при сохранении кадра {n}: {str(e)}")
                
                # Следующий номер кадра для имени файла.
                n += 1
                
                # Клавиши ПРИ ВОСПРОИЗВЕДЕНИИ: p — пауза, n — сброс, r — печать
                # времён (с текущими радиусами), q/ESC — досрочный выход.
                k = cv2.waitKey(30) & 0xff
                if k == ord('p'):
                    Pause = True
                    print("Видео на паузе (клавиша p)")
                # Тот же полный сброс, что и на паузе.
                if k == ord('n'):
                    Flag1 = Flag2 = FlagTime = False
                    Once = True
                    x1 = x2 = y1 = y2 = 0
                    nframe1 = nframe2 = 0
                    onlyOne = 0
                    print("Области сброшены")
                    
                if k == ord('r'):
                    print(f'Time 1 is = {int(nframe1/FPS)} ms (радиус области: {radius_area1})')
                    print(f'Time 2 is = {int(nframe2/FPS)} ms (радиус области: {radius_area2})')
                if k == 27 or k == ord('q'):
                    print("Выход по клавише ESC/q")
                    break
                    
        cap.release()
        # cap.release() выше освобождает видеозахват; destroyAllWindows()
        # закрывает оба окна OpenCV: основное 'res' и отладочное 'kek'.
        cv2.destroyAllWindows()

        # Итоговый отчёт в консоль: время в каждой области (мс), время
        # исследования, а при включённой записи — статистика по папке с кадрами
        # (обработано / сохранено / первый и последний файлы).
        print("\n" + "="*50)
        print("Анализ завершен!")
        print(f"Итоговое время в области 1: {int(nframe1/FPS) if FPS > 0 else 0} ms (радиус: {radius_area1})")
        print(f"Итоговое время в области 2: {int(nframe2/FPS) if FPS > 0 else 0} ms (радиус: {radius_area2})")
        print(f"Время исследования: {research_time_str}")
        
        if RECORD:
            if output_folder and os.path.exists(output_folder):
                try:
                    # Подсчитываем количество файлов в папке
                    files = [f for f in os.listdir(output_folder) if f.endswith(('.jpg', '.png'))]
                    print(f"✓ Всего кадров обработано: {n}")
                    print(f"✓ Кадров сохранено: {frames_saved}")
                    print(f"✓ В папке файлов: {len(files)}")
                    print(f"✓ Путь к папке: {output_folder}")
                    
                    if files:
                        print(f"✓ Первый файл: {sorted(files)[0]}")
                        print(f"✓ Последний файл: {sorted(files)[-1]}")
                    else:
                        print("✗ В папке нет файлов изображений")
                except Exception as e:
                    print(f"✗ Ошибка при проверке папки: {e}")
            else:
                print(f"✗ Папка не была создана или не существует: {output_folder}")
        
        print("="*50)
        
        # Словарь результатов, который попадает в save_results_to_file().
        # Ключи 'folder' и 'output_folder' дублируют друг друга (совместимость
        # с более ранними версиями программы). Радиусы и число кадров тоже
        # возвращаются, но в result.txt сейчас пишутся только 4 поля:
        # имя файла, время 1, время 2, время исследования.
        return {
            'video_file': os.path.basename(video_path),
            'time_area1': int(nframe1/FPS) if FPS > 0 else 0,
            'time_area2': int(nframe2/FPS) if FPS > 0 else 0,
            'research_time_str': research_time_str,
            'radius_area1': radius_area1,
            'radius_area2': radius_area2,
            'recorded_frames': frames_saved if RECORD else 0,
            'output_folder': output_folder,
            'folder': output_folder
        }


# Создаём приложение Qt, включаем единый стиль оформления Fusion, показываем
# главное окно и передаём управление циклу событий app.exec(). Выход из цикла
# (закрытие окна) завершает процесс через sys.exit().
def main():
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    analyzer = VideoAnalyzer()
    analyzer.show()
    
    sys.exit(app.exec())


# Срабатывает только при ПРЯМОМ запуске файла; при импорте как модуля
# окно не создаётся и приложение не стартует.
if __name__ == "__main__":
    main()