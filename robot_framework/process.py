"""This module contains the main process of the robot."""

import os
from datetime import date
from selenium import webdriver
from selenium.webdriver.common.by import By

from itk_dev_shared_components.eflyt import eflyt_login, eflyt_search, eflyt_case, eflyt_letter
import itk_dev_event_log
from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement, QueueStatus

from robot_framework.eflyt import filter_cases
from robot_framework import config


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    credentials = orchestrator_connection.get_credential("Eflyt")
    webdriver = eflyt_login.login(credentials.username, credentials.password)
    event_log = orchestrator_connection.get_constant("Event Log")
    itk_dev_event_log.setup_logging(event_log)

    eflyt_search.search(webdriver, to_date=date.today(), case_state="Ubehandlet")
    cases = eflyt_search.extract_cases(webdriver)
    orchestrator_connection.log_trace(f"Found {len(cases)} cases.")

    cases = filter_cases.filter_cases(cases)
    for case in cases:
        queue_element = get_queue_element(orchestrator_connection, case.case_number)
        if queue_element.status is not QueueStatus.NEW:
            continue
        orchestrator_connection.log_trace(f"Starting case {case.case_number}")
        eflyt_search.open_case(webdriver, case)
        handle_case(webdriver, orchestrator_connection, case.case_number)


def handle_case(webdriver: webdriver.Chrome, oc: OrchestratorConnection, reference: str):
    """Handle case in eFlyt."""
    oc.set_queue_element_status(reference, QueueStatus.IN_PROGRESS)
    # Check that there is just one applicant
    applicants = eflyt_case.get_applicants(webdriver)
    table = webdriver.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons")
    rows = table.find_elements(By.TAG_NAME, "tr")
    move_date = rows[0].find_element(By.XPATH, "td[2]/a[1]").text

    first_habitant_is_applicant = len(applicants) == 1 and rows[0].find_element(By.XPATH, "td[2]/a[1]").text == "A"
    if not first_habitant_is_applicant:
        itk_dev_event_log.emit(config.ROBOT_NAME, "Skipped")
        oc.log_trace("Skipping case, more than one inhabitant")
        oc.set_queue_element_status(reference, QueueStatus.ABANDONED)
        return

    letter_text = f"""Du har anmeldt udrejse af Danmark.

Vi har d. {date.today().strftime("%d-%m-%Y")} godkendt din anmodning om udrejse med virkning fra den {move_date}.
"""
    if not eflyt_letter.send_letter_to_anmelder(webdriver, letter_text):
        itk_dev_event_log.emit(config.ROBOT_NAME, "Not registered")
        oc.log_trace("Letter could not be sent.")
        oc.set_queue_element_status(reference, QueueStatus.ABANDONED)
        return

    eflyt_case.approve_case(webdriver)
    note_text = "Orientering om godkendelse af udrejse er sendt til anmelder"
    eflyt_case.add_note(webdriver, note_text)
    oc.log_trace("Case approved and note added.")
    itk_dev_event_log.emit(config.ROBOT_NAME, "Completed")
    oc.set_queue_element_status(reference, QueueStatus.DONE)


def get_queue_element(oc: OrchestratorConnection, reference: str) -> QueueElement:
    """Get the first existing queue element, or create a new one and return that.   

    Args:
        oc: Orchestrator connection to use.
        reference: Case number used as reference for queue element.

    Returns:
        A QueueElement for the case.
    """
    existing_elements = oc.get_queue_elements(config.ROBOT_NAME, reference)
    if len(existing_elements) == 0:
        return oc.create_queue_element(config.ROBOT_NAME, reference)
    return existing_elements[0]


if __name__ == "__main__":
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection(config.ROBOT_NAME, conn_string, crypto_key, "")
    process(oc)
