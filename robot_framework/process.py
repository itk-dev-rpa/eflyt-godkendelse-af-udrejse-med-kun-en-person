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


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    credentials = orchestrator_connection.get_credential("Eflyt")
    browser = eflyt_login.login(credentials.username, credentials.password)
    event_log = orchestrator_connection.get_constant("Event Log")
    itk_dev_event_log.setup_logging(event_log.value)

    eflyt_search.search(browser, to_date=date.today(), case_state="Ubehandlet")
    cases = eflyt_search.extract_cases(browser)
    orchestrator_connection.log_trace(f"Found {len(cases)} cases.")

    cases = filter_cases.filter_cases(cases)
    for case in cases:
        queue_element = get_queue_element(orchestrator_connection, case.case_number)
        if queue_element.status is not QueueStatus.NEW:
            continue
        orchestrator_connection.log_trace(f"Starting case {case.case_number}")
        eflyt_search.open_case(browser, case.case_number)
        handle_case(browser, orchestrator_connection, queue_element)


def handle_case(browser: webdriver.Chrome, oc: OrchestratorConnection, queue_element: QueueElement):
    """Handle case in eFlyt."""
    oc.set_queue_element_status(queue_element.id, QueueStatus.IN_PROGRESS)
    # Check that there is just one applicant
    applicants = eflyt_case.get_applicants(browser)
    table = browser.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons")
    rows = table.find_elements(By.TAG_NAME, "tr")
    move_date = rows[0].find_element(By.XPATH, "td[2]/a[1]").text

    first_habitant_is_applicant = len(applicants) == 1 and rows[1].find_element(By.XPATH, "td[2]/a[1]").text == "A"
    case_unprocessed = rows[0].find_element(By.XPATH, "td[6]/a[1]").text == "Ubehandlet" and rows[1].find_element(By.XPATH, "td[6]/a[1]").text == "Ubehandlet"
    if not first_habitant_is_applicant and not case_unprocessed:
        itk_dev_event_log.emit(oc.process_name, "Skipped")
        oc.log_trace("Skipping case")
        oc.set_queue_element_status(queue_element.id, QueueStatus.DONE)
        return

    date_today = date.today().strftime("%d-%m-%Y")
    letter_text = f"""Du har anmeldt udrejse af Danmark.

Vi har d. {date_today} godkendt din anmodning om udrejse med virkning fra den {move_date}.
"""
    if rows[0].find_element(By.XPATH, "td[4]/a[1]").text == "Engelsk":  # If it's an english citizen, write in english.
        letter_text = f"""You have reported your departure from Denmark.

        As of {date_today}, we have approved your request to be registered as having left the country, effective from {move_date}."""

    if not eflyt_letter.send_letter_to_anmelder(browser, letter_text):
        itk_dev_event_log.emit(oc.process_name, "Not registered with Digital Post")
        oc.log_trace("Letter could not be sent.")
        oc.set_queue_element_status(queue_element.id, QueueStatus.DONE)
        return

    eflyt_case.approve_case(browser)
    note_text = "Orientering om godkendelse af udrejse er sendt til anmelder"
    eflyt_case.add_note(browser, note_text)
    oc.log_trace("Case approved and note added.")
    itk_dev_event_log.emit(oc.process_name, "Completed")
    oc.set_queue_element_status(queue_element.id, QueueStatus.DONE)


def get_queue_element(oc: OrchestratorConnection, reference: str) -> QueueElement:
    """Get the first existing queue element, or create a new one and return that.   

    Args:
        oc: Orchestrator connection to use.
        reference: Case number used as reference for queue element.

    Returns:
        A QueueElement for the case.
    """
    existing_elements = oc.get_queue_elements(oc.process_name, reference)
    if len(existing_elements) == 0:
        return oc.create_queue_element(oc.process_name, reference)
    return existing_elements[0]


if __name__ == "__main__":
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    orchestrator_conn = OrchestratorConnection("Eflyt Godkendelse En Person", conn_string, crypto_key, "")
    process(orchestrator_conn)
