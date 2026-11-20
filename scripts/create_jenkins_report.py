#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path.cwd()
EVIDENCE = ROOT / "evidence"
SHOTS = EVIDENCE / "screenshots"
OUTPUT = EVIDENCE / "report.docx"
BLACK = RGBColor(0, 0, 0)
RUN_ID = os.environ.get("GITHUB_RUN_ID", "unknown")
REPO = "https://github.com/GDS7777/cicd-demo-app"
RUN_URL = f"{REPO}/actions/runs/{RUN_ID}"
JENKINSFILE_URL = f"{REPO}/blob/master/Jenkinsfile"

def read_text(name):
    path = EVIDENCE / name
    return path.read_text(encoding="utf-8") if path.exists() else ""

def set_run(run, size=12, bold=None, italic=None):
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic

doc = Document()
section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(2)
section.bottom_margin = Cm(2)
section.left_margin = Cm(2.5)
section.right_margin = Cm(2)

normal = doc.styles["Normal"]
normal.font.name = "Arial"
normal.font.size = Pt(12)
normal.font.color.rgb = BLACK
normal.paragraph_format.line_spacing = 1.15
normal.paragraph_format.space_after = Pt(6)
for style_name in ("Heading 1", "Heading 2", "Title", "Subtitle"):
    style = doc.styles[style_name]
    style.font.name = "Arial"
    style.font.color.rgb = BLACK
    style.font.bold = True
doc.styles["Heading 1"].font.size = Pt(14)
doc.styles["Heading 2"].font.size = Pt(12)

section.different_first_page_header_footer = True
section.first_page_header.paragraphs[0].text = ""
section.first_page_footer.paragraphs[0].text = ""
section.header.paragraphs[0].text = ""
footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
page_field = OxmlElement("w:fldSimple")
page_field.set(qn("w:instr"), "PAGE")
footer._p.append(page_field)

def paragraph(text="", bold=False, align=None, size=12, italic=False):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    set_run(r, size, bold, italic)
    return p

def heading(text):
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    set_run(r, 14, True)
    return p

