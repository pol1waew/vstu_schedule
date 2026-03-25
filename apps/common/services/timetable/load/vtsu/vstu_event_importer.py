import json
import re
from datetime import date, datetime, timedelta

from apps.common.models import (
    AbstractDay,
    Department,
    EventKind,
    EventParticipant,
    EventPlace,
    Schedule,
    Subject,
    TimeSlot,
)
from apps.common.selectors import Selector
from apps.common.services.timetable.load.event_importer import EventImporterBase
from apps.common.services.timetable.utilities.model_helpers import (
    is_abstract_event_already_exists,
)
from apps.common.services.timetable.utilities.normalizers import (
    normalize_kind_name,
    normalize_participant_name,
    normalize_place_building_and_room,
    normalize_scope,
    normalize_subject_name,
    normalize_time_slot_display_name,
)
from apps.common.services.timetable.utilities.utilities import (
    get_number_from_month_name,
    get_scope_from_label,
    replace_roman_with_arabic_numerals,
)
from apps.common.services.timetable.write.factories import (
    create_abstract_event,
    fill_semester_for_dates,
)


class VSTUEventImporter(EventImporterBase):
    title : str = ""

    def _extract_data(self, loaded_data : dict) -> None:
        self.set_title(loaded_data["title"])
        
        self._set_entries(loaded_data["table"]["grid"])
        self._set_weeks(loaded_data["table"]["datetime"]["weeks"])
        self._set_week_days(loaded_data["table"]["datetime"]["week_days"])
        self._set_months(loaded_data["table"]["datetime"]["months"])

    def _get_schedule_find_parameters(self) -> tuple[int, str, str, int, str]:
        # 4 курса
        # 4 курс
        # 4курса
        # 4   курса
        # 1ый курс
        # 5-ого курса
        # 3-го курса
        COURSE_REG_EX = r"(\d)(\-?[а-яА-ЯёЁ]*)?\s*курса?"

        # ФЭВТ
        # ТК
        # курсФЭВТна
        # TODO: ФАСТиВ
        FACULTY_REG_EX = r"[А-ЯЁ]{2,}"

        # Бакалавры
        # бакалавриат
        # магистров
        # Аспирантура
        # консульт.
        SCOPE_REG_EX = r"(([бБ]акалавр|[мМ]агистр|[аА]спирант|[кК]онсульт)[а-яА-ЯёЁ]*)"

        # 2 семестр
        # 2семестр
        # 2   семестр
        # 2-ой семестр
        # 2-й семестр
        # 1ый семестр
        ARABIC_NUMERALS_SEMESTER_REG_EX = r"(\d)(\-?[а-яА-ЯёЁ]*)?\s*семестра?"
        
        # 2024-2025
        # 2024 -  2025
        FULL_YEARS_REG_EX = r"(\d{4}\s*-\s*\d{4})"

        

        course_match = re.search(COURSE_REG_EX, self.title, flags=re.IGNORECASE)
        if not course_match:
            raise ValueError(f"Не удалось извлечь КУРС из заголовка '{self.title}'.")

        faculty_matches = re.findall(FACULTY_REG_EX, self.title)
        if not faculty_matches:
            raise ValueError(f"Не удалось извлечь ПОДРАЗДЕЛЕНИЕ или ФАКУЛЬТЕТ из заголовка '{self.title}'.")

        faculty = ""
        
        for match in faculty_matches:
            try:
                Department.objects.get(shortname=match)
            except Department.DoesNotExist:
                continue
            
            # Take first existing faculty from title
            faculty = match
            break

        if not faculty:
            raise ValueError(f"Не удалось найти подходящее ПОДРАЗДЕЛЕНИЕ или ФАКУЛЬТЕТ для заголовка '{self.title}'.")

        scope_match = re.search(SCOPE_REG_EX, self.title)
        if not scope_match:
            raise ValueError(f"Не удалось извлечь СТЕПЕНЬ ОБУЧЕНИЯ из заголовка '{self.title}'.")

        semester_match = re.search(ARABIC_NUMERALS_SEMESTER_REG_EX, self.title, flags=re.IGNORECASE)
        if not semester_match:
            raise ValueError(f"Не удалось извлечь НОМЕР СЕМЕСТРА из заголовка '{self.title}'.")

        full_years_match = re.search(FULL_YEARS_REG_EX, self.title)
        if not full_years_match:
            raise ValueError(f"Не удалось извлечь ГОД ОБУЧЕНИЯ из заголовка '{self.title}'.")

        return (
            int(course_match.group(1)),
            faculty,
            scope_match.group(1),
            int(semester_match.group(1)),
            full_years_match.group(1).replace(" ", "")
        )

    def _calculate_dates(self) -> dict:
        """Used to make calendar in format

        { 
            week_id : { 
                week_day_index : [
                    dd.mm.YYYY,
                    dd.mm.YYYY...
                ]
            } 
        }
        """
        
        normalized_weeks = {}

        if not len(self.__weeks):
            raise ValueError("Отсутствуют данные недель в импортируемом файле.")

        if isinstance(self.__weeks, dict):
            normalized_weeks = self.__weeks
        elif isinstance(self.__weeks, list):
            for week in self.__weeks:
                if isinstance(week, dict):
                    for key, data in week.items():
                        normalized_weeks[key] = data
                else:
                    raise ValueError("Некорректный формат данных недель в импортируемом файле.")
        else:
            raise ValueError("Некорректный формат данных недель в импортируемом файле.")

        calendar = {}

        LEFT_YEAR, RIGHT_YEAR = self.__schedule.metadata.years.split("-", 1)

        for key in normalized_weeks.keys():
            calendar[key] = {}

            for week_day in normalized_weeks[key]:
                calendar[key][week_day["week_day_index"]] = []

                for month in week_day["calendar"]:
                    month_number = get_number_from_month_name(self.__months[month["month_index"]])

                    for month_day in month["month_days"]:
                        calendar[key][week_day["week_day_index"]].append(
                            datetime.strptime(
                                "{}.{}.{}".format(month_day, month_number, LEFT_YEAR if month_number > 6 else RIGHT_YEAR), 
                                "%d.%m.%Y"
                            ).date()
                        )

        return calendar

    def set_title(self, title : str) -> None:
        """Updates title

        Corrects given title before assignment
        """
        
        self.title = replace_roman_with_arabic_numerals(title)
