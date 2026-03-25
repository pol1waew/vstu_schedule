import json
from datetime import datetime

from django.test import TestCase

from apps.common.models import (
    AbstractDay,
    AbstractEvent,
    Department,
    Event,
    EventKind,
    EventParticipant,
    EventPlace,
    Organization,
    Schedule,
    ScheduleMetadata,
    ScheduleTemplate,
    ScheduleTemplateMetadata,
    Subject,
    TimeSlot,
)
from apps.common.services.timetable.load.reference_importer import ReferenceImporter
from apps.common.services.timetable.read.filters import (
    PlaceFilter,
    TimeSlotFilter,
)
from apps.common.services.timetable.utilities.model_helpers import (
    create_common_abstract_days,
    create_common_time_slots,
)

"""python manage.py test apps.common.tests.test_reference_import
"""


class TestReferenceImporter(TestCase):
    def test_place_import_reference(self):
        PLACE_REFERENCE_DATA = """
            {
                "places": [
                    "002",
                    "КЦ УНЦ",
                    "В-1402-3",
                    "Б-205а",
                    "ГУК101"
                ]
            }
        """

        ReferenceImporter.import_place_reference(PLACE_REFERENCE_DATA)

        try:
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_building_and_room("002")), None)
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_building_and_room("КЦ УНЦ")), None)
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_building_and_room("В-1402-3")), None)
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_building_and_room("Б-205а")), None)
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_building_and_room("ГУК101")), None)
        except EventPlace.DoesNotExist:
            self.fail()

    def test_import_same_place_reference(self):
        PLACE_REFERENCE_DATA = """
            {
                "places": [
                    "В-902а",
                    "В 902а",
                    "В,902а"
                ]
            }
        """

        ReferenceImporter.import_place_reference(PLACE_REFERENCE_DATA)

        try:
            self.assertEqual(EventPlace.objects.all().count(), 1)
            self.assertNotEqual(EventPlace.objects.get(building="В", room="902а"), None)
        except EventPlace.DoesNotExist:
            self.fail()
    
    def test_import_duplicate_place_reference(self):
        PLACE_REFERENCE_DATA = """
            {
                "places": [
                    "002",
                    "002",
                    "КЦ УНЦ",
                    "В-1402-3",
                    "Б-205а",
                    "ГУК101"
                ]
            }
        """

        ReferenceImporter.import_place_reference(PLACE_REFERENCE_DATA)
        ReferenceImporter.import_place_reference(PLACE_REFERENCE_DATA)

        try:
            self.assertEqual(EventPlace.objects.all().count(), 5)
        except EventPlace.DoesNotExist:
            self.fail()

    def test_faculty_import_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "0",
                    "faculty_fullname" : "Информационно-библиотечный центр",
                    "faculty_code" : "0000",
                    "faculty_shortname" : "ИБЦ"
                },
                {
                    "faculty_id" : "1",
                    "faculty_fullname" : "Факультет автоматизированных систем, транспорта и вооружений",
                    "faculty_code" : "0001",
                    "faculty_shortname" : "ФАСТиВ"
                },
                {
                    "faculty_id" : "2",
                    "faculty_fullname" : "Факультет автомобильного транспорта",
                    "faculty_code" : "0002",
                    "faculty_shortname" : "ФАТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)

        try:
            self.assertEqual(Department.objects.all().count(), 3)
            self.assertEqual(Department.objects.filter(parent_department__isnull=True).count(), 3)
            self.assertNotEqual(Department.objects.get(shortname="ФАСТиВ"), None)
            self.assertNotEqual(Department.objects.get(code="2"), None)
        except Department.DoesNotExist:
            self.fail()

    def test_faculty_import_duplicate_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "106",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000157",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "106",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000157",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)

        try:
            self.assertEqual(Department.objects.all().count(), 1)
        except Department.DoesNotExist:
            self.fail()

    def test_department_import_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "222",
                    "faculty_fullname" : "Химико-технологический факультет",
                    "faculty_code" : "000000222",
                    "faculty_shortname" : "ХТФ"
                }
            ]
        """
        DEPARTMENT_REFERENCE_DATA = """
            [
                {
                    "department_id" : "0",
                    "department_code" : "000000000",
                    "department_fullname" : "Кафедра Автоматизация производственных процессов",
                    "department_shortname" : "АПП",
                    "faculty_id" : "111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "department_id" : "1",
                    "department_code" : "000000001",
                    "department_fullname" : "Кафедра Автоматические установки",
                    "department_shortname" : "АУ",
                    "faculty_id" : "333",
                    "faculty_shortname" : "ТАКОГО ФАКУЛЬТЕТА НЕТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_department_reference(DEPARTMENT_REFERENCE_DATA)

        try:
            self.assertEqual(Department.objects.filter(parent_department__isnull=True).count(), 3) # 2 faculty + 1 department
            self.assertEqual(Department.objects.filter(parent_department__isnull=False).count(), 1)
            self.assertNotEqual(Department.objects.get(shortname="ФЭВТ"), None)
            self.assertNotEqual(Department.objects.get(parent_department__code="111"), None)
            self.assertEqual(Department.objects.get(code="000000001").name, "Кафедра Автоматические установки")
        except Department.DoesNotExist:
            self.fail()

    def test_department_import_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "106",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000157",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """
        DEPARTMENT_REFERENCE_DATA = """
            [
                {
                    "department_id" : "106",
                    "department_code" : "000000165",
                    "department_fullname" : "Кафедра Программное обеспечение автоматизированных систем",
                    "department_shortname" : "ПОАС",
                    "faculty_id" : "106",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "department_id" : "106",
                    "department_code" : "000000165",
                    "department_fullname" : "Кафедра Программное обеспечение автоматизированных систем",
                    "department_shortname" : "ПОАС",
                    "faculty_id" : "106",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_department_reference(DEPARTMENT_REFERENCE_DATA)
        ReferenceImporter.import_department_reference(DEPARTMENT_REFERENCE_DATA)

        try:
            self.assertEqual(Department.objects.filter(parent_department__isnull=False).count(), 1)
            self.assertEqual(Department.objects.filter(parent_department__isnull=True).count(), 1)
        except Department.DoesNotExist:
            self.fail()

    def test_subject_import_reference(self):
        SUBJECT_REFERENCE_DATA = """
        [
            {
                "discipline_code" : "000006700",
                "discipline_name" : "Динамика и устойчивость самоходного артиллерийского орудия",
                "discipline_shortname" : "ДИУСАО",
                "is_elective" : "Нет",
                "discipline_department_code" : "000000130",
                "discipline_department_id" : "2",
                "discipline_department_shortname" : "АУ"
            },
            {
                "discipline_code" : "000002373",
                "discipline_name" : "Основы проектирования WEB-приложений",
                "discipline_shortname" : "ОПW",
                "is_elective" : "Нет",
                "discipline_department_code" : "000000215",
                "discipline_department_id" : "210",
                "discipline_department_shortname" : "ВИТ"
            },
            {
                "discipline_code" : "000006579",
                "discipline_name" : "Экзамен по ПМ.05 'Организация деятельности подчиненного персонала'",
                "discipline_shortname" : "ЭПП'ДПП",
                "is_elective" : "Нет",
                "discipline_department_code" : "000000327",
                "discipline_department_id" : "329",
                "discipline_department_shortname" : "ТМ (КТИ)"
            }
        ]
        """

        ReferenceImporter.import_subject_reference(SUBJECT_REFERENCE_DATA)

        try:
            self.assertEqual(Subject.objects.all().count(), 3)
            self.assertNotEqual(Subject.objects.get(name="Основы проектирования WEB-приложений"), None)
            self.assertNotEqual(Subject.objects.get(name="Экзамен по ПМ.05 'Организация деятельности подчиненного персонала'"), None)
        except Subject.DoesNotExist:
            self.fail()

    def test_subject_import_duplicate_reference(self):
        SUBJECT_REFERENCE_DATA = """
        [
            {
                "discipline_code" : "0",
                "discipline_name" : "НАЗВАНИЕ ПРЕДМЕТА",
                "discipline_shortname" : "ЙЦУКЕН",
                "is_elective" : "Нет",
                "discipline_department_code" : "1",
                "discipline_department_id" : "2",
                "discipline_department_shortname" : "ФЫВАПР"
            },
            {
                "discipline_code" : "0",
                "discipline_name" : "НАЗВАНИЕ ПРЕДМЕТА",
                "discipline_shortname" : "ЙЦУКЕН",
                "is_elective" : "Нет",
                "discipline_department_code" : "1",
                "discipline_department_id" : "2",
                "discipline_department_shortname" : "ФЫВАПР"
            }
        ]
        """

        ReferenceImporter.import_subject_reference(SUBJECT_REFERENCE_DATA)
        ReferenceImporter.import_subject_reference(SUBJECT_REFERENCE_DATA)

        try:
            self.assertEqual(Subject.objects.all().count(), 1)
        except Subject.DoesNotExist:
            self.fail()

    def test_teacher_import_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "222",
                    "faculty_fullname" : "Химико-технологический факультет",
                    "faculty_code" : "000000222",
                    "faculty_shortname" : "ХТФ"
                }
            ]
        """
        TEACHER_REFERENCE_DATA = """
        [
            {
                "staff_department_code" : "111",
                "staff_department" : "Факультет электроники и вычислительной техники",
                "staff_code" : "000008945",
                "staff_surname" : "Рамасуббу",
                "staff_name" : "Сундер",
                "staff_patronymic" : ""
            },
            {
                "staff_department_code" : "222",
                "staff_department" : "Химико-технологический факультет",
                "staff_code" : "000008785",
                "staff_surname" : "Завьялов",
                "staff_name" : "Дмитрий",
                "staff_patronymic" : "Викторович"
            }
        ]
        """
        
        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_teacher_reference(TEACHER_REFERENCE_DATA)

        try:
            self.assertEqual(EventParticipant.objects.all().count(), 2)
            self.assertNotEqual(EventParticipant.objects.get(name="Рамасуббу С."), None)
            self.assertEqual(EventParticipant.objects.get(role=EventParticipant.Role.TEACHER, department__code="222").name, "Завьялов Д.В.")
        except EventParticipant.DoesNotExist:
            self.fail()

    def test_teacher_import_duplicate_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "222",
                    "faculty_fullname" : "Химико-технологический факультет",
                    "faculty_code" : "000000222",
                    "faculty_shortname" : "ХТФ"
                }
            ]
        """
        TEACHER_REFERENCE_DATA = """
        [
            {
                "staff_department_code" : "222",
                "staff_department" : "Химико-технологический факультет",
                "staff_code" : "000008785",
                "staff_surname" : "Завьялов",
                "staff_name" : "Дмитрий",
                "staff_patronymic" : "Викторович"
            },
            {
                "staff_department_code" : "222",
                "staff_department" : "Химико-технологический факультет",
                "staff_code" : "000008785",
                "staff_surname" : "Завьялов",
                "staff_name" : "Дмитрий",
                "staff_patronymic" : "Викторович"
            },
            {
                "staff_department_code" : "222",
                "staff_department" : "Химико-технологический факультет",
                "staff_code" : "000008785",
                "staff_surname" : "Завьялов",
                "staff_name" : "Денис",
                "staff_patronymic" : "Владимирович"
            }
        ]
        """
        
        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_teacher_reference(TEACHER_REFERENCE_DATA)

        try:
            self.assertEqual(EventParticipant.objects.all().count(), 3)
        except EventParticipant.DoesNotExist:
            self.fail()

    def test_student_import_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """
        DEPARTMENT_REFERENCE_DATA = """
            [
                {
                    "department_id" : "1",
                    "department_code" : "000000001",
                    "department_fullname" : "Кафедра Автоматизация производственных процессов",
                    "department_shortname" : "АПП",
                    "faculty_id" : "111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "department_id" : "2",
                    "department_code" : "000000002",
                    "department_fullname" : "Кафедра Автоматические установки",
                    "department_shortname" : "АУ",
                    "faculty_id" : "111",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """
        STUDENT_REFERENCE_DATA = """
        [
            {
                "group_code" : "000003049",
                "group_name" : "АДП-222",
                "faculty_id" : "000000001",
                "speciality" : "Управление в технических системах",
                "profile" : "Автоматизированные системы управления в цифровом производстве",
                "qualification" : "Бакалавр",
                "graduating_department_name" : ""
            },
            {
                "group_code" : "000000700",
                "group_name" : "АДП-322",
                "faculty_id" : "000000002",
                "speciality" : "Управление в технических системах",
                "profile" : "Аддитивное производство",
                "qualification" : "Бакалавр",
                "graduating_department_name" : ""
            }
        ]
        """
        
        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_department_reference(DEPARTMENT_REFERENCE_DATA)
        ReferenceImporter.import_student_reference(STUDENT_REFERENCE_DATA)

        try:
            self.assertEqual(EventParticipant.objects.all().count(), 2)
            self.assertNotEqual(EventParticipant.objects.get(name="АДП-222"), None)
            self.assertEqual(EventParticipant.objects.get(
                role=EventParticipant.Role.STUDENT,
                is_group=True,
                department__name="Кафедра Автоматические установки"
            ).name, "АДП-322")
        except EventParticipant.DoesNotExist:
            self.fail()

    def test_student_import_duplicate_reference(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """
        DEPARTMENT_REFERENCE_DATA = """
            [
                {
                    "department_id" : "1",
                    "department_code" : "000000001",
                    "department_fullname" : "Кафедра Автоматизация производственных процессов",
                    "department_shortname" : "АПП",
                    "faculty_id" : "111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "department_id" : "2",
                    "department_code" : "000000002",
                    "department_fullname" : "Кафедра Автоматические установки",
                    "department_shortname" : "АУ",
                    "faculty_id" : "111",
                    "faculty_shortname" : "ФЭВТ"
                }
            ]
        """
        STUDENT_REFERENCE_DATA = """
        [
            {
                "group_code" : "000000558",
                "group_name" : "ПрИн-166",
                "faculty_id" : "000000001",
                "speciality" : "Программная инженерия",
                "profile" : "Программная инженерия. Факультет ФЭВТ",
                "qualification" : "бакалавр техники и технологии",
                "graduating_department_name" : ""
            },
            {
                "group_code" : "000000558",
                "group_name" : "ПрИн-166",
                "faculty_id" : "000000001",
                "speciality" : "Программная инженерия",
                "profile" : "Программная инженерия. Факультет ФЭВТ",
                "qualification" : "бакалавр техники и технологии",
                "graduating_department_name" : ""
            }
        ]
        """
        
        Organization.objects.create(name="ВолгГТУ")

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_department_reference(DEPARTMENT_REFERENCE_DATA)
        ReferenceImporter.import_student_reference(STUDENT_REFERENCE_DATA)
        ReferenceImporter.import_student_reference(STUDENT_REFERENCE_DATA)

        try:
            self.assertEqual(EventParticipant.objects.all().count(), 1)
        except EventParticipant.DoesNotExist:
            self.fail()

    def test_schedule_import_saving_archive(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "222",
                    "faculty_fullname" : "Химико-технологический факультет",
                    "faculty_code" : "000000222",
                    "faculty_shortname" : "ХТФ"
                }
            ]
        """
        SCHEDULE_REFERENCE_DATA = """
            [
                {
                    "course": "4",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": "бакалавриат",
                    "department_shortname": "ФЭВТ"
                },
                {
                    "course": "4",
                    "schedule_template_metadata_faculty_shortname": "ХТФ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": "  магистратура ",
                    "department_shortname": "ХТФ"
                },
                {
                    "course": "3",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": " Магистратура",
                    "department_shortname": "ФЭВТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")
        if not create_common_abstract_days():
            self.fail()

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)

        # first import
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, True)

        try:
            self.assertEqual(Schedule.objects.all().count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 0)
            self.assertNotEqual(
                Schedule.objects.get(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ),
                None
            )
            self.assertNotEqual(
                Schedule.objects.get(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=3
                ),
                None
            )
        except Schedule.DoesNotExist:
            self.fail()

        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

        # second import
        # now we have ARCHIVE Schedules
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, True)

        try:
            self.assertEqual(Schedule.objects.all().count(), 6)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 3)
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ARCHIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
        except Schedule.DoesNotExist:
            self.fail()

        # nothing must change
        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

        # third import
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, True)

        try:
            self.assertEqual(Schedule.objects.all().count(), 9)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 6)
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ARCHIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                2
            )
        except Schedule.DoesNotExist:
            self.fail()

        # nothing must change
        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

    def test_schedule_import_deleting_archive(self):
        FACULTY_REFERENCE_DATA = """
            [
                {
                    "faculty_id" : "111",
                    "faculty_fullname" : "Факультет электроники и вычислительной техники",
                    "faculty_code" : "000000111",
                    "faculty_shortname" : "ФЭВТ"
                },
                {
                    "faculty_id" : "222",
                    "faculty_fullname" : "Химико-технологический факультет",
                    "faculty_code" : "000000222",
                    "faculty_shortname" : "ХТФ"
                }
            ]
        """
        SCHEDULE_REFERENCE_DATA = """
            [
                {
                    "course": "4",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": "бакалавриат",
                    "department_shortname": "ФЭВТ"
                },
                {
                    "course": "4",
                    "schedule_template_metadata_faculty_shortname": "ХТФ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": "  магистры ",
                    "department_shortname": "ХТФ"
                },
                {
                    "course": "3",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2025",
                    "end_date": "01.02.2026",
                    "scope": " Магистратура",
                    "department_shortname": "ФЭВТ"
                }
            ]
        """

        Organization.objects.create(name="ВолгГТУ")
        if not create_common_abstract_days():
            self.fail()

        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)

        # first import
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, False)

        try:
            self.assertEqual(Schedule.objects.all().count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 0)
            self.assertNotEqual(
                Schedule.objects.get(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ),
                None
            )
            self.assertNotEqual(
                Schedule.objects.get(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=3
                ),
                None
            )
        except Schedule.DoesNotExist:
            self.fail()

        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

        # second import
        # now we have ARCHIVE Schedules
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, False)

        try:
            self.assertEqual(Schedule.objects.all().count(), 6)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 3)
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ARCHIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
        except Schedule.DoesNotExist:
            self.fail()

        # nothing must change
        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

        # third import
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, False)

        try:
            self.assertEqual(Schedule.objects.all().count(), 6)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 3)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 3)
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ФЭВТ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ACTIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
            self.assertEqual(
                Schedule.objects.filter(
                    status=Schedule.Status.ARCHIVE,
                    schedule_template__metadata__faculty="ХТФ",
                    metadata__course=4
                ).count(),
                1
            )
        except Schedule.DoesNotExist:
            self.fail()

        # nothing must change
        # 4 course 1 semester 2024-2025
        # 3 course 1 semester 2024-2025
        try:
            self.assertEqual(ScheduleMetadata.objects.all().count(), 2)
        except ScheduleMetadata.DoesNotExist:
            self.fail()

        # Факультет электроники и вычислительной техники (Бакалавриат)
        # Факультет электроники и вычислительной техники (Магистратура)
        # Химико-технологический факультет
        try:
            self.assertEqual(ScheduleTemplate.objects.all().count(), 3)
        except ScheduleTemplate.DoesNotExist:
            self.fail()
        
        # ФЭВТ, Бакалавриат
        # ФЭВТ, Магистратура
        # ХТФ, Магистратура
        try:
            self.assertEqual(ScheduleTemplateMetadata.objects.all().count(), 3)
        except ScheduleTemplateMetadata.DoesNotExist:
            self.fail()

    # TODO: schedule_import test with event deleting
