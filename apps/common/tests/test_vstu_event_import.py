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
from apps.common.services.timetable.load.event_importer import EventImporterBase
from apps.common.services.timetable.load.vtsu.vstu_event_importer import VSTUEventImporter
from apps.common.services.timetable.load.event_importer import EventImporter
from apps.common.services.timetable.load.reference_importer import ReferenceImporter
from apps.common.services.timetable.read.filters import (
    PlaceFilter,
    TimeSlotFilter,
)
from apps.common.services.timetable.utilities.model_helpers import (
    create_common_abstract_days,
    create_common_time_slots,
)

"""python manage.py test apps.common.tests.test_vstu_event_import
"""


# TODO: split into separate tests: VSTU importer and pure EventImporterBase
class TestVSTUEventImporter(TestCase):
    importer : VSTUEventImporter = None
    
    def setUp(self):
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
                    "semester": "2",
                    "years": "2024-2025",
                    "start_date": "01.09.2024",
                    "end_date": "01.02.2025",
                    "scope": "Бакалавриат",
                    "department_shortname": "ФЭВТ"
                },
                {
                    "course": "2",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "1",
                    "years": "2024-2025",
                    "start_date": "01.09.2024",
                    "end_date": "01.02.2025",
                    "scope": "магистры",
                    "department_shortname": "ФЭВТ"
                },
                {
                    "course": "1",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "2",
                    "years": "2024-2025",
                    "start_date": "01.09.2024",
                    "end_date": "01.02.2025",
                    "scope": "аспиранты",
                    "department_shortname": "ФЭВТ"
                }
            ]
        """
    
        self.importer = VSTUEventImporter()

        create_common_abstract_days()
        create_common_time_slots()
        Organization.objects.create(name="ВолгГТУ")
        ReferenceImporter.import_faculty_reference(FACULTY_REFERENCE_DATA)
        ReferenceImporter.import_schedule(SCHEDULE_REFERENCE_DATA, True)

    def test_get_schedule_find_parameters(self):
        with self.assertRaises(ValueError) as err:  
            self.importer.set_title("")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось извлечь КУРС из заголовка"), True)

            self.importer.set_title("Учебные занятия 4 курса бакалавриат на 2 семестр 2024-2025 учебного года")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось извлечь ПОДРАЗДЕЛЕНИЕ или ФАКУЛЬТЕТ из заголовка"), True)

            self.importer.set_title("Учебные занятия 4 курса НЕСУЩЕСТВУЮЩЕЕПОДРАЗДЕЛЕНИЕ бакалавриат на 2 семестр 2024-2025 учебного года")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось найти подходящее ПОДРАЗДЕЛЕНИЕ или ФАКУЛЬТЕТ для заголовка"), True)

            self.importer.set_title("Учебные занятия 4 курса ФЭВТ на 2 семестр 2024-2025 учебного года")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось извлечь СТЕПЕНЬ ОБУЧЕНИЯ из заголовка"), True)

            self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2024-2025")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось извлечь НОМЕР СЕМЕСТРА из заголовка"), True)

            self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2 семестр")
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception.startswith("Не удалось извлечь ГОД ОБУЧЕНИЯ из заголовка"), True)

    def test_find_schedule(self):
        self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2 семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(schedule_template__metadata__faculty="ФЭВТ", schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR)
        )

        self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2 семестр 2024 -  2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(schedule_template__metadata__faculty="ФЭВТ", schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR)
        )

        self.assertRaises(
            Schedule.DoesNotExist,
            self.importer._EventImporterBase__find_schedule,
            *(
                11,
                "НЕСУЩЕСТВУЮЩИЙФАКУЛЬТЕТ",
                "Бакалавр",
                99,
                "2000-2010"
            )
        )

        ReferenceImporter.import_schedule("""
            [
                {
                    "course": "4",
                    "schedule_template_metadata_faculty_shortname": "ФЭВТ",
                    "semester": "2",
                    "years": "2024-2025",
                    "start_date": "01.09.2024",
                    "end_date": "01.02.2025",
                    "scope": "Бакалавриат",
                    "department_shortname": "ФЭВТ"
                }
            ]
        """, True)

        second_schedule = Schedule.objects.get(status=Schedule.Status.ARCHIVE)
        second_schedule.status = Schedule.Status.ACTIVE
        second_schedule.save()

        self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2 семестр 2024-2025 учебного года")
        self.assertRaises(
            Schedule.MultipleObjectsReturned,
            self.importer._EventImporterBase__find_schedule,
            *self.importer._get_schedule_find_parameters()
        )

    def test_find_schedule_scopes(self):
        self.importer.set_title("4 курс ФЭВТ Бакалавры II-ого семестра 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
                metadata__course=4,
                metadata__semester=2
            )
        )

        self.importer.set_title("4 курс ФЭВТ бакалавров II-ого семестра 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
                metadata__course=4,
                metadata__semester=2
            )
        )

        self.importer.set_title("Учебные занятия ФЭВТ магистров 2 курса I-ого семестра 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.MASTER,
                metadata__course=2,
                metadata__semester=1
            )
        )

        self.importer.set_title("Учебные занятия ФЭВТ магистратуры 2 курса I-ого семестра 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.MASTER,
                metadata__course=2,
                metadata__semester=1
            )
        )

        self.importer.set_title("ФЭВТ 1 курс аспирантов на II-й семестр 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.POSTGRADUATE,
                metadata__course=1,
                metadata__semester=2
            )
        )

    def test_find_schedule_multiple_department(self):
        self.importer.set_title("Учебные занятия 4 курса АБЬЪ-999, ФЭВТ бакалавриат на 2 семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(schedule_template__metadata__faculty="ФЭВТ", schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR)
        )

        self.importer.set_title("Учебные занятия 4 курса ФЭВТ ХТФ бакалавриат на 2 семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(schedule_template__metadata__faculty="ФЭВТ", schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR)
        )

        WRONG_SCHEDULE_TITLE = "Учебные занятия 4 курса АБВГ, ПРИН-466 бакалавриат на 2 семестр 2024-2025 учебного года"

        with self.assertRaises(ValueError) as err:  
            self.importer.set_title(WRONG_SCHEDULE_TITLE)
            self.importer._get_schedule_find_parameters()  
            self.assertEqual(err.exception, f"Не удалось найти подходящее ПОДРАЗДЕЛЕНИЕ или ФАКУЛЬТЕТ для заголовка '{WRONG_SCHEDULE_TITLE}'.")

    def test_find_schedule_semester(self):
        self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на II-ой семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
                metadata__course=4,
                metadata__semester=2
            )
        )

        self.importer.set_title("Учебные занятия 4 курса ФЭВТ бакалавриат на 2семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
                metadata__course=4,
                metadata__semester=2
            )
        )

        self.importer.set_title("Учебные занятия 2 курса ФЭВТ магистров 1-ого семестра 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.MASTER,
                metadata__course=2,
                metadata__semester=1
            )
        )

        self.importer.set_title("Учебные занятия 1 курса ФЭВТ аспирантов II-огосеместра 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.POSTGRADUATE,
                metadata__course=1,
                metadata__semester=2
            )
        )

    def test_find_schedule_course(self):
        self.importer.set_title("ФЭВТ 4ыйкурс бакалавр. 2 семестра 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
                metadata__course=4,
                metadata__semester=2
            )
        )

        self.importer.set_title("ФЭВТ 2-ого курса  Магистров 1ый семестр 2024-2025")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.MASTER,
                metadata__course=2,
                metadata__semester=1
            )
        )

        self.importer.set_title("Учебные занятия 1ый курс ФЭВТ аспиранты 2-ой семестр 2024-2025 учебного года")
        self.assertEqual(
            self.importer._EventImporterBase__find_schedule(*self.importer._get_schedule_find_parameters()),
            Schedule.objects.get(
                schedule_template__metadata__faculty="ФЭВТ", 
                schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.POSTGRADUATE,
                metadata__course=1,
                metadata__semester=2
            )
        )

    def test_find_schedule_upper_and_lower_chars(self):
        # TODO: ФАСТиВ
        pass

    def test_correct_holds_on_date_data(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )
        
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, [
                "10.09.2001", 
                "11.09.2002", 
                "12.09.2003", 
                "14.09.2004"
            ]), 
            None
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, [
                "12.09.1999", 
                "04.09..02.10", 
                "12.07;12.08", 
                "05.09",
                "с 03.09",

            ]),
            sorted([
                "12.09.1999",

                "04.09.2024",
                "18.09.2024",
                "02.10.2024",

                "12.07.2024",
                "12.08.2024",

                "05.09.2024",

                "03.09.2024", 
                "17.09.2024", 
                "01.10.2024", 
                "15.10.2024", 
                "29.10.2024", 
                "12.11.2024", 
                "26.11.2024", 
                "10.12.2024", 
                "24.12.2024", 
                "07.01.2025", 
                "21.01.2025"
            ])
        )

        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, [
                "10.09.1999", 
                "11.09.1999", 
                "04.09..02.10", 
                "12.09.1999", 
                "03.09",
                "14.09.1999"
            ]),
            sorted([
                "10.09.1999", 

                "11.09.1999", 

                "04.09.2024",
                "18.09.2024",
                "02.10.2024",

                "12.09.1999", 

                "03.09.2024",

                "14.09.1999"
            ])
        )

    def test_correct_holds_on_date_data_double_range(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )
        
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["03.09..01.10"]),
            sorted([
                "03.09.2024",
                "17.09.2024",
                "01.10.2024"
            ])
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["03.09..01.10", "03.09..01.10"]),
            sorted([
                "03.09.2024",
                "17.09.2024",
                "01.10.2024"
            ])
        )        

    def test_correct_holds_on_date_data_single_range(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )

        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["с 03.09"]),
            sorted([
                "03.09.2024", 
                "17.09.2024", 
                "01.10.2024", 
                "15.10.2024", 
                "29.10.2024", 
                "12.11.2024", 
                "26.11.2024", 
                "10.12.2024", 
                "24.12.2024", 
                "07.01.2025", 
                "21.01.2025"
            ])
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["с 03.09", "с 03.09"]),
            sorted([
                "03.09.2024", 
                "17.09.2024", 
                "01.10.2024", 
                "15.10.2024", 
                "29.10.2024", 
                "12.11.2024", 
                "26.11.2024", 
                "10.12.2024", 
                "24.12.2024", 
                "07.01.2025", 
                "21.01.2025"
            ])
        )
        
    def test_correct_holds_on_date_data_colon(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )
        
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["12.09;10.10;07.11;05.12"]),
            sorted([
                "12.09.2024",
                "10.10.2024",
                "07.11.2024",
                "05.12.2024"
            ])
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, [" 13.09;  11.10  ; 08.11 ;06.12   "]),
            sorted([
                "13.09.2024",
                "11.10.2024",
                "08.11.2024",
                "06.12.2024"
            ])
        )

    def test_correct_holds_on_date_data_add_year(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )

        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["03.09"]),
            [
                "03.09.2024"
            ]
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["12.12."]),
            [
                "12.12.2024"
            ]
        )
        self.assertEqual(
            EventImporter.correct_holds_on_date_data(SCHEDULE, ["03.09", "03.09", "04.09"]),
            sorted([
                "03.09.2024",
                "04.09.2024"
            ])
        )

    def test_make_calendar(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )
        MONTHS = [
            "февраль",
            "март",
            "апрель",
            "май",
            "июнь",
            "сентябрь"
        ]
        weeks_as_dict = {
            "first_week": [
                {
                    "week_day_index": 0,
                    "calendar": [
                        {
                            "month_index": 0,
                            "month_days": ["1", "15"]
                        },
                        {
                            "month_index": 1,
                            "month_days": ["20", "28"]
                        }
                    ]
                }
            ],
            "second_week": [
                {
                    "week_day_index": 0,
                    "calendar": [
                        {
                            "month_index": 0,
                            "month_days": ["8", "22"]
                        }
                    ]
                },
                {
                    "week_day_index": 1,
                    "calendar": [
                        {
                            "month_index": 0,
                            "month_days": ["9", "23"]
                        }
                    ]
                }
            ]
        }
        weeks_as_list = [
            {
                "first_week": [
                    {
                        "week_day_index": 0,
                        "calendar": [
                            {
                                "month_index": 0,
                                "month_days": ["1", "15"]
                            },
                            {
                                "month_index": 1,
                                "month_days": ["20", "28"]
                            }
                        ]
                    }
                ]
            },
            {
                "second_week": [
                    {
                        "week_day_index": 0,
                        "calendar": [
                            {
                                "month_index": 0,
                                "month_days": ["8", "22"]
                            }
                        ]
                    },
                    {
                        "week_day_index": 1,
                        "calendar": [
                            {
                                "month_index": 0,
                                "month_days": ["9", "23"]
                            }
                        ]
                    }
                ]
            }
        ]
        
        FIRST_WEEK_EXPECTED_RESULT = { 
            "first_week" : { 
                0 : [
                    datetime.strptime("1.02.2025", "%d.%m.%Y").date(),
                    datetime.strptime("15.02.2025", "%d.%m.%Y").date(),
                    datetime.strptime("20.03.2025", "%d.%m.%Y").date(),
                    datetime.strptime("28.03.2025", "%d.%m.%Y").date()
                ]
            }
        }
        SECOND_WEEK_EXPECTED_RESULT = {
            "second_week" : { 
                0 : [
                    datetime.strptime("8.02.2025", "%d.%m.%Y").date(),
                    datetime.strptime("22.02.2025", "%d.%m.%Y").date()
                ],
                1 : [
                    datetime.strptime("9.02.2025", "%d.%m.%Y").date(),
                    datetime.strptime("23.02.2025", "%d.%m.%Y").date()
                ]
            } 
        }
        expected_result : dict = {}
        expected_result.update(FIRST_WEEK_EXPECTED_RESULT)
        expected_result.update(SECOND_WEEK_EXPECTED_RESULT)

        self.assertEqual(
            EventImporter.make_calendar(weeks_as_dict, MONTHS, SCHEDULE),
            expected_result
        )
        self.assertEqual(
            EventImporter.make_calendar(weeks_as_list, MONTHS, SCHEDULE),
            expected_result
        )

        weeks_as_dict.pop("first_week")
        weeks_as_list.pop(1)

        self.assertEqual(
            EventImporter.make_calendar(weeks_as_dict, MONTHS, SCHEDULE),
            SECOND_WEEK_EXPECTED_RESULT
        )
        self.assertEqual(
            EventImporter.make_calendar(weeks_as_list, MONTHS, SCHEDULE),
            FIRST_WEEK_EXPECTED_RESULT
        )

        self.assertEqual(
            EventImporter.make_calendar(
                {
                    "first_week": [
                        {
                            "week_day_index": 0,
                            "calendar": [
                                {
                                    "month_index": 0,
                                    "month_days": ["1"]
                                },
                                {
                                    "month_index": 1,
                                    "month_days": ["1"]
                                }
                            ]
                        }
                    ]
                }, 
                [
                    "декабрь",
                    "февраль"
                ], 
                SCHEDULE
            ),
            { 
                "first_week" : { 
                    0 : [
                        datetime.strptime("1.12.2024", "%d.%m.%Y").date(),
                        datetime.strptime("1.02.2025", "%d.%m.%Y").date()
                    ]
                }
            }
        )

        self.assertRaises(
            ValueError,
            EventImporter.make_calendar,
            set(), MONTHS, SCHEDULE
        )
        self.assertRaises(
            ValueError,
            EventImporter.make_calendar,
            [["qwe"], ["asd"]], MONTHS, SCHEDULE
        )
        self.assertRaises(
            ValueError,
            EventImporter.make_calendar,
            {}, MONTHS, SCHEDULE
        )

    def test_create_events(self):
        SCHEDULE = Schedule.objects.get(
            schedule_template__metadata__faculty="ФЭВТ", 
            schedule_template__metadata__scope=ScheduleTemplateMetadata.Scope.BACHELOR,
            metadata__course=4,
            metadata__semester=2
        )
        DEPARTMENT = Department.objects.get(shortname="ФЭВТ")
        CALENDAR = [
            datetime.strptime("1.02.2025", "%d.%m.%Y").date(),
            datetime.strptime("15.02.2025", "%d.%m.%Y").date()
        ]
        KIND = EventKind.objects.create(name="Лекция")
        SUBJECT = Subject.objects.create(name="ВКР")
        PARTICIPANTS = [
            EventParticipant.objects.create(
                name="Гилка В.В.",
                role=EventParticipant.Role.TEACHER,
                is_group=False,
                department=DEPARTMENT
            ),
            EventParticipant.objects.create(
                name="ПрИн-466",
                role=EventParticipant.Role.STUDENT,
                is_group=True,
                department=DEPARTMENT
            )
        ]
        PLACES = [EventPlace.objects.create(building="В", room="902")]
        TIME_SLOTS = [
            TimeSlot.objects.get(alt_name="1-2"),
            TimeSlot.objects.get(alt_name="3-4")
        ]

        EventImporter.create_events(
            SCHEDULE,
            KIND,
            SUBJECT,
            PARTICIPANTS,
            PLACES,
            AbstractDay.objects.get(day_number=0),
            TIME_SLOTS,
            [None],
            CALENDAR
        )

        self.assertEqual(AbstractEvent.objects.all().count(), 2)
        self.assertEqual(Event.objects.all().count(), 4)

        # trying to create duplicate
        EventImporter.create_events(
            SCHEDULE,
            KIND,
            SUBJECT,
            PARTICIPANTS,
            PLACES,
            AbstractDay.objects.get(day_number=0),
            TIME_SLOTS,
            [None],
            CALENDAR
        )

        self.assertEqual(AbstractEvent.objects.all().count(), 2)
        self.assertEqual(Event.objects.all().count(), 4)

        # still able to create AbstractEvents with holds_on_date
        # method creates 4 AbstractEvents (for 2 holds_on_date with 2 time_slots)
        # and 4 Events
        EventImporter.create_events(
            SCHEDULE,
            KIND,
            SUBJECT,
            PARTICIPANTS,
            PLACES,
            AbstractDay.objects.get(day_number=0),
            TIME_SLOTS,
            [
                datetime.strptime("10.03.2025", "%d.%m.%Y").date(),
                datetime.strptime("11.03.2025", "%d.%m.%Y").date()
            ],
            None
        )

        self.assertEqual(AbstractEvent.objects.all().count(), 6)
        self.assertEqual(Event.objects.all().count(), 8)

        # trying to create duplicate
        EventImporter.create_events(
            SCHEDULE,
            KIND,
            SUBJECT,
            PARTICIPANTS,
            PLACES,
            AbstractDay.objects.get(day_number=0),
            TIME_SLOTS,
            [
                datetime.strptime("10.03.2025", "%d.%m.%Y").date(),
                datetime.strptime("11.03.2025", "%d.%m.%Y").date()
            ],
            None
        )

        self.assertEqual(AbstractEvent.objects.all().count(), 6)
        self.assertEqual(Event.objects.all().count(), 8)

    def test_prepare_reference_lookup(self):
        ENTRY_DATA = {
            "subject": "ВКР",
            "kind": "лекция",
            "participants": {
                "teachers": [
                    "Гилка В.В.",
                    "Кузнецова А.С."
                ],
                "student_groups": [
                    "ИВТ-460"
                ]
            },
            "places": [
                "В 902а",
                "В 902б"
            ],
            "hours": [
                "11-12",
                "8.30",
                "10.10"
            ],
            "week_day_index": 0,
            "week": "first_week",
            "holds_on_date": [
                "09.11.2024"
            ]
        }

        EXPECTED_REFERENCE_DATA = {
            "subject": "ВКР", 
            "kind": "Лекция", 
            "teachers": {
                "Кузнецова А.С.", "Гилка В.В."
            }, 
            "groups": {
                "ИВТ-460"
            }, 
            "places": {
                ("В", "902б"), 
                ("В", "902а")
            }, 
            "time_slots": {
                ("11-12", "", ""), 
                ("", "10:10", ""), 
                ("", "8:30", "")
            }
        }

        self.assertEqual(
            self.importer._EventImporterBase__prepare_reference_data(ENTRY_DATA),
            EXPECTED_REFERENCE_DATA
        )

    # with empty reference_lookup
    # with non empty reference_lookup when some models already exists in reference_lookup
    # already have something in DB that needs to be in reference_lookup
    def test_ensure_reference_lookup_duplicate(self):
        REFERENCE_DATA = [
            {
                "subject": "МИКРОПРОЦЕССОРЫ", 
                "kinds": "Лекция", 
                "teachers": {
                    "Гилка В.В.", 
                    "Кузнецова А.С."
                }, 
                "groups": {
                    "ИВТ-460",
                    "ПрИн-467",
                    "ПрИн-467"
                }, 
                "places": {
                    ("В", "902а"), 
                    ("В", "902б"),
                    ("В", "908")
                }, 
                "time_slots": {
                    ("", "8:30", ""), 
                    ("11-12", "", ""), 
                    ("", "11:50", "13:20")
                }
            },
            {
                "subject": "МИКРОПРОЦЕССОРЫ", 
                "kinds": "Лекция", 
                "teachers": {
                    "Гилка В.В.",
                    "Дмитриев А.С.", 
                    "Синкевич Д."
                }, 
                "groups": {
                    "ПрИн-467", 
                    "ПрИн-466"
                }, 
                "places": {
                    ("В", "903"), 
                    ("В", "908")
                }, 
                "time_slots": {
                    ("", "11:50", "13:20")
                }
            }
        ]
                
        for data in REFERENCE_DATA:
            self.importer._EventImporterBase__build_reference_lookup(data)

        for subject in Subject.objects.all():
            self.assertEqual(
                Subject.objects.filter(name=subject.name).count(),
                1
            )
        for kind in EventKind.objects.all():
            self.assertEqual(
                EventKind.objects.filter(name=kind.name).count(),
                1
            )
        for participant in EventParticipant.objects.all():
            self.assertEqual(
                EventParticipant.objects.filter(name=participant.name).count(),
                1
            )
        for place in EventPlace.objects.all():
            self.assertEqual(
                EventPlace.objects.filter(
                    building=place.building, 
                    room=place.room
                ).count(),
                1
            )
        for time_slot in TimeSlot.objects.all():
            self.assertEqual(
                TimeSlot.objects.filter(
                    alt_name=time_slot.alt_name, 
                    start_time=time_slot.start_time,
                    end_time=time_slot.end_time
                ).count(),
                1
            )

    ## TODO: ...
    def test_(self):
        

        with open("apps/common/tests/data/test_import_1.json", "r", encoding="utf8") as data_file:
            json_data = json.loads(data_file.read())

        reference_lookup = {
            "subjects" : {},
            "kinds" : {},
            "participants" : {},
            "places" : {},
            "time_slots" : TimeSlot.objects.none()
        }

        for entry in json_data["table"]["grid"]:
            reference_data = EventImporter.collect_reference_data(entry)
            #EventImportAPI._ensure_reference_data(reference_data)
            #reference_lookup = EventImportAPI._build_reference_lookup(reference_data)

            EventImporter.make_reference_lookup(reference_data, reference_lookup)
            EventImporter.make_reference_lookup(reference_data, reference_lookup)
            EventImporter.make_reference_lookup(reference_data, reference_lookup)
            EventImporter.make_reference_lookup(reference_data, reference_lookup)

        # print(reference_data)
        # print(reference_lookup)
        # print(EventParticipant.objects.all())

    def test_2(self):
        from django.db.models.functions import Lower
        EventKind.objects.create(name="QWE-166")

        # try:
            # print(EventKind.objects.annotate(lower_name=Lower("name")).filter(lower_name="qwe-166").all())
            
        # except EventKind.DoesNotExist:
            # print("ничего не найдено")

    """

    def test_import_data(self):
        # manualy created TimeSlot
        TimeSlot.objects.create(alt_name="11-12", start_time=datetime.strptime("17:00:00", "%H:%M:%S"), end_time=datetime.strptime("18:30:00", "%H:%M:%S"))

        with open("apps/common/tests/data/test_import_1.json", "r", encoding="utf8") as data_file:
            EventImportAPI.import_event_data(data_file.read())

        try:
            self.assertNotEqual(Event.objects.filter(**TimeSlotFilter.by_repr_event_relative("11-12")).first(), None)
            self.assertNotEqual(Event.objects.filter(**TimeSlotFilter.by_repr_event_relative("11:50")).first(), None)
            self.assertNotEqual(Event.objects.filter(**TimeSlotFilter.by_repr_event_relative("17:00")).first(), None)
        except Event.DoesNotExist:
            self.fail()

        try:
            self.assertNotEqual(AbstractEvent.objects.filter(**TimeSlotFilter.by_repr_abstract_event_relative("11-12")).first(), None)
            self.assertNotEqual(AbstractEvent.objects.filter(**TimeSlotFilter.by_repr_abstract_event_relative("11:50")).first(), None)
            self.assertNotEqual(AbstractEvent.objects.filter(**TimeSlotFilter.by_repr_abstract_event_relative("17:00")).first(), None)
            self.assertNotEqual(AbstractEvent.objects.filter(participants__name="Гилка В.В.").first(), None)
            self.assertNotEqual(AbstractEvent.objects.filter(participants__name="ИВТ-460", participants__role="student").first(), None)
        except AbstractEvent.DoesNotExist:
            self.fail()

        try:
            self.assertNotEqual(TimeSlot.objects.get(**TimeSlotFilter.by_start_time("17:00")[0]), None)
            self.assertNotEqual(TimeSlot.objects.get(**TimeSlotFilter.by_start_time("10:10")[0]), None)
        except TimeSlot.DoesNotExist:
            self.fail()

        try:
            self.assertNotEqual(EventPlace.objects.get(**PlaceFilter.by_repr("В 902а")), None)
        except EventPlace.DoesNotExist:
            self.fail()
    
    def test_collect_reference_data(self):
        INPUT_DATA = [
            {
                "subject": "ВКР",
                "kind": "лекция",
                "participants": {
                    "teachers": [
                        "Гилка В.В.",
                        "Кузнецова А.С."
                    ],
                    "student_groups": [
                        "ИВТ-460"
                    ]
                },
                "places": [
                    "В 902а",
                    "В 902б"
                ],
                "hours": [
                    "1-2",
                    "3-4"
                ],
                "week_day_index": 0,
                "week": "first_week",
                "holds_on_date": [
                    "09.11.2024"
                ]
            },
            {
				"subject": "МИКРОПРОЦЕССОРЫ",
				"kind": "лабораторная работа",
				"participants": {
					"teachers": [
						"Синкевич Д.",
						"Дмитриев А.С."
					],
					"student_groups": [
						"ПрИн-466",
						"ПрИн-467"
					]
				},
				"places": [
					"ГУК101",
					"312"
				],
				"hours": [
					"18.30",
					"11:11 -  12.01"
				],
				"week_day_index": 1,
				"week": "second_week",
				"holds_on_date": []
			}
        ]

        return_value = EventImportAPI._collect_reference_data(INPUT_DATA)
        
        self.assertSequenceEqual(
            return_value,
            {
                "subjects" : {"ВКР", "МИКРОПРОЦЕССОРЫ"},
                "kinds" : {"Лекция", "Лабораторная работа"},
                "teacher_names" : {"Гилка В.В.", "Кузнецова А.С.", "Синкевич Д.", "Дмитриев А.С."},
                "group_names" : {"ИВТ-460", "ПрИн-466", "ПрИн-467"},
                "places" : {("В", "902а"), ("В", "902б"), ("", "ГУК101"), ("", "312")},
                "time_slots" : {("1-2", "", ""), ("3-4", "", ""), ("", "18:30", ""), ("", "11:11", "12:01")}
            }
        )

    def test_ensure_reference_data(self):
        INPUT_DATA = {
            "subjects" : set(),
            "kinds" : set(),
            "teacher_names" : set(),
            "group_names" : set(),
            "places" : set(),
            "time_slots" : {
                ("1-2", "8:30", ""),
                ("", "11:55", ""),
                ("5-6", "13:40", "15:01"),
                ("", "15:09", "15:10")
            }
        }

        EventImportAPI._ensure_reference_data(INPUT_DATA)

        try:
            self.assertEqual(TimeSlot.objects.all().count(), 4)
            self.assertNotEqual(TimeSlot.objects.get(start_time__contains="8:30"), None)
            self.assertNotEqual(TimeSlot.objects.get(start_time__contains="11:55"), None)
            self.assertNotEqual(TimeSlot.objects.get(end_time__contains="15:01"), None)
            self.assertNotEqual(TimeSlot.objects.get(end_time__contains="15:10"), None)
        except TimeSlot.DoesNotExist:
            self.fail()

    def test_import_events_for_only_active_schedule(self):
        ReferenceImporter.import_schedule(self.SCHEDULE_REFERENCE_DATA, True)

        try:
            self.assertEqual(Schedule.objects.all().count(), 2)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ACTIVE).count(), 1)
            self.assertEqual(Schedule.objects.filter(status=Schedule.Status.ARCHIVE).count(), 1)
        except Schedule.DoesNotExist:
            self.fail()
        
        try:
            self.assertEqual(
                AbstractEvent.objects.filter(schedule__status=Schedule.Status.ACTIVE).count(),
                AbstractEvent.objects.all().count()
            )
            self.assertEqual(
                AbstractEvent.objects.filter(schedule__status=Schedule.Status.ARCHIVE).count(),
                0
            )
        except AbstractEvent.DoesNotExist:
            self.fail()
    
    # test_import_event_for_not_existing_time_slot

    """
