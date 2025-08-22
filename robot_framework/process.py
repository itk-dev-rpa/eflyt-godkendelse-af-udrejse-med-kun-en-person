"""This module contains the main process of the robot."""

import os
from datetime import date
from selenium import webdriver
from selenium.webdriver.common.by import By

from itk_dev_shared_components.eflyt import eflyt_login, eflyt_search, eflyt_case
from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

from robot_framework.eflyt import filter_cases


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    credentials = orchestrator_connection.get_credential("Eflyt")
    webdriver = eflyt_login.login(credentials.username, credentials.password)
    
    eflyt_search.search(webdriver, to_date=date.today(), case_state="Ubehandlet")
    cases = eflyt_search.extract_cases(webdriver)
    oc.log_trace(f"Found {len(cases)} cases.")

    cases = filter_cases.filter_cases(cases)

    for case in cases:
        orchestrator_connection.log_trace(f"Starting case {case}")
        eflyt_search.open_case(webdriver, case)
        handle_case(webdriver, orchestrator_connection)


def handle_case(webdriver: webdriver.Chrome, oc: OrchestratorConnection):
    # Check that there is just one applicant
    applicants = eflyt_case.get_applicants(webdriver)
    table = webdriver.find_element(By.ID, "ctl00_ContentPlaceHolder2_GridViewMovingPersons")
    rows = table.find_elements(By.TAG_NAME, "tr")
    move_date = rows[0].find_element(By.XPATH, "td[2]/a[1]").text
    first_habitant_is_applicant = len(applicants) == 1 and rows[0].find_element(By.XPATH, "td[2]/a[1]").text == "A"
    if not first_habitant_is_applicant:
        oc.log_trace("Skipping case, more than one inhabitant")
        return

    letter_text = f"""Du har anmeldt udrejse af Danmark.

Vi har d. {date.today().strftime("%d-%m-%Y")} godkendt din anmodning om udrejse med virkning fra den {move_date}.
"""
    if not send_letter_to_anmelder(webdriver, letter_text):
        oc.log_trace("Letter could not be sent.")
        return

    eflyt_case.approve_case(webdriver)
    note_text = "Orientering om godkendelse af udrejse er sendt til anmelder"
    eflyt_case.add_note(webdriver, note_text)
    oc.log_trace("Case approved and note added.")


if __name__ == "__main__":
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("eflyt-godkendelse-en-person-test", conn_string, crypto_key, "")
    process(oc)
