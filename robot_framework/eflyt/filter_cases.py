from itk_dev_shared_components.eflyt.eflyt_case import Case


def filter_cases(cases: list[Case]) -> list[Case]:
    """Filter cases on case types and return filtered list.

    Args:
        cases: List of cases

    Return:
        List of filtered cases
    """
    disallowed_case_types = (
        "Fraflytning høj vejkode",
        "Børneflytning 1",
        "Børneflytning 2",
        "Børneflytning 3",
        "Mindreårig",
        "Barn"
    )

    filtered_cases = [
        case for case in cases
        if all(case_type not in disallowed_case_types for case_type in case.case_types)
        and "Udland" in case.case_types
    ]

    return filtered_cases