def code(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    set_run(r, 9)
    return p

def image(name, caption, width=5.75):
    path = SHOTS / name
    if not path.exists():
        raise FileNotFoundError(f"Real screenshot is missing: {path}")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(6)
    set_run(cap.add_run(caption), 10, italic=True)

def new_page(title):
    doc.add_page_break()
    heading(title)

matrix = read_text("build-matrix.txt").strip()
buildinfo = read_text("build-info.txt").strip()
archive = read_text("archive-contents.txt").strip().splitlines()
environment = read_text("jenkins-agent-environment.txt").strip()
metadata = read_text("execution-metadata.txt").strip()
numbers_text = read_text("build-numbers.env")
build_numbers = dict(re.findall(r"(B[1-4])=(\d+)", numbers_text))
sha_by_build = {}
for key in ("B1", "B2", "B3", "B4"):
    num = build_numbers.get(key, str(int(key[1:])))
    console = read_text(f"build-{num}-console.txt")
    found = re.findall(r"Commit SHA:\s*([0-9a-f]{40})", console)
    if found:
        sha_by_build[key] = found[-1]

# 1. Титульный лист
for line in (
    "МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ РОССИЙСКОЙ ФЕДЕРАЦИИ",
    "Федеральное государственное бюджетное образовательное учреждение высшего образования",
    "САМАРСКИЙ ГОСУДАРСТВЕННЫЙ ТЕХНИЧЕСКИЙ УНИВЕРСИТЕТ",
    "Кафедра «Информатика и вычислительная техника»",
):
    paragraph(line, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(42)
set_run(p.add_run("ОТЧЁТ"), 16, True)
paragraph("о выполнении лабораторной работы № 2", align=WD_ALIGN_PARAGRAPH.CENTER, size=13)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(12)
set_run(p.add_run("Создание CI/CD Pipeline в Jenkins"), 14, True)
paragraph("по дисциплине «Администрирование информационных систем»", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
for line in (
    "Проверяющий: Сидельников Александр Андреевич",
    "Проверяющий: Алексеев Дмитрий Валентинович",
    "Выполнил: Волков Сергей Николаевич",
):
    paragraph(line, align=WD_ALIGN_PARAGRAPH.RIGHT, size=12)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(46)
set_run(p.add_run("Самара, 07.11.2026"), 12)

# 2. Assignment and goal
new_page("1. Цель и содержание работы")
paragraph("Цель работы — настроить декларативный Jenkins Pipeline, который получает исходный код из заданного GitHub-репозитория и ветки, проверяет структуру проекта, при необходимости запускает unit-тесты, формирует архив app.tar.gz и сохраняет его как артефакт сборки.")
paragraph("В job добавлены параметры REPO_URL, GIT_BRANCH и RUN_TESTS. В отчёте проверены четыре сценария: успешная сборка master с тестами, успешная сборка master без тестов, ожидаемый отказ на ветке broken-tests и повторная успешная сборка master.")
paragraph("Работа выполнялась на облачном Ubuntu runner GitHub Actions. Внутри runner был запущен официальный контейнер Jenkins. Команды и сборки выполнены в этой изолированной среде; виртуальная машина на компьютере пользователя не использовалась.")
paragraph("Фактическая дата облачных запусков: 20.11.2026. Дата на титульном листе указана по просьбе автора отчёта.")
paragraph("Успешным считается результат, при котором все обязательные файлы найдены, тесты проходят или корректно пропущены, архив формируется и доступен со страницы сборки. При ошибке тестов последующие стадии Build и Archive должны быть пропущены.")

# 3. Environment
new_page("2. Среда выполнения")
paragraph("Внешний runner предоставил одноразовую виртуальную машину Ubuntu. В ней собран контейнер Jenkins LTS на JDK 21, установлены Git, Python 3 и tar. Pipeline запускался на Linux executor Jenkins, доступном внутри контейнера. После завершения GitHub Actions runner был удалён.")
if environment:
    paragraph("Зафиксированная информация об executor:")
    for line in environment.splitlines():
        if line.strip():
            code(line.strip())
if metadata:
    paragraph("Идентификатор и исходный commit облачного запуска:")
    for line in metadata.splitlines():
        if line.strip():
            code(line.strip())
paragraph("Jenkins API слушал только loopback-интерфейс облачного runner. Для автоматического запуска job в одноразовом стенде отключена проверка crumb; контроллер не публиковался наружу и не использовался как постоянный сервер.")

# 4. Fork
new_page("3. Fork и исходный код")
paragraph("В качестве основы использован Fork GDS7777/cicd-demo-app. В master сохранён Jenkinsfile с параметрами и стадиями задания. Ветка broken-tests создана от master и содержит одно намеренно неверное ожидаемое значение в тесте сложения.")
paragraph("Снимок показывает master ветку и файлы проекта, которые pipeline проверяет перед тестированием: README.md, requirements.txt, src/ и tests/.")
image("github-fork-master.png", "Рисунок 1. Страница Fork GDS7777/cicd-demo-app в GitHub")

# 5. broken branch
new_page("4. Подготовка ветки broken-tests")
paragraph("Ветка broken-tests нужна для проверки реакции pipeline на сбой unit-тестов. В ней изменено только ожидаемое значение одного assert: функция add(2, 3) возвращает 5, тогда как тест намеренно ожидает 6. Код приложения остаётся неизменным.")
paragraph("Такая правка создаёт воспроизводимый отказ на стадии Test. Ветку можно собрать отдельно через параметр GIT_BRANCH, не влияя на master.")
image("github-broken-tests-branch.png", "Рисунок 2. Ветка broken-tests в Fork")

# 6. Job parameters
new_page("5. Параметры Jenkins job")
paragraph("Создана Pipeline job JenkinsLab. Значение REPO_URL по умолчанию указывает на HTTPS URL Fork. GIT_BRANCH по умолчанию равен master. RUN_TESTS — логический параметр со значением по умолчанию true.")
paragraph("Job хранит Declarative Pipeline script, чтобы параметры текущего запуска применялись к checkout. Идентичный скрипт сохранён в корне Fork как Jenkinsfile. Настройки проверены в интерфейсе запущенного Jenkins.")
image("jenkins-job-parameters.png", "Рисунок 3. Параметризованная Jenkins job")

# 7. Pipeline
new_page("6. Структура Jenkinsfile")
paragraph("Jenkinsfile состоит из стадий Checkout, Validate, Test, Build и Archive. Checkout удаляет содержимое прежнего workspace, клонирует выбранную ветку и выводит полный SHA коммита. Validate проверяет наличие четырёх обязательных путей.")
paragraph("Стадия Test управляется условием when и параметром RUN_TESTS. В Build создаётся build-info.txt с номером Jenkins build и SHA, затем формируется app.tar.gz. Archive сохраняет архив как fingerprinted artifact. Блок post выводит отдельное сообщение для SUCCESS и FAILURE.")
paragraph("Следующий снимок показывает исходный Jenkinsfile, сохранённый в Fork. Полный файл доступен по ссылке в конце отчёта.")
image("github-jenkinsfile.png", "Рисунок 4. Jenkinsfile в ветке master")

# 8. Stage history
new_page("7. История сборок и стадии")
paragraph("После выполнения четырёх запусков Stage View показывает разные пути прохождения pipeline. В сборке № 2 стадия Test пропущена по условию. В сборке № 3 после отказа Test стадии Build и Archive пропущены. Сборки № 1 и № 4 завершаются успешно.")
image("jenkins-stage-history.png", "Рисунок 5. История запусков и состояния стадий в Jenkins")

# 9. Build 1
new_page("8. Сборка № 1. master, тесты включены")
paragraph("Первый запуск выполнен с GIT_BRANCH=master и RUN_TESTS=true. Pipeline получил код, напечатал ветку и SHA, проверил структуру проекта и запустил unittest discover. Все тесты завершились успешно, после чего архив был создан и сохранён.")
image("build-1-console.png", "Рисунок 6. Console Output первой сборки")
paragraph("Итог первой сборки: SUCCESS. Полный лог и статус включены в комплект облачных доказательств.")

# 10. Build 2
new_page("9. Сборка № 2. master, тесты отключены")
paragraph("Второй запуск использовал master и RUN_TESTS=false. Стадия Test пропущена по условию Declarative Pipeline, а остальные обязательные стадии продолжили выполнение. Архив создан и доступен среди Jenkins Artifacts.")
image("build-2-console.png", "Рисунок 7. Console Output сборки без запуска тестов")
paragraph("Итог второй сборки: SUCCESS. Проверено отсутствие остановки pipeline из-за отключённых тестов.")

# 11. Build 3
new_page("10. Сборка № 3. broken-tests")
paragraph("Третий запуск собрал ветку broken-tests с RUN_TESTS=true. Тест сложения завершился ошибкой, как и требовалось для проверки негативного сценария. Jenkins отметил build как FAILURE; стадии Build и Archive не выполнялись.")
image("build-3-console.png", "Рисунок 8. Ошибка unit-теста и остановка последующих стадий")
paragraph("Итог третьей сборки: ожидаемый FAILURE. Сообщение post-блока зафиксировано в Console Output.")

# 12. Build 4
new_page("11. Сборка № 4. Восстановление master")
paragraph("Четвёртый запуск повторно собрал master с RUN_TESTS=true. Это подтверждает, что изменение в broken-tests изолировано в отдельной ветке и не повредило основной код.")
image("build-4-console.png", "Рисунок 9. Успешный повторный запуск master")
paragraph("Итог четвёртой сборки: SUCCESS. Архив итоговой сборки скачан через Jenkins Artifact URL.")

# 13. Artifacts and build-info
new_page("12. Артефакты сборки")
paragraph("На странице артефактов итоговой сборки опубликован app.tar.gz. Архив содержит README.md, requirements.txt, каталог src/, каталог tests/, Jenkinsfile и build-info.txt.")
image("build-4-artifacts.png", "Рисунок 10. Артефакт app.tar.gz в Jenkins")
paragraph("Содержимое build-info.txt извлечено из реально скачанного app.tar.gz:")
for line in buildinfo.splitlines():
    if line.strip():
        code(line.strip())
paragraph(f"В архиве перечислено элементов: {len([x for x in archive if x.strip()])}.")

# 14. Commands and result table
new_page("13. Команды и контроль результатов")
paragraph("Скрипт облачного запуска собрал образ Jenkins, установил в Linux executor Python 3 и tar, запустил Jenkins, создал Pipeline job, передал параметры и проверил результаты четырёх сборок. Основные команды pipeline:")
for command in (
    "python3 -m unittest discover -s tests -v",
    "git rev-parse HEAD",
    "tar -czf app.tar.gz --exclude=.git README.md requirements.txt src tests Jenkinsfile build-info.txt",
    "tar -tzf app.tar.gz",
    "curl -X POST http://127.0.0.1:8080/job/JenkinsLab/buildWithParameters?...",
):
    code(command)
paragraph("Фактическая матрица запусков:")
for line in matrix.splitlines():
    if line.strip():
        code(line.strip())
paragraph("Полный исполняемый сценарий облачной подготовки сохранён как scripts/cloud_jenkins_lab.sh в Fork. Консольные логи всех четырёх Jenkins builds находятся в evidence.")

# 15. Conclusion and sources
new_page("14. Выводы")
paragraph("Pipeline соответствует проверенным требованиям: принимает URL, ветку и Boolean-параметр; проверяет обязательную структуру; запускает тесты по условию; сообщает SHA коммита; создаёт и архивирует app.tar.gz с build-info.txt; завершает сборку со статусом, соответствующим результатам тестов.")
paragraph("Негативный сценарий воспроизведён намеренно и завершился ожидаемым FAILURE. Повторная сборка master завершилась SUCCESS. Скриншоты в отчёте сняты из фактически запущенного интерфейса Jenkins и GitHub в облачном runner; искусственно нарисованных скриншотов нет.")
paragraph("Материалы:")
for link in (
    REPO,
    JENKINSFILE_URL,
    f"{REPO}/tree/broken-tests",
    RUN_URL,
    "https://www.jenkins.io/doc/book/installing/docker/",
):
    paragraph(link, size=10)

doc.core_properties.title = "Создание CI/CD Pipeline в Jenkins"
doc.core_properties.subject = "Практическая работа № 2"
doc.core_properties.author = "GDS7777"
doc.save(OUTPUT)
print(f"Created {OUTPUT} with 15 explicit report sections.")
