from datetime import date, timedelta

from apps.common.models import (
    AbstractEvent,
    DayDateOverride,
    Event,
)
from apps.common.selectors import Selector
from apps.common.services.timetable.read.filters import DateFilter, EventFilter


def calculate_semester_filling_parameters(abstract_event : AbstractEvent) -> tuple[date, date, date, int]:
    """Calculates semester filling parameters for given AbstarctEvent

    Returns semester_start_date, semester_end_date, fill_from_date, repetition_period
    """
    
    semester_start_date = abstract_event.schedule.start_date

    # if semester starts from FIRST week
    if abstract_event.schedule.starting_day_number.day_number < 7:
        fill_from_date = semester_start_date + timedelta(abstract_event.abstract_day.day_number)
    # otherwise when semester starts from SECOND week
    else:
        fill_from_date = semester_start_date + timedelta(abstract_event.abstract_day.day_number - 7)

    '''
    # finding first week monday date

    # if semester starts from FIRST week
    # finding previous first week monday date
    if abstract_event.schedule.starting_day_number.day_number < 7:
        fill_from_date -= timedelta(abstract_event.schedule.starting_day_number.day_number)
    # otherwise when semester starts from SECOND week
    # finding next first week monday date
    else:
        fill_from_date += timedelta(14 - abstract_event.schedule.starting_day_number.day_number)
    '''
    # adding abstract_event delta from first week monday
    #fill_from_date += timedelta(abstract_event.abstract_day.day_number)

    return semester_start_date, \
            abstract_event.schedule.end_date, \
            fill_from_date, \
            abstract_event.schedule.schedule_template.repetition_period

def check_for_day_date_override(abstract_event : AbstractEvent) -> None:
    """Find and apply if exists DayDateOverride 
    to Events from given AbstractEvent
    """

    from apps.common.services.timetable.write.factories import apply_day_date_override
    
    reader = Selector({"department" : abstract_event.department})

    # getting all DayDateOverrides for AbstractEvent
    reader.find_models(DayDateOverride)
    date_overrides = reader.get_found_models()

    reader.clear_filter_query()
    reader.add_filter({"abstract_event" : abstract_event})

    # applying date overrides to Events
    for ddo in date_overrides:
        reader.add_filter(DateFilter.from_singe_date(ddo.day_source))
        
        reader.find_models(Event)
        
        if reader.get_found_models().exists():
            for e in reader.get_found_models():
                apply_day_date_override(ddo, e)

        reader.remove_last_filter()

def refresh_related_events(abstract_event : AbstractEvent, update_non_m2m : bool = True, update_m2m : bool = True) -> None:
    """Renew related Events with values from given AbstractEvent

    Use update_non_m2m to renew NOT many-to-many fields

    Use update_m2m to renew many-to-many fields 

    update_non_m2m and update_m2m can be used at the same time

    Saves Event after changes
    """
    
    if not update_non_m2m and not update_m2m:
        return
    
    filter_query = {"abstract_event" : abstract_event}
    filter_query.update(EventFilter.not_overriden())

    for e in Event.objects.filter(**filter_query):
        if e.is_event_overriden:
            continue

        if update_non_m2m:
            e.kind_override = abstract_event.kind
            e.subject_override = abstract_event.subject
            e.time_slot_override = abstract_event.time_slot

        if update_m2m:
            e.participants_override.clear()
            e.participants_override.add(*abstract_event.participants.all())
            e.places_override.clear()
            e.places_override.add(*abstract_event.places.all())

        e.save()
